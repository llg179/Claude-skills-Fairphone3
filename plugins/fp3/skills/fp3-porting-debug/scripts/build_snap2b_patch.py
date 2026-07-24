#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Stage-2b: capture the clock-enable rc with a SIMPLE mid-function splice (no
# conditional replication / trampolines - the fragile part of Stage-2). Splice
# over f04bfba0 (`r17=r0`); cave stashes {SNP4, rc=r0, ctx+0xe14, ctx+0x88,
# ctx+0xdec} then jumps UNCONDITIONALLY to the function's return 0xf04bfbd8
# (skipping only the ULOG error path, which is unreadable anyway).
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os
SRC=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT=f"{FP3_ROOT}/adsp-snap2b.mbn"
SPLICE_VA=0xf04bfba0; SPLICE_FOFF=0x3c2ba0
CAVE_VA=0xf064e098;   CAVE_FOFF=0x551098
RET_VA=0xf04bfbd8     # unconditional return point
def enc_jump(pc,t):
    d=t-pc; assert d%4==0; s=d//4; assert -(1<<21)<=s<(1<<21)
    imm=s&0x3FFFFF; return ((0b0101100<<25)|(((imm>>13)&0x1FF)<<16)|(0b11<<14)|((imm&0x1FFF)<<1))&0xFFFFFFFF
assert enc_jump(0xf04bfc38,0xf01b15d0)==0x599ecccc
ASM=r"""
    { r1 = ##0xf090fcd4 }
    { r1 = memw(r1+#0) }
    { p0 = cmp.eq(r1,#0x0); if (p0.new) jump:nt .Lskip }
    { r1 = add(r1,#0x640) }
    { r2 = ##0x34504e53 }
    { memw(r1+#0x00) = r2 }
    { memw(r1+#0x04) = r0 }
    { r2 = memw(r16+#0xe14) }
    { memw(r1+#0x08) = r2 }
    { r2 = memw(r16+#0x88) }
    { memw(r1+#0x0c) = r2 }
    { r2 = memw(r16+#0xdec) }
    { memw(r1+#0x10) = r2 }
.Lskip:
    { r17 = r0 }
"""
tmp="/tmp/claude-1000/-mnt-1TB-Fp3-Sailfish/dd323baf-a481-4cdd-8106-416f327bbc92/scratchpad"
a=os.path.join(tmp,"snap2b.s");o=os.path.join(tmp,"snap2b.o");b=os.path.join(tmp,"snap2b.bin")
open(a,"w").write(ASM)
subprocess.run(["llvm-mc-21","--arch=hexagon","--mcpu=hexagonv60","--filetype=obj",a,"-o",o],check=True)
subprocess.run(["llvm-objcopy-21","-O","binary","--only-section=.text",o,b],check=True)
body=open(b,"rb").read()
ret=enc_jump(CAVE_VA+len(body),RET_VA)
cave=body+struct.pack("<I",ret)
spl=enc_jump(SPLICE_VA,CAVE_VA)
data=bytearray(open(SRC,"rb").read())
assert data[CAVE_FOFF:CAVE_FOFF+len(cave)]==b"\x00"*len(cave)
assert bytes(data[SPLICE_FOFF:SPLICE_FOFF+4])==bytes.fromhex("11406070")
data[CAVE_FOFF:CAVE_FOFF+len(cave)]=cave
data[SPLICE_FOFF:SPLICE_FOFF+4]=struct.pack("<I",spl)
open(OUT,"wb").write(data); open(os.path.join(tmp,"cave2b.bin"),"wb").write(cave)
print(f"body {len(body)}B cave {len(cave)}B splice={spl:#010x} ret={ret:#010x} wrote {OUT}")
