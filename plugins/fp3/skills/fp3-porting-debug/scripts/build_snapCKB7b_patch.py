#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# snapCKB7b = pin the framer-block branch-ENABLE caller+value (folyt.127, after CKB7).
# CKB7 (UT/golden) proved the enable primitive 0xf04df0c8 RUNS (34 stores) and the framer-block
# targets are 0xee012014 & 0xee012018 (= RCGR base 0xee012000 +0x14/+0x18; clock id 0x12014 -> +0x14),
# NOT 0xee00d01c (that never matched -> 0xee00d01c is a DIFFERENT clock, mis-ID'd by CKB3/CKB6).
# Now capture, per exact target, the CALLER(r31) + VALUE(r3) for 0xee012014 and 0xee012018.
# last-write-wins (no zero-init dependency; SMEM stash is not zeroed). Same boot-safe hook: splice
# 0xf04df0c8, replicate the enable store, leaf exit. Magic 'CB7b'.
#   +0x00 'CB7b'  +0x04 t14 tgt +0x08 t14 caller +0x0c t14 value
#                 +0x10 t18 tgt +0x14 t18 caller +0x18 t18 value  +0x1c last-any-framer-block tgt
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os
SRC=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT=f"{FP3_ROOT}/adsp-snapCKB7b.mbn"
DELTA=0xf00fd000
SPLICE_VA=0xf04df0c8; SPLICE_FOFF=SPLICE_VA-DELTA; STOCK=struct.pack("<I",0x529f4000)  # jumpr r31
CAVE_VA=0xf064e098;   CAVE_FOFF=CAVE_VA-DELTA
def enc_jump(pc,t):
    d=t-pc; assert d%4==0; s=d//4; assert -(1<<21)<=s<(1<<21)
    imm=s&0x3FFFFF; return ((0b0101100<<25)|(((imm>>13)&0x1FF)<<16)|(0b11<<14)|((imm&0x1FFF)<<1))&0xFFFFFFFF
ASM=r"""
    // r2=target, r3=value valid; original store did not run -> replicate the enable first.
    { r4 = memw(r2+#0) }
    { r4 = or(r4,r3) }
    { memw(r2+#0) = r4 }
    { r1 = ##0xf090fcd4 }
    { r1 = memw(r1+#0) }
    { p0 = cmp.eq(r1,#0x0); if (p0.new) jump:nt .Lret }
    { r1 = add(r1,#0x640) }
    { r5 = ##0x62374243 }                  // 'CB7b'
    { memw(r1+#0x00) = r5 }
    // framer-block range? 0xee012000 <= r2 < 0xee013000
    { r5 = ##0xee012000 }
    { p0 = cmp.gtu(r5,r2); if (p0.new) jump:nt .Lret }   // r2 < 0xee012000 -> skip
    { r5 = ##0xee013000 }
    { p0 = cmp.gtu(r5,r2); if (!p0.new) jump:nt .Lret }  // r2 >= 0xee013000 -> skip
    { memw(r1+#0x1c) = r2 }                 // last-any-framer-block target
    // exact 0xee012014 ?
    { r5 = ##0xee012014 }
    { p0 = cmp.eq(r2,r5); if (!p0.new) jump:nt .L18 }
    { memw(r1+#0x04) = r2 } { memw(r1+#0x08) = r31 } { memw(r1+#0x0c) = r3 }
    { jump .Lret }
.L18:
    { r5 = ##0xee012018 }
    { p0 = cmp.eq(r2,r5); if (!p0.new) jump:nt .Lret }
    { memw(r1+#0x10) = r2 } { memw(r1+#0x14) = r31 } { memw(r1+#0x18) = r3 }
.Lret:
    { jumpr r31 }
"""
here=os.path.dirname(os.path.abspath(__file__))
a=os.path.join(here,"snapCKB7b.s");o=os.path.join(here,"snapCKB7b.o");b=os.path.join(here,"snapCKB7b.bin")
open(a,"w").write(ASM)
MC=subprocess.run(["bash","-lc","command -v llvm-mc-21 || command -v llvm-mc"],capture_output=True,text=True).stdout.strip()
OC=subprocess.run(["bash","-lc","command -v llvm-objcopy-21 || command -v llvm-objcopy"],capture_output=True,text=True).stdout.strip()
subprocess.run([MC,"--arch=hexagon","--mcpu=hexagonv60","--filetype=obj",a,"-o",o],check=True)
subprocess.run([OC,"-O","binary","--only-section=.text",o,b],check=True)
cave=open(b,"rb").read()
spl=enc_jump(SPLICE_VA,CAVE_VA)
data=bytearray(open(SRC,"rb").read())
assert bytes(data[SPLICE_FOFF:SPLICE_FOFF+4])==STOCK, "splice stock mismatch"
assert data[CAVE_FOFF:CAVE_FOFF+len(cave)]==b"\x00"*len(cave), "cave region not zero/too small"
data[CAVE_FOFF:CAVE_FOFF+len(cave)]=cave
data[SPLICE_FOFF:SPLICE_FOFF+4]=struct.pack("<I",spl)
open(OUT,"wb").write(data)
print(f"cave {len(cave)}B splice={spl:#010x} @0xf04df0c8 -> {OUT}")
