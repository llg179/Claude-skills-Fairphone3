#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# SAFE: single bounded mmap of ONLY 0x86300000. Stage-8 (SNP8) @0x2ab0:
# {SNP8, id, rc} + input-array[4x{type,sub_ptr}] from 0xf0c85430 + output[4] from 0xf0c85468
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; STASH=0x2ab0; IN=0xf0c85430; OUT=0xf0c85468
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA)
    buf=m.read(WIN); m.close()
print("ADSP ver :", buf[0x2a70:0x2a70+40].split(b"\x00")[0].decode("latin1","replace"))
print("magic    :", buf[STASH:STASH+4], "->", "SNP8 OK" if buf[STASH:STASH+4]==b"SNP8" else "MISSING")
idv,rc=struct.unpack_from("<II",buf,STASH+4)
print("id=%#06x  rc=%#010x"%(idv,rc))
print("input-array @%#010x (4 entries {type, sub_ptr}):"%IN)
for i in range(4):
    t,p=struct.unpack_from("<II",buf,STASH+0x0c+i*8)
    print("  entry[%d] @%#010x  type=%#010x  sub_ptr=%#010x"%(i,IN+i*8,t,p))
print("output-array @%#010x:"%OUT)
for i in range(4):
    v=struct.unpack_from("<I",buf,STASH+0x2c+i*4)[0]
    print("  out[%d] @%#010x = %#010x"%(i,OUT+i*4,v))
