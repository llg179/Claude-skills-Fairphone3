#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# SNTb (T3 hop-2): dump the config-group cfg block HEAD 0xf0c85400..0xf0c8544c (20 words) —
# the region the hop-1 pointers (0xf0c85404/28/30) reference; hop-1 already has 0xf0c85440..6c.
# Same proven splice (f04bfba0, stock 11406070), same cave slot. Straight-line, exit to RET.
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os
SRC=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT=f"{FP3_ROOT}/adsp-snapT3b.mbn"
SPLICE_VA=0xf04bfba0; SPLICE_FOFF=0x3c2ba0
CAVE_VA=0xf064e098;   CAVE_FOFF=0x551098
RET_VA=0xf04bfbd8
def enc_jump(pc,t):
    d=t-pc; assert d%4==0; s=d//4; assert -(1<<21)<=s<(1<<21)
    imm=s&0x3FFFFF; return ((0b0101100<<25)|(((imm>>13)&0x1FF)<<16)|(0b11<<14)|((imm&0x1FFF)<<1))&0xFFFFFFFF
# 20 words from 0xf0c85400 -> stash +0x04..+0x50
lines = [
 "    { r1 = ##0xf090fcd4 }",
 "    { r1 = memw(r1+#0) }",
 "    { p0 = cmp.eq(r1,#0x0); if (p0.new) jump:nt .Lskip }",
 "    { r1 = add(r1,#0x640) }",
 "    { r2 = ##0x62544e53 }",
 "    { memw(r1+#0x00) = r2 }",
 "    { r4 = ##0xf0c85400 }",
]
for i in range(20):
    lines.append(f"    {{ r3 = memw(r4+#0x{i*4:x}) }}")
    lines.append(f"    {{ memw(r1+#0x{4+i*4:x}) = r3 }}")
lines += [".Lskip:", "    { r17 = r0 }"]
ASM="\n".join(lines)+"\n"
here=os.path.dirname(os.path.abspath(__file__))
a=os.path.join(here,"snapT3b.s");o=os.path.join(here,"snapT3b.o");b=os.path.join(here,"snapT3b.bin")
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
print(f"body {len(body)}B cave {len(cave)}B splice={spl:#010x} -> {OUT}")
