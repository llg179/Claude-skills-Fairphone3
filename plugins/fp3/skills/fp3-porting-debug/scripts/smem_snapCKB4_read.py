#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# snapCKB4 reader: POST-ENABLE framer CBCR (does the branch clock turn on?). SAFE SMEM mmap.
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; HDR=0x2ab0
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA); buf=m.read(WIN); m.close()
mg=buf[HDR+0x30:HDR+0x34]
print("CKB4 magic:", mg, "->", "HIT (framer CBCR enable ran)" if mg==b"CKB4" else "MISS (CBCR-enable 0xf04df0ac not called for framer)")
if mg==b"CKB4":
    addr,cbcr,mask=struct.unpack_from("<3I",buf,HDR+0x34)
    clk_off=(cbcr>>31)&1; en=cbcr&1
    print(f"  CBCR addr            = {addr:#010x}")
    print(f"  ★ POST-ENABLE CBCR    = {cbcr:#010x}   ENABLE(bit0)={en}  CLK_OFF(bit31)={clk_off}   mask={mask:#x}")
    print("    => CLK_OFF=1: branch ENABLED but clock NOT running (parent RCG not feeding) = framer clock dead at branch" if clk_off
          else "    => CLK_OFF=0: branch clock RUNNING (framer clock is live at branch level)")
