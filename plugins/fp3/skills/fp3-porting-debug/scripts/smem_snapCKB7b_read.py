#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# snapCKB7b reader: framer-block branch-enable caller+value (0xee012014 / 0xee012018).
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; HDR=0x2ab0
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA); buf=m.read(WIN); m.close()
mg=buf[HDR:HDR+4]
print("CB7b magic:", mg, "->", "HIT" if mg==b"CB7b" else "MISS")
if mg==b"CB7b":
    t14,c14,v14,t18,c18,v18,lastany=struct.unpack_from("<7I",buf,HDR+0x04)
    def show(name,t,c,v,expect):
        seen = (t==expect)
        print(f"  {name} (0x{expect:08x}): "+("ENABLED  " if seen else "not seen ")+
              (f"caller(r31)={c:#010x}  value={v:#010x} (bit0={v&1})" if seen else ""))
    show("0xee012014", t14,c14,v14, 0xee012014)
    show("0xee012018", t18,c18,v18, 0xee012018)
    print(f"  last-any framer-block target = {lastany:#010x}")
