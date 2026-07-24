#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# SAFE single mmap of 0x86300000. SNPC: class object (class_ptr) field dump.
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; STASH=0x2ab0
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA)
    buf=m.read(WIN); m.close()
magic=buf[STASH:STASH+4]
print("magic         :", magic, "->", "SNPC OK" if magic==b"SNPC" else "NOT PRESENT")
names=["handle (ctx+0xe18)","subobj memw(handle+0x10)","class_ptr memw(subobj+0)",
       "class_ptr+0x00","class_ptr+0x04","class_ptr+0x08","class_ptr+0x0c",
       "class_ptr+0x10 (cap/method)","class_ptr+0x14","class_ptr+0x18",
       "class_ptr+0x1c","class_ptr+0x20"]
for i,nm in enumerate(names):
    v=struct.unpack_from("<I",buf,STASH+4+i*4)[0]
    print(f"  {nm:28s} = {v:#010x}")
