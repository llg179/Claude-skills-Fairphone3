#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# snapCKB2 reader: POST-ENABLE framer-clock RCGR (latch test). SAFE bounded SMEM mmap.
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; HDR=0x2ab0
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA); buf=m.read(WIN); m.close()
sent=buf[HDR+0x44:HDR+0x48]
print("CKB2 sentinel:", sent, "->", "OK (framer reached poll, post-enable captured)" if sent==b"CKB2" else "ABSENT (framer never reached the poll / base!=0xee012000)")
if sent==b"CKB2":
    cmd,cfg,M,N,D=struct.unpack_from("<5I",buf,HDR+0x30)
    root_off=(cmd>>31)&1; update=cmd&1
    print(f"  CMD_RCGR = {cmd:#010x}   ROOT_OFF(bit31)={root_off}  UPDATE(bit0)={update}")
    print(f"  CFG_RCGR = {cfg:#010x}   src-sel[10:8]={(cfg>>8)&7}  div[4:0]={cfg&0x1f}")
    print(f"  M={M:#010x}  N={N:#010x}  D={D:#010x}")
    print("  => ROOT_OFF=1 means the RCG root did NOT turn on (parent/source missing)" if root_off else "  => ROOT_OFF=0: RCG root running")
