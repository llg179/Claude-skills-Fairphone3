#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# snapCGP2b reader: SAFE pointer-only deeper-hop capture (magic 'CGP3').
# Reads PA 0x86302ab0 (stash *(0xf090fcd4)+0x640). SAFE: single bounded SMEM mmap.
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; HDR=0x2ab0
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA); buf=m.read(WIN); m.close()
magic=buf[HDR:HDR+4]
print("magic :", magic, "->", "CGP3 OK" if magic==b"CGP3" else "ABSENT/stale (cave didn't run or wrong tag)")
if magic!=b"CGP3": raise SystemExit
h,f38,f3c,f40,f44,f48,rc=struct.unpack_from("<7I",buf,HDR+0x04)
print(f"  handle (ctx+0xe18)      = {h:#010x}")
print(f"  handle+0x38             = {f38:#010x}")
print(f"  ★ handle+0x3c SUBOBJ PTR = {f3c:#010x}   <<< the deeper-hop ptr (captured, NOT deref)")
print(f"  handle+0x40             = {f40:#010x}")
print(f"  handle+0x44             = {f44:#010x}")
print(f"  handle+0x48 (poke)      = {f48:#010x}")
print(f"  config-group rc         = {rc:#010x}")
