#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# snapCKB8 = confirm the PHYSICAL wall after B (folyt.127c). B proved the framer-branch
# enable memw(0xee012014)|=1 is BYTE-IDENTICAL working(UT) vs dead(pmOS). CKB8 reads back,
# right after the enable, the CBCR CLK_OFF (bit31 of 0xee012014/18) via a BOUNDED poll, plus
# the root RCGR ROOT_OFF (bit31 of 0xee012000). Same boot-safe hook as CKB7b: splice 0xf04df0c8,
# replicate the enable store, leaf exit. Magic 'CB8 '.
#   Both readbacks are safe: CBCR is in the always-clocked clock-controller (this is exactly how
#   clk_branch2 polls); 0xee012000 is the RCGR the original bring-up already programs.
# PASS/FAIL: UT -> CLK_OFF clears (bit31->0, iters-remaining>0). pmOS -> if CLK_OFF stays 1
#   (iters-remaining==0) the branch is enabled but NOT RUNNING; then ROOT_OFF (0xee012000 bit31)
#   splits it: ROOT_OFF=1 -> source PLL/root not supplying (the parent wall); ROOT_OFF=0 -> root
#   spins but branch dead (branch-local gate).
# Capture layout (SMEM stash + 0x640):
#   +0x00 'CB8 '
#   t14: +0x04 tgt  +0x08 caller  +0x0c CBCR-final  +0x10 iters-remaining  +0x14 root(0xee012000)
#   t18: +0x18 tgt  +0x1c caller  +0x20 CBCR-final  +0x24 iters-remaining  +0x2c root
#   +0x28 last-any-framer-block target
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os
SRC=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT=f"{FP3_ROOT}/adsp-snapCKB8.mbn"
DELTA=0xf00fd000
SPLICE_VA=0xf04df0c8; SPLICE_FOFF=SPLICE_VA-DELTA; STOCK=struct.pack("<I",0x529f4000)  # jumpr r31
CAVE_VA=0xf064e098;   CAVE_FOFF=CAVE_VA-DELTA
def enc_jump(pc,t):
    d=t-pc; assert d%4==0; s=d//4; assert -(1<<21)<=s<(1<<21)
    imm=s&0x3FFFFF; return ((0b0101100<<25)|(((imm>>13)&0x1FF)<<16)|(0b11<<14)|((imm&0x1FFF)<<1))&0xFFFFFFFF
ASM=r"""
    // r2=target, r3=value, r31=caller. Original store did not run -> replicate the enable.
    { r4 = memw(r2+#0) }
    { r4 = or(r4,r3) }
    { memw(r2+#0) = r4 }
    { r1 = ##0xf090fcd4 }
    { r1 = memw(r1+#0) }
    { p0 = cmp.eq(r1,#0x0); if (p0.new) jump:nt .Lret }
    { r1 = add(r1,#0x640) }
    { r5 = ##0x20384243 }                  // 'CB8 '
    { memw(r1+#0x00) = r5 }
    // framer-block range gate: 0xee012000 <= r2 < 0xee013000
    { r5 = ##0xee012000 }
    { p0 = cmp.gtu(r5,r2); if (p0.new) jump:nt .Lret }
    { r5 = ##0xee013000 }
    { p0 = cmp.gtu(r5,r2); if (!p0.new) jump:nt .Lret }
    { memw(r1+#0x28) = r2 }                 // last-any-framer-block target
    // exact 0xee012014 ?
    { r5 = ##0xee012014 }
    { p0 = cmp.eq(r2,r5); if (!p0.new) jump:nt .L18 }
    { r6 = ##0x00080000 }                   // bounded K (~1-2ms)
.Lp14:
    { r7 = memw(r2+#0) }
    { p1 = tstbit(r7,#31) }                 // CLK_OFF
    { if (!p1) jump:nt .Ld14 }              // cleared -> running
    { r6 = add(r6,#-1) }
    { p1 = cmp.eq(r6,#0); if (!p1.new) jump:nt .Lp14 }
.Ld14:
    { r7 = memw(r2+#0) }
    { memw(r1+#0x04) = r2 } { memw(r1+#0x08) = r31 }
    { memw(r1+#0x0c) = r7 } { memw(r1+#0x10) = r6 }
    { r5 = ##0xee012000 }
    { r7 = memw(r5+#0) }
    { memw(r1+#0x14) = r7 }
    { jump .Lret }
.L18:
    { r5 = ##0xee012018 }
    { p0 = cmp.eq(r2,r5); if (!p0.new) jump:nt .Lret }
    { r6 = ##0x00080000 }
.Lp18:
    { r7 = memw(r2+#0) }
    { p1 = tstbit(r7,#31) }
    { if (!p1) jump:nt .Ld18 }
    { r6 = add(r6,#-1) }
    { p1 = cmp.eq(r6,#0); if (!p1.new) jump:nt .Lp18 }
.Ld18:
    { r7 = memw(r2+#0) }
    { memw(r1+#0x18) = r2 } { memw(r1+#0x1c) = r31 }
    { memw(r1+#0x20) = r7 } { memw(r1+#0x24) = r6 }
    { r5 = ##0xee012000 }
    { r7 = memw(r5+#0) }
    { memw(r1+#0x2c) = r7 }
.Lret:
    { jumpr r31 }
"""
here=os.path.dirname(os.path.abspath(__file__))
a=os.path.join(here,"snapCKB8.s");o=os.path.join(here,"snapCKB8.o");b=os.path.join(here,"snapCKB8.bin")
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
