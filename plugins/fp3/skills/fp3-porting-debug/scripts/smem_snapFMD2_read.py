#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# snapFMD2 reader: unconditional entry-capture of framer mode-update fn. 'FMD2' present => fn ran.
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; HDR=0x2ab0
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA); buf=m.read(WIN); m.close()
print("== raw stash 0x86302ab0 +0..+0x30 ==")
for o in range(0,0x30,16):
    row=buf[HDR+o:HDR+o+16]
    print(f"  +{o:#04x}: "+" ".join(f"{x:02x}" for x in row)+"  "+"".join(chr(x) if 32<=x<127 else "." for x in row))
mg=buf[HDR:HDR+4]
print("FMD2 magic:", mg, "->", "HIT" if mg==b"FMD2" else "MISS")
if mg==b"FMD2":
    ctx,mode,e08,e58,db4,x6c,caller,cnt=struct.unpack_from("<8I",buf,HDR+4)
    print(f"  ctx            = {ctx:#010x}")
    print(f"  memw(ctx+0x78) = {mode:#010x}  (mode-flag; 1=active, 0=external)")
    print(f"  memw(ctx+0xe08)= {e08:#010x}  (detector input; bit0={e08&1})")
    print(f"  memw(ctx+0xe58)= {e58:#010x}")
    print(f"  memw(ctx+0xdb4)= {db4:#010x}")
    print(f"  memw(ctx+0x6c) = {x6c:#010x}")
    print(f"  caller r31     = {caller:#010x}  (which of 5: f04bf7dc/f04c36a0/f04c44f4/f04ce770/f04d1a4c)")
    print(f"  entry-count    = {cnt}")
