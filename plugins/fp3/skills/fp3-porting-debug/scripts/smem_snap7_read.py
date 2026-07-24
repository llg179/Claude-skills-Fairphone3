#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# SAFE: single bounded mmap of ONLY 0x86300000. Stage-7 (SNP7) @0x2ab0:
# {SNP7, id(ctx+0xe14), rc} then 12 words dumped from 0xf0c85440.
# f0191c68's actual cfg ptr r1 = 0xf0c85450 = base+0x10 (word index 4);
# it early-returns if *(r1+0x8)==0 or *(r1+0xc)==0.
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; STASH=0x2ab0; CFG=0xf0c85440; R1=0xf0c85450
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA)
    buf=m.read(WIN); m.close()
print("ADSP ver slot :", buf[0x2a70:0x2a70+40].split(b"\x00")[0].decode("latin1","replace"))
print("magic         :", buf[STASH:STASH+4], "->", "SNP7 OK" if buf[STASH:STASH+4]==b"SNP7" else "NOT PRESENT")
idv,rc=struct.unpack_from("<II",buf,STASH+4)
print("id(ctx+0xe14) = %#010x   rc = %#010x" % (idv,rc))
print("config window from %#010x  (f0191c68 uses r1=%#010x):" % (CFG,R1))
for i in range(12):
    v=struct.unpack_from("<I",buf,STASH+0x0c+i*4)[0]
    va=CFG+i*4; tag=""
    if va==R1:      tag=" <-- r1 struct base (r17)"
    if va==R1+0x4:  tag=" <-- r17+0x4 (<=8 check)"
    if va==R1+0x8:  tag=" <-- r17+0x8 (checked !=0)"
    if va==R1+0xc:  tag=" <-- r17+0xc (checked !=0)"
    print("  [%2d] %#010x = %#010x%s" % (i,va,v,tag))
