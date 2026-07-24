#!/usr/bin/env python3
# Reads the UT-side (WORKING) FSS2 cave: does FN_B (framer ENABLE, +0x610=7) execute on the PIL/working side,
# and what does the framer read right after? Symmetric to the DEAD-side FSS2 (folyt.160 = MISS/count=0).
# SMEM PA 0x86300000 + 0x2ab0. On UT the STRICT_DEVMEM path is OFF, so /dev/mem RAM reads work (SMEM is DDR).
# Layout (build_snapFSS2_patch.py): +00 'FSS2' | +04 base | +08 +0x610 | +0c +0x600 | +10 +0x604 |
#   +14 +0x404 | +18 +0x804 | +1c ctx+0xec4(gate) | +20 hit-count
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; HDR=0x2ab0
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA); buf=m.read(WIN); m.close()
mg=buf[HDR:HDR+4]
print("UT-FSS2 magic:", mg, "->", "HIT" if mg==b"FSS2" else "MISS")
if mg==b"FSS2":
    (base,r610,r600,r604,r404,r804,gate,cnt)=struct.unpack_from("<8I",buf,HDR+4)
    print(f"  reached-count (FN_B) = {cnt}")
    print(f"  framer base          = {base:#010x}   <- expect 0xee140000")
    print(f"  +0x610 control(latch)= {r610:#010x}   <- expect 0x7 if FN_B's store latched")
    print(f"  +0x600 ENABLE        = {r600:#010x}")
    print(f"  +0x604 FS/SFS/MS     = {r604:#010x}")
    print(f"  +0x404 FRM_STAT      = {r404:#010x}")
    print(f"  +0x804 running-bit   = {r804:#010x}")
    print(f"  ctx+0xec4 (gate)     = {gate:#010x}")
    print()
    print("  DIFFERENTIAL vs DEAD side (folyt.160 = MISS, count=0, FN_B never ran):")
    print("  ** FN_B RUNS on the working side (this HIT) but NOT on the dead side.")
    print("     => the framer-ENABLE path is reached under PIL, skipped under PAS.")
    print("     => the divergence is UPSTREAM of FN_B: the dispatcher 0xf04cda24 / its gate 0xf04c2480")
    print("        (memb(ctx+0x58)==0) or a ctx state field decides differently. THAT is the next two-sided cave.")
else:
    print("  ** UNEXPECTED: FN_B did NOT run on the working side either. Then FN_B is not the enable path that")
    print("     frames; the real enable is elsewhere. Re-anchor on the codec-enumeration (laddr 0xc7/0xc8) path.")
