#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# snapFSS2 = does the framer ENABLE/CONFIG write (FN_B) execute on the DEAD side, and does it latch?
# (staged 2026-07-14, motivated by FSS1/folyt.159: at the capability-timeout instant the dead framer reads
#  +0x600=0 / +0x610=0 -- i.e. NOT enabled -- while the resting AP-alias dump showed 1/7, now known to be an
#  NGD-force-resume artifact. So: is FN_B ever reached naturally on the dead side, and does +0x610 latch to 7
#  right after its store?)
#
# FN_B = 0xf04ca3b0 writes base+0x610=7 via HAL_write(base,id=1,val=7) at 0xf04ca3c8 (returns to 0xf04ca3d8).
# Splice at 0xf04ca3d8 (stock 0x9390f620 = { r0 = memw(r16+#0xec4) }, single-word packet, r16=ctx preserved),
# i.e. IMMEDIATELY after the +0x610=7 store returns. FN_B has only 2 call sites (0xf04cdb4c/0xf04cdbc4, a
# framer state-machine dispatcher) -> could fire >1x, so a FIRST-HIT GUARD bounds the SMEM stash to one write
# and makes the per-hit overhead trivial (count-check + branch) -> NOT the FWT1 hot-HAL rule-11 hazard.
#
# Verdicts:
#  - magic MISS / count=0  -> FN_B NEVER runs naturally on the dead side -> the enable/activate path is
#    DOWNSTREAM of (gated by) the capability handshake that times out -> capability is the UPSTREAM gate
#    (flips folyt.131b "capability subsumed"). Redirect: the capability handshake itself.
#  - count>0, +0x610 reads 0x7 right after -> FN_B runs and the write LATCHES on the dead side -> the enable
#    executes fine; the wall is genuinely below the register file (physical). Then +0x600/FS/FRM_STAT at that
#    instant show whether the rest of the framer responds to the enable.
#  - count>0, +0x610 reads 0 -> the store does NOT latch (xPU/access denial at the framer write) -> decisive
#    access-control finding.
#
# Stash (SMEM +0x640, AP reads PA 0x86302ab0; onboard zeroes 0x60):
#   +0x00 'FSS2' | +0x04 framer base | +0x08 +0x610(latch, exp 7) | +0x0c +0x600 enable | +0x10 +0x604 FS
#   +0x14 +0x404 FRM_STAT | +0x18 +0x804 run | +0x1c ctx+0xec4(FN_B gate field) | +0x20 hit-count
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os
SRC=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT=f"{FP3_ROOT}/adsp-snapFSS2.mbn"
DELTA=0xf00fd000
def foff(va): return va-DELTA
SPLICE_VA=0xf04ca3d8; STOCK=0x9390f620      # { r0 = memw(r16+#0xec4) }  (right after FN_B's +0x610=7 store)
CAVE_VA=0xf064e098
RET_VA=0xf04ca3dc
def enc_jump(pc,t):
    d=t-pc; assert d%4==0; s=d//4; assert -(1<<21)<=s<(1<<21)
    imm=s&0x3FFFFF; return ((0b0101100<<25)|(((imm>>13)&0x1FF)<<16)|(0b11<<14)|((imm&0x1FFF)<<1))&0xFFFFFFFF
ASM=fr"""
    // entry: r16 = ctx (PRESERVE). scratch r2,r3,r4,r5,r6.
    {{ r3 = ##0xf090fcd4 }}
    {{ r3 = memw(r3+#0) }}                                    // SMEM base ptr (ADSP side)
    {{ p0 = cmp.eq(r3,#0x0); if (p0.new) jump:nt .Lrep }}     // null -> replicate + return
    {{ r3 = add(r3,#0x640) }}
    {{ r6 = memw(r3+#0x20) }}                                 // hit-count
    {{ r5 = add(r6,#0x1) }}
    {{ memw(r3+#0x20) = r5 }}                                 // count++
    {{ p0 = cmp.eq(r6,#0x0); if (!p0.new) jump:nt .Lrep }}    // not first hit -> skip stash (bounds SMEM writes)
    {{ r4 = ##0x32535346 }}                                   // 'FSS2'
    {{ memw(r3+#0x00) = r4 }}
    {{ r2 = memw(r16+#0x5c) }}                                // framer base (0xee140000)
    {{ memw(r3+#0x04) = r2 }}
    {{ r4 = memw(r2+#0x610) }}                                // +0x610 right after FN_B store (expect 7 if latched)
    {{ memw(r3+#0x08) = r4 }}
    {{ r4 = memw(r2+#0x600) }}                                // enable
    {{ memw(r3+#0x0c) = r4 }}
    {{ r4 = memw(r2+#0x604) }}                                // FS/SFS/MS
    {{ memw(r3+#0x10) = r4 }}
    {{ r4 = memw(r2+#0x404) }}                                // FRM_STAT
    {{ memw(r3+#0x14) = r4 }}
    {{ r4 = memw(r2+#0x804) }}                                // running
    {{ memw(r3+#0x18) = r4 }}
    {{ r4 = memw(r16+#0xec4) }}                               // ctx+0xec4 (FN_B gate field)
    {{ memw(r3+#0x1c) = r4 }}
.Lrep:
    {{ r0 = memw(r16+#0xec4) }}                               // replicate spliced stock instruction
    {{ r5 = ##{RET_VA:#010x} }}
    {{ jumpr r5 }}
"""
here=os.path.dirname(os.path.abspath(__file__))
a=os.path.join(here,"snapFSS2.s");o=os.path.join(here,"snapFSS2.o");b=os.path.join(here,"snapFSS2.bin")
open(a,"w").write(ASM)
MC=subprocess.run(["bash","-lc","command -v llvm-mc-21 || command -v llvm-mc"],capture_output=True,text=True).stdout.strip()
OC=subprocess.run(["bash","-lc","command -v llvm-objcopy-21 || command -v llvm-objcopy"],capture_output=True,text=True).stdout.strip()
subprocess.run([MC,"--arch=hexagon","--mcpu=hexagonv60","--filetype=obj",a,"-o",o],check=True)
subprocess.run([OC,"-O","binary","--only-section=.text",o,b],check=True)
cave=open(b,"rb").read()
data=bytearray(open(SRC,"rb").read())
got=struct.unpack_from("<I",data,foff(SPLICE_VA))[0]
assert got==STOCK, f"splice stock mismatch: {got:#x} != {STOCK:#x}"
assert data[foff(CAVE_VA):foff(CAVE_VA)+len(cave)]==b"\x00"*len(cave), "cave region not zero"
data[foff(CAVE_VA):foff(CAVE_VA)+len(cave)]=cave
j=enc_jump(SPLICE_VA,CAVE_VA); data[foff(SPLICE_VA):foff(SPLICE_VA)+4]=struct.pack("<I",j)
open(OUT,"wb").write(data)
print(f"cave={len(cave)}B@{CAVE_VA:#x} splice={j:#010x}@{SPLICE_VA:#x} ret={RET_VA:#x} -> {OUT}")
