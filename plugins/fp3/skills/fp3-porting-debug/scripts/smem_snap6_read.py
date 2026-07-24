#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# SAFE: single bounded mmap of ONLY 0x86300000. Stage-6 (SNP6) RING @0x2ab0:
# header {SNP6, count}; then ring[4] x {id(ctx+0xe14), rc(f0191c68), gate(ctx+0x74)}
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; STASH=0x2ab0
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA)
    buf=m.read(WIN); m.close()
print("ADSP ver slot :", buf[0x2a70:0x2a70+40].split(b"\x00")[0].decode("latin1","replace"))
magic=buf[STASH:STASH+4]
print("magic         :", magic, "->", "SNP6 OK" if magic==b"SNP6" else "NOT PRESENT")
count=struct.unpack_from("<I",buf,STASH+4)[0]
print("count (total firings) :", count)
n=min(count,4)
for i in range(n):
    base=STASH+8+i*12
    idv,rc,gate=struct.unpack_from("<III",buf,base)
    print(f"  entry[{i}] id(ctx+0xe14)={idv:#010x}  rc={rc:#010x} ({rc if rc<0x80000000 else rc-0x100000000})  gate(ctx+0x74)={gate:#x}")
