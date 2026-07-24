#!/usr/bin/env python3
# SNT3 (T3 hop-1): the config-group path (f0191c68) was NEVER walked (snapD walked the
# NPA-vote side). Splice at the proven-safe f04bfba0 (rc of f0191c68), capture:
#  - r0 = config-group rc
#  - the .bss GATE memw(0xf0913658) + neighbours (f0191c68 branches on this)
#  - ctx fields (sat_hw_owner +0x74, group id +0xe14, core-clk handle +0xe18)
#  - the runtime cfg region 0xf0c85450 (§11 "cfg@0xf0c85450") + 0xf0c85440
# All absolute reads are ADSP .bss (safe) + ctx derefs the code itself uses. Straight-line,
# null-guarded, single unconditional exit to RET_VA (snapD-proven safe). Magic 'SNT3'.
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os
SRC=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT=f"{FP3_ROOT}/adsp-snapT3.mbn"
SPLICE_VA=0xf04bfba0; SPLICE_FOFF=0x3c2ba0
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
    { r2 = ##0x33544e53 }
    { memw(r1+#0x00) = r2 }
    { memw(r1+#0x04) = r0 }
    { r2 = ##0xf0913658 }
    { r3 = memw(r2+#0x00) }
    { memw(r1+#0x08) = r3 }
    { r3 = memw(r2+#0x04) }
    { memw(r1+#0x0c) = r3 }
    { r3 = memw(r2+#0x08) }
    { memw(r1+#0x10) = r3 }
    { r3 = memw(r16+#0x74) }
    { memw(r1+#0x14) = r3 }
    { r3 = memw(r16+#0xe14) }
    { memw(r1+#0x18) = r3 }
    { r3 = memw(r16+#0xe18) }
    { memw(r1+#0x1c) = r3 }
    { r4 = ##0xf0c85450 }
    { r3 = memw(r4+#0x00) }
    { memw(r1+#0x20) = r3 }
    { r3 = memw(r4+#0x04) }
    { memw(r1+#0x24) = r3 }
    { r3 = memw(r4+#0x08) }
    { memw(r1+#0x28) = r3 }
    { r3 = memw(r4+#0x0c) }
    { memw(r1+#0x2c) = r3 }
    { r3 = memw(r4+#0x10) }
    { memw(r1+#0x30) = r3 }
    { r3 = memw(r4+#0x14) }
    { memw(r1+#0x34) = r3 }
    { r3 = memw(r4+#0x18) }
    { memw(r1+#0x38) = r3 }
    { r3 = memw(r4+#0x1c) }
    { memw(r1+#0x3c) = r3 }
    { r4 = ##0xf0c85440 }
    { r3 = memw(r4+#0x00) }
    { memw(r1+#0x40) = r3 }
    { r3 = memw(r4+#0x04) }
    { memw(r1+#0x44) = r3 }
    { r3 = memw(r4+#0x08) }
    { memw(r1+#0x48) = r3 }
    { r3 = memw(r4+#0x0c) }
    { memw(r1+#0x4c) = r3 }
.Lskip:
    { r17 = r0 }
"""
here=os.path.dirname(os.path.abspath(__file__))
a=os.path.join(here,"snapT3.s");o=os.path.join(here,"snapT3.o");b=os.path.join(here,"snapT3.bin")
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
