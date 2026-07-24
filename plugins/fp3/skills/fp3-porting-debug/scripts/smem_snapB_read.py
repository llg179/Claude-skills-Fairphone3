#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# SAFE single mmap of 0x86300000. SNPB level-2 walk: handle+0x10 subobj slice.
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; STASH=0x2ab0
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA)
    buf=m.read(WIN); m.close()
print("ADSP ver slot :", buf[0x2a70:0x2a70+40].split(b"\x00")[0].decode("latin1","replace"))
magic=buf[STASH:STASH+4]
print("magic         :", magic, "->", "SNPB OK" if magic==b"SNPB" else "NOT PRESENT")
names=["handle (ctx+0xe18)","subobj memw(handle+0x10)","subobj+0x00 class_ptr",
       "subobj+0x14 hal_vtable","subobj+0x18 result","subobj+0x24 desc",
       "subobj+0x54 desc2","subobj+0x64 obj_ptr","subobj+0x04"]
for i,nm in enumerate(names):
    v=struct.unpack_from("<I",buf,STASH+4+i*4)[0]
    print(f"  {nm:26s} = {v:#010x}")
