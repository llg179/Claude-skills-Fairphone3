#!/usr/bin/env python3
# snapCKB7 reader: CBCR branch-ENABLE capture (corrected path, folyt.127).
# Answers: does the framer branch-CBCR (0xee00d01c) get ENABLE-set at all, from where, and
# what else gets enabled. SAFE bounded SMEM mmap.
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; HDR=0x2ab0
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA); buf=m.read(WIN); m.close()
mg=buf[HDR:HDR+4]
print("CKB7 magic:", mg, "->", "HIT (a branch-enable store ran)" if mg==b"CKB7" else "MISS (0xf04df0c8 never executed)")
if mg==b"CKB7":
    total,last=struct.unpack_from("<2I",buf,HDR+0x04)
    fhit,=struct.unpack_from("<I",buf,HDR+0x0c)
    caller,val=struct.unpack_from("<2I",buf,HDR+0x14)
    idx,=struct.unpack_from("<I",buf,HDR+0x1c)
    ring=struct.unpack_from("<4I",buf,HDR+0x20)
    print(f"  total branch-enable stores = {total}")
    print(f"  last target reg            = {last:#010x}")
    print(f"  ring of last-4 targets     = " + ", ".join(f"{x:#010x}" for x in ring) + f"  (next idx={idx&3})")
    print(f"  ★ framer CBCR (0xee00d01c) enable-hits = {fhit}")
    if fhit:
        print(f"    ★★ framer branch WAS enabled -> caller(r31) = {caller:#010x}   value applied = {val:#010x} (bit0={val&1})")
    else:
        print("    framer CBCR 0xee00d01c NEVER enable-set on this side (check ring for a 0xee00dxxx-range addr = map differs)")
