#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# SN97 (folyt.97): resolve the RUNTIME-DISPATCHED physical framer-clock poke leaf.
# Static RE bottomed out: f01a12bc does `callr memw(memw(subobj+4)+4)` where subobj+4 is a
# runtime-registered driver node (fn addr set at init, not in rodata/text). Walk it dynamically.
# Reuse the PROVEN-SAFE T3 splice at f04bfba0 (stock 11406070 = `r17=r0`, packet
# `{r17=r0; if(r17==0) jump f04bfbd8}`; rc is always 0 here so an unconditional return to
# f04bfbd8 = the epilogue is correct — same trick as SNT3). r16 = slim ctx at this site.
# Cave stashes handle->subobj->drivernode->resolved_fn (THE LEAF) + neighbours to SMEM.
# All reads are null-guarded ctx/handle derefs the code itself uses; NO cave-issued MMIO (rule 4).
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os
SRC=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT=f"{FP3_ROOT}/adsp-snapH97.mbn"
SPLICE_VA=0xf04bfba0; SPLICE_FOFF=0x3c2ba0
CAVE_VA=0xf064e098;   CAVE_FOFF=0x551098
RET_VA=0xf04bfbd8
def enc_jump(pc,t):
    d=t-pc; assert d%4==0; s=d//4; assert -(1<<21)<=s<(1<<21)
    imm=s&0x3FFFFF; return ((0b0101100<<25)|(((imm>>13)&0x1FF)<<16)|(0b11<<14)|((imm&0x1FFF)<<1))&0xFFFFFFFF
ASM=r"""
    { r1 = ##0xf090fcd4 }
    { r1 = memw(r1+#0) }
    { p0 = cmp.eq(r1,#0x0); if (p0.new) jump:nt .Lend }
    { r1 = add(r1,#0x640) }
    { r2 = ##0x37394e53 }
    { memw(r1+#0x00) = r2 }
    { r2 = memw(r1+#0x04) }
    { r2 = add(r2,#1) }
    { memw(r1+#0x04) = r2 }
    { r3 = memw(r16+#0xe18) }
    { memw(r1+#0x08) = r3 }
    { p0 = cmp.eq(r3,#0x0); if (p0.new) jump:nt .Lend }
    { r4 = memw(r3+#0x10) }
    { memw(r1+#0x0c) = r4 }
    { r5 = memw(r3+#0x48) }
    { memw(r1+#0x24) = r5 }
    { r5 = memw(r3+#0x44) }
    { memw(r1+#0x28) = r5 }
    { r5 = memw(r3+#0x38) }
    { memw(r1+#0x2c) = r5 }
    { p0 = cmp.eq(r4,#0x0); if (p0.new) jump:nt .Lend }
    { r5 = memw(r4+#0x00) }
    { memw(r1+#0x10) = r5 }
    { r5 = memw(r4+#0x14) }
    { memw(r1+#0x14) = r5 }
    { r5 = memw(r4+#0x04) }
    { memw(r1+#0x18) = r5 }
    { p0 = cmp.eq(r5,#0x0); if (p0.new) jump:nt .Lend }
    { r6 = memw(r5+#0x04) }
    { memw(r1+#0x1c) = r6 }
    { r6 = memw(r5+#0x00) }
    { memw(r1+#0x20) = r6 }
.Lend:
    { r17 = r0 }
"""
here=os.path.dirname(os.path.abspath(__file__))
a=os.path.join(here,"snapH97.s");o=os.path.join(here,"snapH97.o");b=os.path.join(here,"snapH97.bin")
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
assert data[CAVE_FOFF:CAVE_FOFF+len(cave)]==b"\x00"*len(cave), "cave region not zero/too small"
assert bytes(data[SPLICE_FOFF:SPLICE_FOFF+4])==bytes.fromhex("11406070"), "splice stock mismatch"
data[CAVE_FOFF:CAVE_FOFF+len(cave)]=cave
data[SPLICE_FOFF:SPLICE_FOFF+4]=struct.pack("<I",spl)
open(OUT,"wb").write(data)
print(f"body {len(body)}B cave {len(cave)}B splice={spl:#010x} ret={ret:#010x} -> {OUT}")
