#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# snapCGP = DYNAMIC-CAPTURE of the runtime-dispatched clock poke fn-pointer.
# Static RE (2026-07-12): the real clock-enable dispatch is inside the DAL clock op
# 0xf019f134 (called at f04bfaf4 with r0=handle=ctx+0xe18, r1=#6=enable):
#     f019f1bc:  r2 = memw(r16+#0x48)   ; r16=handle -> r2 = memw(handle+0x48)
#     f019f1c0:  callr r2               ; <<< the runtime-dispatched poke
# So the resolved poke fn-ptr = memw(handle+0x48), handle = memw(ctx+0xe18). Both derefs
# are done by the firmware itself -> safe to replicate in a cave. The poke has ALREADY run
# by the proven splice f04bfba0 (which is AFTER f04bfaf4), and the handle is a persistent
# ctx field -> capture memw(memw(ctx+0xe18)+0x48) there. Disasm that address offline to
# reach the actual memw(base+off) CBCR write (+ any deeper memw(memw(subobj+4)+4)).
# Same proven splice/exit/stash as snapT3 (f04bfba0 -> cave -> f04bfbd8). Magic 'CGP1'.
#   +0x00 'CGP1'  +0x04 handle  +0x08 memw(handle+0x48) = POKE FN-PTR  +0x0c handle+0x34
#   +0x10 handle+0x40  +0x14 handle+0x44  +0x18 handle+0x08  +0x1c handle+0x0c  +0x20 rc
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os
SRC=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT=f"{FP3_ROOT}/adsp-snapCGP.mbn"
SPLICE_VA=0xf04bfba0; SPLICE_FOFF=0x3c2ba0; STOCK=bytes.fromhex("11406070")
CAVE_VA=0xf064e098;   CAVE_FOFF=0x551098
RET_VA=0xf04bfbd8
def enc_jump(pc,t):
    d=t-pc; assert d%4==0; s=d//4; assert -(1<<21)<=s<(1<<21)
    imm=s&0x3FFFFF; return ((0b0101100<<25)|(((imm>>13)&0x1FF)<<16)|(0b11<<14)|((imm&0x1FFF)<<1))&0xFFFFFFFF
ASM=r"""
    { r1 = ##0xf090fcd4 }
    { r1 = memw(r1+#0) }
    { p0 = cmp.eq(r1,#0x0); if (p0.new) jump:nt .Lskip }
    { r1 = add(r1,#0x640) }
    { r2 = ##0x31504743 }              // 'C''G''P''1'
    { memw(r1+#0x00) = r2 }
    { r3 = memw(r16+#0xe18) }          // handle = ctx+0xe18
    { memw(r1+#0x04) = r3 }
    { p0 = cmp.eq(r3,#0x0); if (p0.new) jump:nt .Lrc }
    { r4 = memw(r3+#0x48) }            // ★ POKE FN-PTR = memw(handle+0x48)
    { memw(r1+#0x08) = r4 }
    { r4 = memw(r3+#0x34) }
    { memw(r1+#0x0c) = r4 }
    { r4 = memw(r3+#0x40) }
    { memw(r1+#0x10) = r4 }
    { r4 = memw(r3+#0x44) }
    { memw(r1+#0x14) = r4 }
    { r4 = memw(r3+#0x08) }
    { memw(r1+#0x18) = r4 }
    { r4 = memw(r3+#0x0c) }
    { memw(r1+#0x1c) = r4 }
.Lrc:
    { memw(r1+#0x20) = r0 }            // config-group rc
.Lskip:
    { r17 = r0 }
"""
here=os.path.dirname(os.path.abspath(__file__))
a=os.path.join(here,"snapCGP.s");o=os.path.join(here,"snapCGP.o");b=os.path.join(here,"snapCGP.bin")
open(a,"w").write(ASM)
MC=subprocess.run(["bash","-lc","command -v llvm-mc-21 || command -v llvm-mc"],capture_output=True,text=True).stdout.strip()
OC=subprocess.run(["bash","-lc","command -v llvm-objcopy-21 || command -v llvm-objcopy"],capture_output=True,text=True).stdout.strip()
subprocess.run([MC,"--arch=hexagon","--mcpu=hexagonv60","--filetype=obj",a,"-o",o],check=True)
subprocess.run([OC,"-O","binary","--only-section=.text",o,b],check=True)
body=open(b,"rb").read()
ret=enc_jump(CAVE_VA+len(body),RET_VA)
cave=body+struct.pack("<I",ret)
spl=enc_jump(SPLICE_VA,CAVE_VA)
data=bytearray(open(SRC,"rb").read())
assert bytes(data[SPLICE_FOFF:SPLICE_FOFF+4])==STOCK, "splice stock mismatch"
assert data[CAVE_FOFF:CAVE_FOFF+len(cave)]==b"\x00"*len(cave), "cave region not zero/too small"
data[CAVE_FOFF:CAVE_FOFF+len(cave)]=cave
data[SPLICE_FOFF:SPLICE_FOFF+4]=struct.pack("<I",spl)
open(OUT,"wb").write(data)
print(f"body {len(body)}B cave {len(cave)}B splice={spl:#010x} ret={ret:#010x} -> {OUT}")
