#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Reads the FSS2 trace: does FN_B (framer +0x610=7 enable/config write) execute on the DEAD side & latch?
# SMEM PA 0x86300000 + 0x2ab0. Layout: 'FSS2' | base | +0x610 | +0x600 | +0x604 | +0x404 | +0x804 | ec4 | count
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; HDR=0x2ab0
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA); buf=m.read(WIN); m.close()
mg=buf[HDR:HDR+4]
print("FSS2 magic:", mg, "->", "HIT" if mg==b"FSS2" else "MISS")
if mg!=b"FSS2":
    print("  MISS -> FN_B (0xf04ca3b0, the +0x610=7 enable/config write) NEVER ran naturally on the dead side.")
    print("     => the enable/activate path is DOWNSTREAM of / gated by the capability handshake that times out.")
    print("     => capability is the UPSTREAM gate (revises folyt.131b). Redirect: the capability handshake itself.")
else:
    (base,r610,r600,r604,r404,r804,ec4,cnt)=struct.unpack_from("<8I",buf,HDR+4)
    print(f"  hit-count            = {cnt}   (times FN_B's +0x610=7 store executed this SSR init)")
    print(f"  framer base (ctx+5c) = {base:#010x}   <- expect 0xee140000")
    print(f"  +0x610 (just written)= {r610:#010x}   <- 0x7 => store LATCHED; 0x0 => did NOT latch (xPU/access denial!)")
    print(f"  +0x600 enable        = {r600:#010x}")
    print(f"  +0x604 FS/SFS/MS     = {r604:#010x}")
    print(f"  +0x404 FRM_STAT      = {r404:#010x}")
    print(f"  +0x804 running-bit   = {r804:#010x}")
    print(f"  ctx+0xec4 (gate)     = {ec4:#010x}")
    print()
    print("  INTERPRETATION:")
    if base!=0xee140000:
        print("  ?? framer base unexpected -> ctx drift; treat with caution.")
    elif r610==0x7:
        print("  == FN_B RUNS and +0x610=7 LATCHES on the dead side. The enable/config write executes fine.")
        print("     So the wall is genuinely below the register file (physical frame start), NOT a skipped/denied")
        print("     enable write. Compare +0x600/FS/FRM_STAT here vs the FSS1 timeout snapshot to see whether the")
        print("     framer clears the enable again between activate and the capability wait.")
    elif r610==0x0:
        print("  ** FN_B runs but +0x610 does NOT latch (reads 0 right after the store) -> the framer register")
        print("     write is being DROPPED (xPU/access-control denial on the ADSP's framer master writes).")
        print("     DECISIVE access-control finding -> that is the PIL-vs-PAS precondition.")
    else:
        print(f"  ?? +0x610 = {r610:#x} (unexpected) -> partial/other; inspect.")
