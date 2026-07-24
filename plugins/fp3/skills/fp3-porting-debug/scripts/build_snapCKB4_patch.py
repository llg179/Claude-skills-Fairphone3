#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# snapCKB4 = POST-ENABLE framer CBCR capture (folyt.122 next: does the branch clock turn on?).
# folyt.122: framer branch CBCR = 0xee00d01c; at the RCGR-enable splice (pkt5, pre-branch-enable)
# it read 0x80000000 (ENABLE=0, CLK_OFF=1). The CBCR ENABLE itself is method 0xf04df0ac:
#   r2=memw(desc+12)=CBCR addr; r3=memw(desc+16)=mask; memw(r2+0) |= r3  (0xf04df0ac->0b4->0c8).
# This splices 0xf04df0b4 (r0=desc, r2=CBCR live), REPLICATES the enable, then RE-READS the CBCR
# = the POST-ENABLE state, filtered to the framer CBCR r2==0xee00d01c (a PROVEN safe addr).
# If post-enable CLK_OFF(bit31) stays 1 => branch enabled but clock not running (parent RCG not
# feeding) = the framer clock chain is dead at the branch (UT works => UT must show it running,
# so a dead-side CLK_OFF=1 here is decisive by logical control). Exit = jumpr r31 (returns to the
# caller) -> no trampoline. Magic 'CKB4'. pmOS-deployable (no UT needed).
#   +0x30 'CKB4' +0x34 CBCR addr +0x38 ★post-enable CBCR +0x3c mask
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os
SRC=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT=f"{FP3_ROOT}/adsp-snapCKB4.mbn"
DELTA=0xf00fd000
SPLICE_VA=0xf04df0b4; SPLICE_FOFF=SPLICE_VA-DELTA; STOCK=struct.pack("<I",0x5800400a)
CAVE_VA=0xf064e098;   CAVE_FOFF=CAVE_VA-DELTA
def enc_jump(pc,t):
    d=t-pc; assert d%4==0; s=d//4; assert -(1<<21)<=s<(1<<21)
    imm=s&0x3FFFFF; return ((0b0101100<<25)|(((imm>>13)&0x1FF)<<16)|(0b11<<14)|((imm&0x1FFF)<<1))&0xFFFFFFFF
ASM=r"""
    { r3 = memw(r0+#16) }             // mask = memw(desc+16)  (replicate)
    { r4 = memw(r2+#0) }              // CBCR current (r2=memw(desc+12)=CBCR addr, from pkt @0xf04df0ac)
    { r4 = or(r4,r3) }                // set enable bit
    { memw(r2+#0) = r4 }              // write back = the ENABLE (replicated)
    { r4 = memw(r2+#0) }              // ★ RE-READ post-enable CBCR
    { p0 = cmp.eq(r2,##0xee00d01c); if (!p0.new) jump:nt .Lret }   // only the framer CBCR
    { r1 = ##0xf090fcd4 }
    { r1 = memw(r1+#0) }
    { p0 = cmp.eq(r1,#0x0); if (p0.new) jump:nt .Lret }
    { r1 = add(r1,#0x640) }
    { r5 = ##0x34424b43 }             // 'CKB4'
    { memw(r1+#0x30) = r5 }
    { memw(r1+#0x34) = r2 }           // CBCR addr
    { memw(r1+#0x38) = r4 }           // ★ post-enable CBCR value
    { memw(r1+#0x3c) = r3 }           // mask
.Lret:
    { jumpr r31 }
"""
here=os.path.dirname(os.path.abspath(__file__))
a=os.path.join(here,"snapCKB4.s");o=os.path.join(here,"snapCKB4.o");b=os.path.join(here,"snapCKB4.bin")
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
print(f"cave {len(cave)}B splice={spl:#010x} (exit=jumpr r31) -> {OUT}")
