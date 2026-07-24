#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; HDR=0x2ab0
OFFS=[0x000,0x004,0x008,0x00c,0x010,0x014,0x018,0x01c,0x600,0x604,0x608,0x60c,0x610,0x614,0x618,0x61c]
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA); buf=m.read(WIN); m.close()
mg=buf[HDR:HDR+4]
print("FRS2 magic:", mg, "->", "HIT" if mg==b"FRS2" else "MISS")
if mg==b"FRS2":
    base,cnt=struct.unpack_from("<2I",buf,HDR+4)
    print(f"  framer_base = {base:#010x}   reads-completed = {cnt}/16")
    vals=struct.unpack_from("<16I",buf,HDR+0x0c)
    for i,off in enumerate(OFFS):
        done = i < cnt
        extra=""
        if off==0x604: extra=f"  FS={(vals[i]>>11)&1} SFS={(vals[i]>>12)&1} MS={(vals[i]>>13)&1}"
        print(f"  {base+off:#010x} (+{off:#05x}) = {vals[i]:#010x}{extra}" + ("" if done else "   <-- NOT READ (hang?)"))
