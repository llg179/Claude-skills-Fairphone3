#!/usr/bin/env python3
# Reads the FRS8 ctx-scan stash: SMEM PA 0x86300000 + 0x2ab0. Layout: 'FRS8' | count | up to 8 (off,val) pairs.
# FRS8 records ctx fields holding EITHER an LPASS MMIO pointer (0xee..) OR an ADSP image/data pointer (0xf0..).
# +0x5c = framer base (0xee140000, known). A 0xf0xxxxxx field = the parent/device struct pointer -> chase it
# (FRS9) to scan that struct for the clock/pad LPASS base. Any OTHER 0xee.. field = a direct clock/pad sibling.
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; HDR=0x2ab0; MAXP=8
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA); buf=m.read(WIN); m.close()
mg=buf[HDR:HDR+4]
print("FRS8 magic:", mg, "->", "HIT" if mg==b"FRS8" else "MISS")
if mg==b"FRS8":
    cnt=struct.unpack_from("<I",buf,HDR+4)[0]
    print(f"  pointer fields found in ctx = {cnt}"+("  (>=8: capped, re-scan/narrow)" if cnt>=MAXP else ""))
    n=min(cnt,MAXP)
    for i in range(n):
        off,val=struct.unpack_from("<2I",buf,HDR+0x08+i*8)
        if val==0xee140000: tag="  <- framer base (known)"
        elif 0xee000000<=val<0xee400000: tag="  <- ★ LPASS sibling (direct clock/pad candidate)"
        elif 0xf0000000<=val<0xf1000000: tag="  <- ★ ADSP image/data ptr (parent-struct candidate -> chase)"
        else: tag=""
        print(f"  ctx+{off:#06x} = {val:#010x}{tag}")
