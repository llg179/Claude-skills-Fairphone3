#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# snapCKB3 reader: framer BRANCH-CLOCK (CBCR) capture. SAFE bounded SMEM mmap.
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; HDR=0x2ab0
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA); buf=m.read(WIN); m.close()
mg=buf[HDR:HDR+4]
print("CKB3 magic:", mg, "->", "HIT (framer enable ran)" if mg==b"CKB3" else "MISS")
if mg==b"CKB3":
    h,ops,h10,h14,h18,cbcr_addr,h20,cbcr,cbcr4=struct.unpack_from("<9I",buf,HDR+0x04)
    print(f"  handle        = {h:#010x}   ops-vtable(+0x0c)={ops:#010x}")
    print(f"  handle +0x10={h10:#010x} +0x14={h14:#010x} +0x18={h18:#010x} +0x20={h20:#010x}")
    print(f"  ★ CBCR addr (h+0x1c) = {cbcr_addr:#010x}")
    if cbcr:
        clk_off=(cbcr>>31)&1; enable=cbcr&1
        print(f"  ★ CBCR value (memw+0) = {cbcr:#010x}   ENABLE(bit0)={enable}  CLK_OFF(bit31)={clk_off}")
        print(f"    CBCR +0x04          = {cbcr4:#010x}")
        print("    => CLK_OFF=1 => branch clock is OFF (not running)" if clk_off else "    => CLK_OFF=0 => branch clock RUNNING")
    else:
        print(f"  CBCR value NOT read (h+0x1c={cbcr_addr:#010x} outside 0xee000000-0xee100000 guard) -> +0x1c is not the CBCR; check other handle offsets above")
