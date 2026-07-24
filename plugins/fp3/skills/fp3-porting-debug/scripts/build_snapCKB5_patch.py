#!/usr/bin/env python3
# snapCKB5 = DISCOVERY of what the accessor 0xf04df0ac actually targets (folyt.123 #1).
# CKB4 (filter r2==0xee00d01c) MISSED -> 0xf04df0ac never writes the framer CBCR. But we can't
# tell "called for other regs" from "never called". This is the same splice (0xf04df0b4,
# r0=desc, r2=memw(desc+12)=target reg), replicates the enable (memw(r2)|=memw(desc+16)), and
# records: a call COUNTER (is it invoked?), the LAST target+mask (what does it write?), and the
# LAST non-page-aligned target (a CBCR/offset-style reg, if any -> the branch-enable candidate).
# Answers: is 0xf04df0ac on the framer path at all, and does it ever touch a branch CBCR?
# Exit = jumpr r31 (leaf). Magic 'CKB5'. pmOS-deployable.
#   +0x30 'CKB5' +0x34 counter +0x38 last target +0x3c last mask +0x40 last CBCR-ish target
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os
SRC=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT=f"{FP3_ROOT}/adsp-snapCKB5.mbn"
DELTA=0xf00fd000
SPLICE_VA=0xf04df0b4; SPLICE_FOFF=SPLICE_VA-DELTA; STOCK=struct.pack("<I",0x5800400a)
CAVE_VA=0xf064e098;   CAVE_FOFF=CAVE_VA-DELTA
def enc_jump(pc,t):
    d=t-pc; assert d%4==0; s=d//4; assert -(1<<21)<=s<(1<<21)
    imm=s&0x3FFFFF; return ((0b0101100<<25)|(((imm>>13)&0x1FF)<<16)|(0b11<<14)|((imm&0x1FFF)<<1))&0xFFFFFFFF
ASM=r"""
    { r3 = memw(r0+#16) }             // mask (replicate)
    { r4 = memw(r2+#0) }
    { r4 = or(r4,r3) }
    { memw(r2+#0) = r4 }              // enable (replicate)
    { r1 = ##0xf090fcd4 }
    { r1 = memw(r1+#0) }
    { p0 = cmp.eq(r1,#0x0); if (p0.new) jump:nt .Lret }
    { r1 = add(r1,#0x640) }
    { r5 = ##0x35424b43 }             // 'CKB5'
    { memw(r1+#0x30) = r5 }
    { r5 = memw(r1+#0x34) }
    { r5 = add(r5,#0x1) }
    { memw(r1+#0x34) = r5 }           // counter++
    { memw(r1+#0x38) = r2 }           // last target reg
    { memw(r1+#0x3c) = r3 }           // last mask
    { r5 = and(r2,#0xfff) }
    { p0 = cmp.eq(r5,#0x0); if (p0.new) jump:nt .Lret }   // page-aligned (RCGR base) -> skip
    { memw(r1+#0x40) = r2 }           // last non-page-aligned (CBCR/offset) target
.Lret:
    { jumpr r31 }
"""
here=os.path.dirname(os.path.abspath(__file__))
a=os.path.join(here,"snapCKB5.s");o=os.path.join(here,"snapCKB5.o");b=os.path.join(here,"snapCKB5.bin")
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
