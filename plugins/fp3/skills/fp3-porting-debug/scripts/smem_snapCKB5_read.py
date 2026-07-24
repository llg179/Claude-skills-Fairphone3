#!/usr/bin/env python3
# snapCKB5 reader: DISCOVERY of what accessor 0xf04df0ac targets. SAFE SMEM mmap.
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; HDR=0x2ab0
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA); buf=m.read(WIN); m.close()
mg=buf[HDR+0x30:HDR+0x34]
print("CKB5 magic:", mg, "->", "0xf04df0ac IS invoked" if mg==b"CKB5" else "NOT invoked at all (0xf04df0ac never runs)")
if mg==b"CKB5":
    cnt,last,mask,cbcrish=struct.unpack_from("<4I",buf,HDR+0x34)
    print(f"  call counter        = {cnt}")
    print(f"  last target reg     = {last:#010x}   mask={mask:#x}   (target&0xfff={last&0xfff:#x})")
    print(f"  last CBCR-ish target = {cbcrish:#010x}   " + ("(a non-page-aligned/branch reg WAS written)" if cbcrish else "(none: only page-aligned RCGR bases written -> 0xf04df0ac = RCGR op, not CBCR)"))
