#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Full ADSP F3 dump: all readable EXT (0x79) msgs grouped by ss_id + source file,
# plus QSR (0x92) msgs with line/hash/args and best-effort pointer-arg resolution.
#   f3_dump.py <raw_f3.bin> <adsp.mbn>
import sys, struct
raw = open(sys.argv[1], 'rb').read()
mbn = open(sys.argv[2], 'rb').read()

e_phoff, = struct.unpack_from('<I', mbn, 28)
e_phentsize, e_phnum = struct.unpack_from('<HH', mbn, 42)
LOADS = []
for i in range(e_phnum):
    o = e_phoff + i * e_phentsize
    p_type, p_off, p_vaddr, _, p_filesz, _ = struct.unpack_from('<IIIIII', mbn, o)
    if p_type == 1 and p_filesz:
        LOADS.append((p_vaddr, p_off, p_filesz))
def va2off(va):
    for v, o, fs in LOADS:
        if v <= va < v + fs: return o + (va - v)
    return None
def cstr(va, maxlen=160):
    o = va2off(va)
    if o is None: return None
    e = mbn.find(b'\x00', o, o + maxlen)
    if e < 0: return None
    s = mbn[o:e]
    try: t = s.decode('ascii')
    except Exception: return None
    if len(t) < 2 or any(ord(c) < 9 or (13 < ord(c) < 32) for c in t): return None
    return t

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
    if len(p) > 2: frames.append(p[:-2])

ext = {}   # ss -> list of (line, fname, fmt, args)
for p in frames:
    if len(p) < 20 or p[0] != 0x79: continue
    na = p[2]; line = struct.unpack_from('<H', p, 12)[0]; ss = struct.unpack_from('<H', p, 14)[0]
    args = struct.unpack_from('<%dI' % na, p, 20) if na else ()
    rest = p[20 + 4 * na:].split(b'\x00')
    fmt = rest[0].decode('ascii', 'replace')
    fname = rest[1].decode('ascii', 'replace') if len(rest) > 1 else ''
    ext.setdefault(ss, []).append((line, fname, fmt, args))

def fill(fmt, args):
    out = fmt; i = 0
    def rep(_):
        nonlocal i
        v = args[i] if i < len(args) else 0; i += 1
        return str(v)
    import re
    # crude %-expansion for readability
    def sub(m):
        nonlocal i
        v = args[i] if i < len(args) else 0; i += 1
        c = m.group(0)
        if c.endswith('s'):
            s = cstr(v); return s if s else ('0x%x' % v)
        if c.endswith(('x', 'X', 'p')): return '0x%x' % v
        return str(v)
    return re.sub(r'%[-#0-9.lhz]*[dioxXupsc]', sub, fmt)

print("############ READABLE EXT (0x79) by ss_id ############")
for ss in sorted(ext):
    print("\n===== ss_id=%d  (%d msgs) =====" % (ss, len(ext[ss])))
    seen = set()
    for line, fname, fmt, args in ext[ss]:
        key = (line, fmt, args)
        if key in seen: continue
        seen.add(key)
        print("  [%-22s L%-5d] %s" % (fname, line, fill(fmt, args)))

# QSR with pointer-arg resolution
print("\n############ QSR (0x92) args (pointer-args resolved) ############")
for p in frames:
    if len(p) < 20 or p[0] != 0x92: continue
    na = p[2]; line = struct.unpack_from('<H', p, 12)[0]; ss = struct.unpack_from('<H', p, 14)[0]
    mask, = struct.unpack_from('<I', p, 16)
    h, = struct.unpack_from('<I', p, 20)
    args = struct.unpack_from('<%dI' % na, p, 24) if na else ()
    if ss not in (53, 0): continue
    argstr = []
    for a in args:
        s = cstr(a)
        argstr.append('"%s"' % s if s else '0x%x' % a)
    print("  ss=%d L%-5d mask=%d hash=0x%08x args=[%s]" % (ss, line, mask, h, ', '.join(argstr)))
