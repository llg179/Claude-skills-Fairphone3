#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# snapFRS1 reader: framer HW register-state at enumerate-timeout. Decodes FS/SFS/MS from base+0x604.
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; HDR=0x2ab0
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA); buf=m.read(WIN); m.close()
print("== raw stash +0..+0x30 ==")
for o in range(0,0x30,16):
    row=buf[HDR+o:HDR+o+16]
    print(f"  +{o:#04x}: "+" ".join(f"{x:02x}" for x in row)+"  "+"".join(chr(x) if 32<=x<127 else "." for x in row))
mg=buf[HDR:HDR+4]
print("FRS1 magic:", mg, "->", "HIT" if mg==b"FRS1" else "MISS")
if mg==b"FRS1":
    ctx,mode,gate,devid,base,r600,r604,r608,r60c,mark=struct.unpack_from("<10I",buf,HDR+4)
    print(f"  ctx              = {ctx:#010x}")
    print(f"  memw(ctx+0x78)   = {mode:#010x}  (mode 1=active 0=external)")
    print(f"  memw(ctx+0xdfc)  = {gate:#010x}  (this fn's branch gate)")
    print(f"  memw(ctx+0xe00)  = {devid:#010x}  (DevId)")
    print(f"  framer_base(+0x5c)= {base:#010x}")
    print(f"  MMIO-reached mark = {mark:#06x} ({'yes' if mark==0xf00d else 'NO — base null or read skipped'})")
    if mark==0xf00d:
        print(f"  base+0x600 = {r600:#010x}")
        print(f"  base+0x604 = {r604:#010x}  FS(b11)={(r604>>11)&1} SFS(b12)={(r604>>12)&1} MS(b13)={(r604>>13)&1}")
        print(f"  base+0x608 = {r608:#010x}")
        print(f"  base+0x60c = {r60c:#010x}")
