#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# snapVA: capture the CONSTANT SMEM base ADSP-VA (= value of *(0xf090fcd4)) so it can be
# hardcoded into an EARLY-phase leaf cave (where *(0xf090fcd4) is still null). Splice at the
# proven-safe SMEM-READY config-group point f04bfba0 (same as snapT3; stock 11406070 = r17=r0),
# stash at *(0xf090fcd4)+0x640: magic 'HVA0', the pointer value, two neighbors, config rc.
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os
SRC=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT=f"{FP3_ROOT}/adsp-snapVA.mbn"
SPLICE_VA=0xf04bfba0; SPLICE_FOFF=0x3c2ba0; STOCK=bytes.fromhex("11406070")
CAVE_VA=0xf064e098; CAVE_FOFF=0x551098; RET_VA=0xf04bfbd8
def enc_jump(pc,t):
    d=t-pc; s=d//4; imm=s&0x3FFFFF
    return ((0b0101100<<25)|(((imm>>13)&0x1FF)<<16)|(0b11<<14)|((imm&0x1FFF)<<1))&0xFFFFFFFF
ASM=r"""
    { r1 = ##0xf090fcd4 }
    { r2 = memw(r1+#0) }
    { p0 = cmp.eq(r2,#0x0); if (p0.new) jump:nt .Lexit }
    { r3 = add(r2,#0x640) }
    { r4 = ##0x30415648 }             // 'H''V''A''0'
    { memw(r3+#0x00) = r4 }
    { memw(r3+#0x04) = r2 }           // *(0xf090fcd4)  = SMEM base ADSP-VA (the constant)
    { r5 = memw(r1+#-4) }
    { memw(r3+#0x08) = r5 }           // *(0xf090fcd0)
    { r5 = memw(r1+#4) }
    { memw(r3+#0x0c) = r5 }           // *(0xf090fcd8)
    { memw(r3+#0x10) = r0 }           // config-group rc
.Lexit:
    { r17 = r0 }
"""
here=os.path.dirname(os.path.abspath(__file__))
a=os.path.join(here,"snapVA.s");o=os.path.join(here,"snapVA.o");b=os.path.join(here,"snapVA.bin")
open(a,"w").write(ASM)
MC=subprocess.run(["bash","-lc","command -v llvm-mc-21 || command -v llvm-mc"],capture_output=True,text=True).stdout.strip()
OC=subprocess.run(["bash","-lc","command -v llvm-objcopy-21 || command -v llvm-objcopy"],capture_output=True,text=True).stdout.strip()
subprocess.run([MC,"--arch=hexagon","--mcpu=hexagonv60","--filetype=obj",a,"-o",o],check=True)
subprocess.run([OC,"-O","binary","--only-section=.text",o,b],check=True)
body=open(b,"rb").read()
ret=enc_jump(CAVE_VA+len(body),RET_VA); cave=body+struct.pack("<I",ret); spl=enc_jump(SPLICE_VA,CAVE_VA)
data=bytearray(open(SRC,"rb").read())
assert bytes(data[SPLICE_FOFF:SPLICE_FOFF+4])==STOCK, "splice stock mismatch"
assert data[CAVE_FOFF:CAVE_FOFF+len(cave)]==b"\x00"*len(cave), "cave not zero"
data[CAVE_FOFF:CAVE_FOFF+len(cave)]=cave; data[SPLICE_FOFF:SPLICE_FOFF+4]=struct.pack("<I",spl)
open(OUT,"wb").write(data)
print(f"cave {len(cave)}B splice={spl:#010x} ret={ret:#010x} -> {OUT}")
