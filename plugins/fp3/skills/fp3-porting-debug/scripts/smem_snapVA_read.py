#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
import mmap, struct
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),0x40000,mmap.MAP_SHARED,mmap.PROT_READ,offset=0x86300000); buf=m.read(0x40000); m.close()
H=0x2ab0; magic=buf[H:H+4]
print("magic:",magic,"->","HVA0 OK" if magic==b"HVA0" else "ABSENT")
if magic==b"HVA0":
    va,n0,n8,rc=struct.unpack_from("<4I",buf,H+4)
    print(f"  *(0xf090fcd4) = {va:#010x}   <- SMEM base ADSP-VA (hardcode this + 0x640 in the early leaf cave)")
    print(f"  *(0xf090fcd0) = {n0:#010x}")
    print(f"  *(0xf090fcd8) = {n8:#010x}")
    print(f"  config rc     = {rc:#010x}")
