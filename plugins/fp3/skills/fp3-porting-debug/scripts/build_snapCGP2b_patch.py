#!/usr/bin/env python3
# snapCGP2b = SAFE pointer-only variant of snapCGP2 (folyt.114 crash-fix).
# snapCGP2 crashed on the DEAD side by dereferencing s3c=memw(handle+0x3c) when it was
# uninitialised garbage -> NoC fault -> boot-loop. This variant captures ONLY the handle
# fields (0x38/0x3c/0x40) WITHOUT dereferencing s3c, so it is safe on BOTH sides. Goal:
# does the deeper-hop subobject pointer (handle+0x3c) itself diverge working<->dead?
# If identical (like +0x48/+0x40/+0x08/+0x0c/+0x34 already were, folyt.116), the whole
# level-1 dispatch object graph matches -> divergence is purely physical realization.
# Same proven splice/exit as snapCGP (f04bfba0 -> f04bfbd8). Magic 'CGP3'=0x33504743.
#   +0x00 'CGP3' +0x04 handle +0x08 handle+0x38 +0x0c handle+0x3c(subobj ptr, NO deref)
#   +0x10 handle+0x40 +0x14 handle+0x44 +0x18 handle+0x48 +0x1c rc
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os
SRC=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT=f"{FP3_ROOT}/adsp-snapCGP2b.mbn"
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
    { r2 = ##0x33504743 }              // 'C''G''P''3'
    { memw(r1+#0x00) = r2 }
    { r3 = memw(r16+#0xe18) }          // handle
    { memw(r1+#0x04) = r3 }
    { p0 = cmp.eq(r3,#0x0); if (p0.new) jump:nt .Lrc }
    { r4 = memw(r3+#0x38) }
    { memw(r1+#0x08) = r4 }
    { r4 = memw(r3+#0x3c) }            // subobj ptr -- captured but NOT dereferenced
    { memw(r1+#0x0c) = r4 }
    { r4 = memw(r3+#0x40) }
    { memw(r1+#0x10) = r4 }
    { r4 = memw(r3+#0x44) }
    { memw(r1+#0x14) = r4 }
    { r4 = memw(r3+#0x48) }
    { memw(r1+#0x18) = r4 }
.Lrc:
    { memw(r1+#0x1c) = r0 }
.Lskip:
    { r17 = r0 }
"""
here=os.path.dirname(os.path.abspath(__file__))
a=os.path.join(here,"snapCGP2b.s");o=os.path.join(here,"snapCGP2b.o");b=os.path.join(here,"snapCGP2b.bin")
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
