#!/usr/bin/env python3
# Reads the FST1 live framing-START capability-wait trace: SMEM PA 0x86300000 + 0x2ab0.
# Layout: 'FST1' | wait-return | ctx+0xe54 | ctx+0xe0c | ctx+0xe08 | ctx+0xeb0 | ctx+0xeb4 | ctx+0x5c | count
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; HDR=0x2ab0
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA); buf=m.read(WIN); m.close()
mg=buf[HDR:HDR+4]
print("FST1 magic:", mg, "->", "HIT" if mg==b"FST1" else "MISS")
if mg==b"FST1":
    (wret,e54,e0c,e08,eb0,eb4,base,cnt)=struct.unpack_from("<8I",buf,HDR+4)
    print(f"  reached-count      = {cnt}   (times the post-wait point executed during this SSR init)")
    print(f"  wait-return (r0)   = {wret:#010x}   <- the queue-recv result: 0=success/msg, nonzero=timeout/err code")
    print(f"  ctx+0xe54          = {e54:#010x}   <- !=0 -> takes error/status handler 0xf0175b38")
    print(f"  ctx+0xe0c          = {e0c:#010x}")
    print(f"  ctx+0xe08          = {e08:#010x}   <- capability callable object ptr")
    print(f"  ctx+0xeb0          = {eb0:#010x}   <- set to 1 pre-wait; 0 after processing")
    print(f"  ctx+0xeb4          = {eb4:#010x}")
    print(f"  ctx+0x5c (frmbase) = {base:#010x}   <- sanity, expect 0xee140000")
