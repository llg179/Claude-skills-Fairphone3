#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; STASH=0x2ab0
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA); buf=m.read(WIN); m.close()
magic=buf[STASH:STASH+4]
print("magic:", magic, "->", "SNTb OK" if magic==b"SNTb" else "NOT PRESENT")
for i in range(20):
    va=0xf0c85400+i*4
    v=struct.unpack_from("<I",buf,STASH+4+i*4)[0]
    print(f"  0x{va:08x} = {v:#010x}")
