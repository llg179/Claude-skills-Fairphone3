#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# SAFE single mmap of 0x86300000. SNT3 (T3 hop-1): config-group runtime state + .bss gate.
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; STASH=0x2ab0
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA)
    buf=m.read(WIN); m.close()
magic=buf[STASH:STASH+4]
print("magic         :", magic, "->", "SNT3 OK" if magic==b"SNT3" else "NOT PRESENT (stale/absent)")
names=["r0 config-group rc","GATE memw(0xf0913658)","memw(0xf091365c)","memw(0xf0913660)",
       "ctx+0x74 sat_hw_owner","ctx+0xe14 group id","ctx+0xe18 core-clk handle",
       "cfg[0xf0c85450]+0x00","cfg+0x04","cfg+0x08","cfg+0x0c","cfg+0x10","cfg+0x14","cfg+0x18","cfg+0x1c",
       "0xf0c85440+0x00","+0x04","+0x08","+0x0c"]
for i,nm in enumerate(names):
    v=struct.unpack_from("<I",buf,STASH+4+i*4)[0]
    print(f"  +0x{4+i*4:02x} {nm:26s} = {v:#010x}")
