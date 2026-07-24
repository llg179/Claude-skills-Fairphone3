#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# snapCGP reader: dynamic-capture of the runtime-dispatched clock poke fn-pointer.
# Reads PA 0x86302ab0 (stash *(0xf090fcd4)+0x640). SAFE: single bounded SMEM mmap.
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; HDR=0x2ab0
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA); buf=m.read(WIN); m.close()
magic=buf[HDR:HDR+4]
print("magic :", magic, "->", "CGP1 OK" if magic==b"CGP1" else "ABSENT/stale (cave didn't run or wrong tag)")
if magic!=b"CGP1": raise SystemExit
h,poke,f34,f40,f44,f08,f0c,rc=struct.unpack_from("<8I",buf,HDR+0x04)
print(f"  handle (ctx+0xe18)      = {h:#010x}")
print(f"  ★ POKE FN-PTR memw(h+0x48)= {poke:#010x}   <<< disasm THIS for the CBCR write")
print(f"  handle+0x34             = {f34:#010x}")
print(f"  handle+0x40             = {f40:#010x}")
print(f"  handle+0x44             = {f44:#010x}")
print(f"  handle+0x08             = {f08:#010x}")
print(f"  handle+0x0c             = {f0c:#010x}")
print(f"  config-group rc         = {rc:#010x}")
