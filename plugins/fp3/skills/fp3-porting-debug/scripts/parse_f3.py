#!/usr/bin/env python3
import sys, struct
buf = open(sys.argv[1], 'rb').read()

def unescape(raw):
    u = bytearray(); esc = False
    for b in raw:
        if esc: u.append(b ^ 0x20); esc = False
        elif b == 0x7d: esc = True
        else: u.append(b)
    return bytes(u)

ext = {}   # (ss,line,fname,fmt) -> count
qsr = {}   # (ss,line,hash) -> count
other = {}
for frame in buf.split(b'\x7e'):
    if not frame: continue
    p = unescape(frame)
    if len(p) <= 2: continue
    p = p[:-2]
    if len(p) < 20: continue
    cmd = p[0]
    num_args = p[2]
    line = struct.unpack_from('<H', p, 12)[0]
    ss = struct.unpack_from('<H', p, 14)[0]
    off = 20 + 4 * num_args
    if cmd == 0x79:
        parts = p[off:].split(b'\x00')
        fmt = parts[0].decode('ascii', 'replace')
        fname = parts[1].decode('ascii', 'replace') if len(parts) > 1 else ''
        ext[(ss, line, fname, fmt)] = ext.get((ss, line, fname, fmt), 0) + 1
    elif cmd == 0x92:
        h = struct.unpack_from('<I', p, 20)[0] if len(p) >= 24 else 0
        qsr[(ss, line, h)] = qsr.get((ss, line, h), 0) + 1
    else:
        other[cmd] = other.get(cmd, 0) + 1

print("=== EXT (0x79, readable) unique by ss_id ===")
for ss in sorted(set(k[0] for k in ext)):
    print(f"--- ss_id={ss} ---")
    for (s, line, fname, fmt), c in sorted(ext.items()):
        if s != ss: continue
        print(f"  L{line:<5} {fname:<20} x{c}  {fmt}")
print("\n=== QSR (0x92, hashed) unique by ss_id ===")
for ss in sorted(set(k[0] for k in qsr)):
    lines = sorted(set((k[1], k[2]) for k in qsr if k[0] == ss))
    tot = sum(c for k, c in qsr.items() if k[0] == ss)
    print(f"  ss_id={ss}: {len(lines)} distinct msgs, {tot} total; lines={[l for l,_ in lines][:20]}")
print("\nother cmds:", other)
