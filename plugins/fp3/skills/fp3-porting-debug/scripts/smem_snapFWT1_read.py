#!/usr/bin/env python3
# Reads the FWT1 framer-write trace ring: SMEM PA 0x86300000 + 0x2af0 (ADSP stash +0x680).
# Layout: 'FWTF' | count | up to 64 (addr,value) pairs. addr in framer aperture 0xee14xxxx.
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; HDR=0x2af0; MAXP=64
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA); buf=m.read(WIN); m.close()
mg=buf[HDR:HDR+4]
print("FWT1 magic:", mg, "->", "HIT" if mg==b"FWTF" else "MISS")
if mg==b"FWTF":
    cnt=struct.unpack_from("<I",buf,HDR+4)[0]
    n=min(cnt,MAXP)
    print(f"  framer writes captured = {cnt}"+("  (>=64 capped)" if cnt>=MAXP else ""))
    for i in range(n):
        addr,val=struct.unpack_from("<2I",buf,HDR+0x08+i*8)
        off=addr-0xee140000
        print(f"  [{i:2}] framer+{off:#06x} (addr {addr:#010x}) <= {val:#010x}")
