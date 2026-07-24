#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# snapCKB9 = the framer-clock RCGR RATE/SOURCE (folyt.128b). CKB8 proved the branch CBCR
# (0xee012014/18) is enabled+running IDENTICAL both sides -> not the differentiator. But CKB8 did
# NOT read the RCGR CFG (source-mux + M/N/D divider = the actual RATE). The rate-update method
# 0xf04df244 shows the RCGR base = memw(handle+0), fields at base+0x0 CMD, +0x4 CFG(src[10:8]+div[4:0]
# +MND-mode bit13), +0x8 M, +0xc N, +0x10 D; CBCRs +0x14/+0x18. Base for the framer branch = 0xee012000
# (CBCRs at +0x14/+0x18). All of +0x00..+0x18 are provably touched by the original code -> safe to read.
# CKB9 dumps 0xee012000..+0x18 (7 words) at the 0xee012014 enable match (settled, last-write-wins).
# Same boot-safe hook: splice 0xf04df0c8, replicate enable, leaf exit. Magic 'CB9 '.
#   +0x00 'CB9 '  +0x04 CMD  +0x08 CFG  +0x0c M  +0x10 N  +0x14 D  +0x18 CBCR14  +0x1c CBCR18  +0x20 caller
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os
SRC=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT=f"{FP3_ROOT}/adsp-snapCKB9.mbn"
DELTA=0xf00fd000
SPLICE_VA=0xf04df0c8; SPLICE_FOFF=SPLICE_VA-DELTA; STOCK=struct.pack("<I",0x529f4000)  # jumpr r31
CAVE_VA=0xf064e098;   CAVE_FOFF=CAVE_VA-DELTA
def enc_jump(pc,t):
    d=t-pc; assert d%4==0; s=d//4; assert -(1<<21)<=s<(1<<21)
    imm=s&0x3FFFFF; return ((0b0101100<<25)|(((imm>>13)&0x1FF)<<16)|(0b11<<14)|((imm&0x1FFF)<<1))&0xFFFFFFFF
ASM=r"""
    { r4 = memw(r2+#0) }
    { r4 = or(r4,r3) }
    { memw(r2+#0) = r4 }
    { r1 = ##0xf090fcd4 }
    { r1 = memw(r1+#0) }
    { p0 = cmp.eq(r1,#0x0); if (p0.new) jump:nt .Lret }
    { r1 = add(r1,#0x640) }
    { r5 = ##0x20394243 }                  // 'CB9 '
    { memw(r1+#0x00) = r5 }
    { r5 = ##0xee012014 }                  // framer branch only
    { p0 = cmp.eq(r2,r5); if (!p0.new) jump:nt .Lret }
    { r6 = ##0xee012000 }                  // RCGR base (proved by 0xf04df244)
    { r7 = memw(r6+#0x00) } { memw(r1+#0x04) = r7 }   // CMD
    { r7 = memw(r6+#0x04) } { memw(r1+#0x08) = r7 }   // CFG  (src[10:8]+div[4:0]+MND bit13)
    { r7 = memw(r6+#0x08) } { memw(r1+#0x0c) = r7 }   // M
    { r7 = memw(r6+#0x0c) } { memw(r1+#0x10) = r7 }   // N
    { r7 = memw(r6+#0x10) } { memw(r1+#0x14) = r7 }   // D
    { r7 = memw(r6+#0x14) } { memw(r1+#0x18) = r7 }   // CBCR14
    { r7 = memw(r6+#0x18) } { memw(r1+#0x1c) = r7 }   // CBCR18
    { memw(r1+#0x20) = r31 }
.Lret:
    { jumpr r31 }
"""
here=os.path.dirname(os.path.abspath(__file__))
a=os.path.join(here,"snapCKB9.s");o=os.path.join(here,"snapCKB9.o");b=os.path.join(here,"snapCKB9.bin")
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
