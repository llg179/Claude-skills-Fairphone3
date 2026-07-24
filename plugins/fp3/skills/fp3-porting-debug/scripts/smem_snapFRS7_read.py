#!/usr/bin/env python3
# Reads the FRS7 ctx-scan stash: SMEM PA 0x86300000 + 0x2ab0. Layout: 'FRS7' | count | up to 8 (off,val) pairs.
# Each pair = an offset into the framer ctx whose value is an LPASS MMIO pointer (0xeexxxxxx). +0x5c = framer
# base (0xee140000, known); ANY OTHER offset = a clock/pad sibling base -> the C1/C3 target.
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; HDR=0x2ab0; MAXP=8
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA); buf=m.read(WIN); m.close()
mg=buf[HDR:HDR+4]
print("FRS7 magic:", mg, "->", "HIT" if mg==b"FRS7" else "MISS")
if mg==b"FRS7":
    cnt=struct.unpack_from("<I",buf,HDR+4)[0]
    print(f"  LPASS-pointer fields found in ctx = {cnt}"+("  (>=8: capped, re-scan upper range)" if cnt>=MAXP else ""))
    n=min(cnt,MAXP)
    for i in range(n):
        off,val=struct.unpack_from("<2I",buf,HDR+0x08+i*8)
        tag=""
        if val==0xee140000: tag="  <- framer base (known, FRS1)"
        elif 0xee010000<=val<0xee014000: tag="  <- LPASS clock region (C1 candidate)"
        else: tag="  <- ★ sibling LPASS block (C1/C3 candidate)"
        print(f"  ctx+{off:#06x} = {val:#010x}{tag}")
    if n==0:
        print("  (no LPASS pointer in ctx+0..0xdfc -> framer base held elsewhere / indirected)")
