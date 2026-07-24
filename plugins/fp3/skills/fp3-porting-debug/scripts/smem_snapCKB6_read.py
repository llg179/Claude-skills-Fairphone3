#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# snapCKB6 reader: LEVER — forced framer CBCR ENABLE. SAFE SMEM mmap.
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; HDR=0x2ab0
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA); buf=m.read(WIN); m.close()
mg=buf[HDR:HDR+4]
print("CKB6 magic:", mg, "->", "forced" if mg==b"CKB6" else "MISS")
if mg==b"CKB6":
    h,addr,pre,post=struct.unpack_from("<4I",buf,HDR+0x04)
    print(f"  handle={h:#010x} CBCR addr={addr:#010x}")
    print(f"  CBCR pre  = {pre:#010x}  (ENABLE={pre&1} CLK_OFF={(pre>>31)&1})")
    print(f"  CBCR post = {post:#010x}  (ENABLE={post&1} CLK_OFF={(post>>31)&1})  <- after forcing ENABLE=1")
    print("  => forced ENABLE latched; CLK_OFF still 1 => parent not feeding" if (post&1 and (post>>31)&1)
          else ("  => CLK_OFF cleared => branch clock RUNNING after force!" if (post&1 and not((post>>31)&1)) else "  => (unexpected)"))
