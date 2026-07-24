#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# F0/§0.1 full-snapshot read: 0x2c marker + neighbour SLIMbus-block sanity + FRM_STAT + timestamp.
# SAFE: only addresses proven readable on pmOS under PAS (QDSP6SS 0xc200000 block per E1/E3;
# SLIMbus wrapper FRM_CFG/FRM_STAT per context doc §2). ADSP must be up (state=running).
import mmap, os, struct, time, sys
def rd(base, offs, span=0x1000):
    f=os.open('/dev/mem', os.O_RDONLY|os.O_SYNC)
    pg=base & ~0xfff; delta=base-pg
    m=mmap.mmap(f, span, mmap.MAP_SHARED, mmap.PROT_READ, offset=pg)
    out={o: struct.unpack_from('<I', m, delta+o)[0] for o in offs}
    m.close(); os.close(f); return out
ts=time.strftime('%Y-%m-%d %H:%M:%S')
up=open('/proc/uptime').read().split()[0]
print(f"# snapshot {ts} uptime={up}")
q=rd(0x0c200000, [0x00,0x04,0x08,0x10,0x2c,0x110])
print("QDSP6SS 0x0c200000 block:")
for o in [0x00,0x04,0x08,0x10,0x2c,0x110]:
    tag=" <== MARKER 0x2c (UT/PIL=0x103, pmOS/PAS=0x10b)" if o==0x2c else (" STRAP" if o==0x110 else "")
    print(f"  +0x{o:03x} = 0x{q[o]:08x}{tag}")
s=rd(0x0c140000, [0x400,0x404])
print("SLIMbus wrapper 0x0c140000 (neighbour sanity + symptom):")
print(f"  +0x400 FRM_CFG  = 0x{s[0x400]:08x}  (known-nonzero sanity; expect 0x000D0C83)")
print(f"  +0x404 FRM_STAT = 0x{s[0x404]:08x}  (SYMPTOM: 0=dead framer, nonzero=framing)")
