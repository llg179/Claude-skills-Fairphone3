#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# snapCGP2 reader: deeper hop — the actual driver fn memw(memw(handle+0x3c)+0).
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; HDR=0x2ab0
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA); buf=m.read(WIN); m.close()
magic=buf[HDR:HDR+4]
print("magic :", magic, "->", "CGP2 OK" if magic==b"CGP2" else "ABSENT/stale")
if magic!=b"CGP2": raise SystemExit
h,h38,s3c,fn,s3c4,s40,rc=struct.unpack_from("<7I",buf,HDR+0x04)
print(f"  handle           = {h:#010x}")
print(f"  handle+0x38      = {h38:#010x}")
print(f"  s3c=memw(h+0x3c) = {s3c:#010x}   (subobj ptr)")
print(f"  ★ DRIVER FN memw(s3c+0) = {fn:#010x}   <<< disasm THIS (if text) for CBCR poke")
print(f"  memw(s3c+4)      = {s3c4:#010x}")
print(f"  handle+0x40      = {s40:#010x}")
print(f"  config-group rc  = {rc:#010x}")
