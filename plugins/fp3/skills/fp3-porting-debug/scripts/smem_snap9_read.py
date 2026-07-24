#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# SAFE: single bounded mmap of ONLY 0x86300000. Stage-9 (SNP9) @0x2ab0:
# {SNP9, id, rc} + 12 words from 0xf0c85400 (leaf structs for entry[2]@0xf0c85404 type4, entry[3]@0xf0c85428 type0xe)
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; STASH=0x2ab0; BASE=0xf0c85400
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA)
    buf=m.read(WIN); m.close()
print("ADSP ver :", buf[0x2a70:0x2a70+40].split(b"\x00")[0].decode("latin1","replace"))
print("magic    :", buf[STASH:STASH+4], "->", "SNP9 OK" if buf[STASH:STASH+4]==b"SNP9" else "MISSING")
idv,rc=struct.unpack_from("<II",buf,STASH+4)
print("id=%#06x rc=%#010x"%(idv,rc))
print("leaf window from %#010x:"%BASE)
for i in range(12):
    v=struct.unpack_from("<I",buf,STASH+0x0c+i*4)[0]
    va=BASE+i*4; tag=""
    if va==0xf0c85404: tag=" <-- entry[2] leaf (type4)"
    if va==0xf0c85428: tag=" <-- entry[3] leaf (type0xe)"
    print("  [%2d] %#010x = %#010x%s"%(i,va,v,tag))
