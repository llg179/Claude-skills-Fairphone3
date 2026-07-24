#!/usr/bin/env python3
# SAFE: single bounded mmap of ONLY 0x86300000. Stage-5 (SNP5) stash @0x2ab0:
# {SNP5, rc, handle, reg_addr, *reg (CBCR), ctx+0xe14}
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; STASH=0x2ab0
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA)
    buf=m.read(WIN); m.close()
print("ADSP ver slot :", buf[0x2a70:0x2a70+40].split(b"\x00")[0].decode("latin1","replace"))
magic=buf[STASH:STASH+4]
print("magic         :", magic, "->", "SNP5 OK" if magic==b"SNP5" else "NOT PRESENT")
names=["rc (r0)","handle (ctx+0xe18)","reg_addr","*reg (CBCR value)","ctx+0xe14"]
for i,nm in enumerate(names):
    v=struct.unpack_from("<I",buf,STASH+4+i*4)[0]
    print(f"  {nm:22s} = {v:#010x}")
