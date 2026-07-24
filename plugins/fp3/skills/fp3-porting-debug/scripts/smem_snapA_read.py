#!/usr/bin/env python3
# SAFE: single bounded mmap of ONLY 0x86300000. Reads Step-1 (SNPA) stash at
# SMEM item-469 slot#12 +0x40 (in-SMEM 0x2ab0):
# {SNPA, f0191c68-rc, handle, LEAF=memw(handle+0x48), h+0x08, h+0x0c, h+0x40, h+0x44, h+0x18}
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; STASH=0x2ab0
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA)
    buf=m.read(WIN); m.close()
ver=buf[0x2a70:0x2a70+40].split(b"\x00")[0].decode("latin1","replace")
print("ADSP ver slot :", ver)
magic=buf[STASH:STASH+4]
print("magic         :", magic, "->", "SNPA OK" if magic==b"SNPA" else "NOT PRESENT")
names=["f0191c68 rc (r0)","handle (ctx+0xe18)","LEAF memw(handle+0x48)",
       "handle+0x08","handle+0x0c","handle+0x40","handle+0x44","handle+0x18"]
for i,nm in enumerate(names):
    v=struct.unpack_from("<I",buf,STASH+4+i*4)[0]
    print(f"  {nm:24s} = {v:#010x}")
