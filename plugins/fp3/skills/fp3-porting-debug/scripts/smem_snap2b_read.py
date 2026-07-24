#!/usr/bin/env python3
# SAFE: single bounded mmap of ONLY 0x86300000. Reads the Stage-2b (SNP4) stash
# at SMEM item-469 slot#12 +0x40 (in-SMEM 0x2ab0): {SNP4, rc, ctx+0xe14, ctx+0x88, ctx+0xdec}
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; STASH=0x2ab0
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA)
    buf=m.read(WIN); m.close()
ver=buf[0x2a70:0x2a70+40].split(b"\x00")[0].decode("latin1","replace")
print("ADSP ver slot :", ver)
magic=buf[STASH:STASH+4]
print("magic         :", magic, "->", "SNP4 OK" if magic==b"SNP4" else "NOT PRESENT")
names=["rc (r0)","ctx+0xe14 clock_handle","ctx+0x88","ctx+0xdec"]
for i,nm in enumerate(names):
    v=struct.unpack_from("<I",buf,STASH+4+i*4)[0]
    print(f"  {nm:24s} = {v:#010x} ({struct.unpack('<i',struct.pack('<I',v))[0]})")
