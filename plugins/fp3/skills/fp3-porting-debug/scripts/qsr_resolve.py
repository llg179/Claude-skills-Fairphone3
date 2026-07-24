#!/usr/bin/env python3
# Attack the QSR wall: resolve terse (0x92) ADSP F3 messages against adsp.mbn.
#
# QShrink terse messages replace the embedded fmt/fname strings with a POINTER
# to the message's const descriptor (msg_const_type) living in the ELF's RO data.
# The ELF is stripped of section headers, but PT_LOAD phdrs give VA->file-offset.
# We brute-check every u32 in the terse payload as a candidate descriptor VA:
# a valid descriptor is {desc:{line,ss_id,ss_mask}, char* fmt, char* fname} where
# fmt/fname point to ASCII strings inside the image. That both validates the
# layout and yields the readable string + args.
#
#   qsr_resolve.py <raw_f3.bin> <adsp.mbn> [ss_id_filter]
import sys, struct

raw = open(sys.argv[1], 'rb').read()
mbn = open(sys.argv[2], 'rb').read()
ss_filter = int(sys.argv[3]) if len(sys.argv) > 3 else None

# ---- ELF32 phdr VA->offset ----
e_phoff, = struct.unpack_from('<I', mbn, 28)
e_phentsize, e_phnum = struct.unpack_from('<HH', mbn, 42)
LOADS = []  # (vaddr, off, filesz)
for i in range(e_phnum):
    o = e_phoff + i * e_phentsize
    p_type, p_off, p_vaddr, p_paddr, p_filesz, p_memsz = struct.unpack_from('<IIIIII', mbn, o)
    if p_type == 1 and p_filesz:
        LOADS.append((p_vaddr, p_off, p_filesz))

def va2off(va):
    for vaddr, off, filesz in LOADS:
        if vaddr <= va < vaddr + filesz:
            return off + (va - vaddr)
    return None

def cstr(va, maxlen=200):
    o = va2off(va)
    if o is None:
        return None
    e = mbn.find(b'\x00', o, o + maxlen)
    if e < 0:
        return None
    s = mbn[o:e]
    try:
        t = s.decode('ascii')
    except Exception:
        return None
    if not t or any(c < 9 or (13 < ord(c) < 32) for c in t):
        return None
    return t

def rd_u32(va):
    o = va2off(va)
    if o is None or o + 4 > len(mbn):
        return None
    return struct.unpack_from('<I', mbn, o)[0]

# ---- deframe ----
def unescape(r):
    u = bytearray(); esc = False
    for b in r:
        if esc: u.append(b ^ 0x20); esc = False
        elif b == 0x7d: esc = True
        else: u.append(b)
    return bytes(u)

frames = []
for fr in raw.split(b'\x7e'):
    if not fr: continue
    p = unescape(fr)
    if len(p) <= 2: continue
    frames.append(p[:-2])

def try_resolve_descriptor(va):
    """If va points to a plausible msg_const_type, return (line, ss, mask, fmt, fname)."""
    o = va2off(va)
    if o is None or o + 12 > len(mbn):
        return None
    line, ss = struct.unpack_from('<HH', mbn, o)
    mask, = struct.unpack_from('<I', mbn, o + 4)
    # descriptor variants: try fmt/fname pointers at a few offsets
    for base in (8, 12):
        if o + base + 8 > len(mbn):
            continue
        fmt_p, fname_p = struct.unpack_from('<II', mbn, o + base)
        fmt = cstr(fmt_p); fname = cstr(fname_p)
        if fmt and fname and len(fmt) >= 2:
            return (line, ss, mask, fmt, fname, base)
    # maybe only a single fmt pointer follows
    fmt_p, = struct.unpack_from('<I', mbn, o + 8)
    fmt = cstr(fmt_p)
    if fmt and len(fmt) >= 3:
        return (line, ss, mask, fmt, '(nofile)', 8)
    return None

print("=== frames: %d total ===" % len(frames))
hist = {}
for p in frames:
    if len(p) < 16: continue
    ss = struct.unpack_from('<H', p, 14)[0]
    hist[(p[0], ss)] = hist.get((p[0], ss), 0) + 1
print("cmd/ss histogram:", {("0x%02x" % k[0], k[1]): v for k, v in sorted(hist.items())})

for p in frames:
    if len(p) < 20: continue
    cmd = p[0]; num_args = p[2]
    line = struct.unpack_from('<H', p, 12)[0]
    ss = struct.unpack_from('<H', p, 14)[0]
    if ss_filter is not None and ss != ss_filter:
        continue
    tag = 'EXT' if cmd == 0x79 else ('QSR' if cmd == 0x92 else '0x%02x' % cmd)
    print("\n[%s ss=%d L%d nargs=%d len=%d]" % (tag, ss, line, num_args, len(p)))
    print("  hex:", p.hex())
    if cmd == 0x79:
        rest = p[20 + 4 * num_args:]
        parts = rest.split(b'\x00')
        print("  fmt  :", parts[0].decode('ascii', 'replace'))
        if len(parts) > 1: print("  fname:", parts[1].decode('ascii', 'replace'))
        if num_args:
            args = struct.unpack_from('<%dI' % num_args, p, 20)
            print("  args :", [hex(a) for a in args])
    elif cmd == 0x92:
        # brute-force: every u32 in payload as candidate descriptor VA
        found = False
        for off in range(16, len(p) - 3):
            va = struct.unpack_from('<I', p, off)[0]
            r = try_resolve_descriptor(va)
            if r:
                dline, dss, dmask, fmt, fname, dbase = r
                print("  >>> descriptor@0x%08x (payload off %d, dbase %d): ss=%d L%d" % (va, off, dbase, dss, dline))
                print("      fmt  : %s" % fmt)
                print("      fname: %s" % fname)
                found = True
        if not found:
            print("  (no descriptor pointer resolved)")
