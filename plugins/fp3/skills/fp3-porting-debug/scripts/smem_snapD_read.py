#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# SAFE single mmap of 0x86300000. SNPD: apply/set_rate object (obj2=subobj+0x04).
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; STASH=0x2ab0
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA)
    buf=m.read(WIN); m.close()
magic=buf[STASH:STASH+4]
print("magic         :", magic, "->", "SNPD OK" if magic==b"SNPD" else "NOT PRESENT")
names=["handle (ctx+0xe18)","subobj memw(handle+0x10)","obj2 memw(subobj+0x04)",
       "obj2+0x00","obj2+0x04 (apply_fn?)","obj2+0x08","obj2+0x0c",
       "obj2+0x10","obj2+0x14","obj2+0x18","obj2+0x1c",
       "FIX[0xf09b2e50]+0x00","FIX+0x04 (apply_fn?)","FIX+0x08","FIX+0x0c",
       "subobj+0x1c (vote)","subobj+0x20 (vote)","subobj+0x24 (vote)",
       "subobj+0x28 (vote)","subobj+0x2c (AGG RATE out)","subobj+0x54 (gear)"]
for i,nm in enumerate(names):
    v=struct.unpack_from("<I",buf,STASH+4+i*4)[0]
    print(f"  {nm:28s} = {v:#010x}")
