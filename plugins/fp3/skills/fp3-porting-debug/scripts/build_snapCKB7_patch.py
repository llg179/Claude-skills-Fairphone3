#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# snapCKB7 = CBCR branch-ENABLE capture, CORRECTED (folyt.127).
# ★ CKB4/CKB5 (folyt.123-124) spliced 0xf04df0b4 and concluded "0xf04df0ac never runs for the
# framer". BUG: the set-bit fn 0xf04df0ac has TWO paths that only converge at 0xf04df0c8:
#   - selector (desc+0xc) != 0 : 0xf04df0ac -> 0xf04df0b4 -> 0xf04df0c8, target = memw(desc+0xc)
#   - selector == 0            : 0xf04df0ac -> 0xf04df0bc -> 0xf04df0c8, target = memw(desc+0x4), val=1
# 0xf04df0b4 is ONLY the selector!=0 path -> CKB4/5 were path-blind (false negative).
# The universal branch-ENABLE store is the packet at 0xf04df0c8 { jumpr r31 ; memw(r2)|=r3 }.
# Splice word0 (jumpr r31 = 0x529f4000) with a jump-to-cave; the parallel store still executes
# (enable NOT broken), then capture and jumpr r31 back. r0-r5 are volatile (leaf, ABI) -> free
# scratch. Filter r2==0xee00d01c = the framer branch CBCR (folyt.122, cross-verified). Also record
# the total call-count + a 4-slot ring of ALL enable targets (discovery: what else gets enabled,
# and the framer addr even if the runtime map differs on UT). Capture r31 = the CALLER (who enables
# the framer branch) -> the trace lead for the gating condition. Leaf exit (jumpr r31). Magic 'CKB7'.
#   +0x00 'CKB7'  +0x04 total-enable-count  +0x08 last target
#   +0x0c framer-hit-count  +0x14 framer caller(r31)  +0x18 framer value(r3)
#   +0x20..0x2c ring of last-4 targets (idx at +0x1c)
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os
SRC=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT=f"{FP3_ROOT}/adsp-snapCKB7.mbn"
DELTA=0xf00fd000
SPLICE_VA=0xf04df0c8; SPLICE_FOFF=SPLICE_VA-DELTA; STOCK=struct.pack("<I",0x529f4000)  # jumpr r31
CAVE_VA=0xf064e098;   CAVE_FOFF=CAVE_VA-DELTA
def enc_jump(pc,t):
    d=t-pc; assert d%4==0; s=d//4; assert -(1<<21)<=s<(1<<21)
    imm=s&0x3FFFFF; return ((0b0101100<<25)|(((imm>>13)&0x1FF)<<16)|(0b11<<14)|((imm&0x1FFF)<<1))&0xFFFFFFFF
ASM=r"""
    // r2=target reg, r3=value valid. The original packet's store did NOT run (our jump word became
    // its own packet, parse=11), so REPLICATE the enable here first, else every clock enable breaks.
    { r4 = memw(r2+#0) }
    { r4 = or(r4,r3) }
    { memw(r2+#0) = r4 }                   // replicate memw(target) |= value  (the actual enable)
    // r31 = caller return addr. r0-r5 volatile -> free scratch.
    { r1 = ##0xf090fcd4 }
    { r1 = memw(r1+#0) }
    { p0 = cmp.eq(r1,#0x0); if (p0.new) jump:nt .Lret }   // no stash yet -> just return
    { r1 = add(r1,#0x640) }
    { r5 = ##0x37424b43 }                 // 'CKB7'
    { memw(r1+#0x00) = r5 }
    { r5 = memw(r1+#0x04) }
    { r5 = add(r5,#0x1) }
    { memw(r1+#0x04) = r5 }                // total enable-store count++
    { memw(r1+#0x08) = r2 }                // last target (any)
    // ring of last-4 targets
    { r4 = memw(r1+#0x1c) }                // ring idx (0..3)
    { r4 = and(r4,#0x3) }
    { r0 = asl(r4,#0x2) }
    { r0 = add(r0,#0x20) }                 // +0x20 + idx*4
    { memw(r1+r0<<#0) = r2 }               // ring[idx] = target
    { r4 = add(r4,#0x1) }
    { memw(r1+#0x1c) = r4 }                // idx++
    // framer filter
    { r5 = ##0xee00d01c }
    { p0 = cmp.eq(r2,r5); if (!p0.new) jump:nt .Lret }    // not framer CBCR -> return
    { r5 = memw(r1+#0x0c) }
    { r5 = add(r5,#0x1) }
    { memw(r1+#0x0c) = r5 }                // framer-hit count++
    { memw(r1+#0x14) = r31 }               // ★ caller of the framer branch-enable
    { memw(r1+#0x18) = r3 }                // value applied (should have bit0)
.Lret:
    { jumpr r31 }
"""
here=os.path.dirname(os.path.abspath(__file__))
a=os.path.join(here,"snapCKB7.s");o=os.path.join(here,"snapCKB7.o");b=os.path.join(here,"snapCKB7.bin")
open(a,"w").write(ASM)
MC=subprocess.run(["bash","-lc","command -v llvm-mc-21 || command -v llvm-mc"],capture_output=True,text=True).stdout.strip()
OC=subprocess.run(["bash","-lc","command -v llvm-objcopy-21 || command -v llvm-objcopy"],capture_output=True,text=True).stdout.strip()
subprocess.run([MC,"--arch=hexagon","--mcpu=hexagonv60","--filetype=obj",a,"-o",o],check=True)
subprocess.run([OC,"-O","binary","--only-section=.text",o,b],check=True)
cave=open(b,"rb").read()
spl=enc_jump(SPLICE_VA,CAVE_VA)
data=bytearray(open(SRC,"rb").read())
assert bytes(data[SPLICE_FOFF:SPLICE_FOFF+4])==STOCK, "splice stock mismatch (0xf04df0c8 != jumpr r31)"
assert data[CAVE_FOFF:CAVE_FOFF+len(cave)]==b"\x00"*len(cave), "cave region not zero/too small"
data[CAVE_FOFF:CAVE_FOFF+len(cave)]=cave
data[SPLICE_FOFF:SPLICE_FOFF+4]=struct.pack("<I",spl)
open(OUT,"wb").write(data)
print(f"cave {len(cave)}B splice={spl:#010x} @0xf04df0c8 (parallel store preserved, exit=jumpr r31) -> {OUT}")
