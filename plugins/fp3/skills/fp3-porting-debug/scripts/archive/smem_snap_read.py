#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# SAFE: single bounded mmap of ONLY 0x86300000. Reads the SNP0 snapshot stash
# at SMEM item-469 slot#12 +0x40 (in-SMEM 0x2ab0) written by the ADSP hook.
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000
STASH=0x2ab0   # slot12 (0x2a70) + 0x40
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA)
    buf=m.read(WIN); m.close()
ver=buf[0x2a70:0x2a70+40].split(b"\x00")[0].decode("latin1","replace")
print("ADSP ver slot :", ver)
magic=buf[STASH:STASH+4]
print("magic         :", magic, "->", "SNP0 OK" if magic==b"SNP0" else "NOT PRESENT")
names=["ctx+0x74 sat_hw_owner","ctx+0xe14 clock_handle","ctx+0xe18 npa_handle",
       "ctx+0xe1c","ctx+0x7c gear","ctx+0x88","ctx+0xdec"]
for i,nm in enumerate(names):
    v=struct.unpack_from("<I",buf,STASH+4+i*4)[0]
    print(f"  {nm:28s} = {v:#010x}")
