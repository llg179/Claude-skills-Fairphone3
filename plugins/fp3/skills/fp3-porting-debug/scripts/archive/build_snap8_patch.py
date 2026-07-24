#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Stage-8 (SNP8): dump the f0191c68 clock-group input+output arrays at splice
# f04bfba0 (after enable, rc in r0). From Stage-7: cfg r1=0xf0c85450 has
# +0x8=0xf0c85430 (input array, 4 entries x 8B = {type, sub_ptr}) and
# +0xc=0xf0c85468 (output array, 4 x 4B). Dump both to characterise the 4
# clock ops (types + leaf pointers) and their results. Fixed fw addresses only,
# no guessed deref (Stage-5 lesson). Stash @ SMEM PA 0x86302ab0 (64B):
#   +0x00 "SNP8" | +0x04 id | +0x08 rc |
#   +0x0c..+0x2c input[0..7] (8 words from 0xf0c85430) |
#   +0x2c..+0x3c output[0..3] (4 words from 0xf0c85468)
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os
SRC=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT=f"{FP3_ROOT}/adsp-snap8.mbn"
SPLICE_VA=0xf04bfba0; SPLICE_FOFF=0x3c2ba0
CAVE_VA=0xf064e098;   CAVE_FOFF=0x551098
RET_VA=0xf04bfbd8
IN_BASE=0xf0c85430; IN_N=8
OUT_BASE=0xf0c85468; OUT_N=4
def enc_jump(pc,t):
    d=t-pc; assert d%4==0; s=d//4; assert -(1<<21)<=s<(1<<21)
    imm=s&0x3FFFFF; return ((0b0101100<<25)|(((imm>>13)&0x1FF)<<16)|(0b11<<14)|((imm&0x1FFF)<<1))&0xFFFFFFFF
assert enc_jump(0xf04bfc38,0xf01b15d0)==0x599ecccc
dump=""
dst=0x0c
for i in range(IN_N):
    dump+=f"    {{ r2 = memw(r3+#{i*4:#x}) }}\n    {{ memw(r1+#{dst:#x}) = r2 }}\n"; dst+=4
dump+=f"    {{ r3 = ##0x{OUT_BASE:08x} }}\n"
for i in range(OUT_N):
    dump+=f"    {{ r2 = memw(r3+#{i*4:#x}) }}\n    {{ memw(r1+#{dst:#x}) = r2 }}\n"; dst+=4
ASM=f"""
    {{ r1 = ##0xf090fcd4 }}
    {{ r1 = memw(r1+#0) }}
    {{ p0 = cmp.eq(r1,#0x0); if (p0.new) jump:nt .Lend }}
    {{ r1 = add(r1,#0x640) }}
    {{ r2 = ##0x38504e53 }}
    {{ memw(r1+#0x00) = r2 }}
    {{ r2 = memw(r16+#0xe14) }}
    {{ memw(r1+#0x04) = r2 }}
    {{ memw(r1+#0x08) = r0 }}
    {{ r3 = ##0x{IN_BASE:08x} }}
{dump}.Lend:
    {{ r17 = r0 }}
"""
tmp="/tmp/claude-1000/-mnt-1TB-Fp3-Sailfish/dd323baf-a481-4cdd-8106-416f327bbc92/scratchpad"
a=os.path.join(tmp,"snap8.s");o=os.path.join(tmp,"snap8.o");b=os.path.join(tmp,"snap8.bin")
open(a,"w").write(ASM)
subprocess.run(["llvm-mc-21","--arch=hexagon","--mcpu=hexagonv60","--filetype=obj",a,"-o",o],check=True)
subprocess.run(["llvm-objcopy-21","-O","binary","--only-section=.text",o,b],check=True)
body=open(b,"rb").read()
ret=enc_jump(CAVE_VA+len(body),RET_VA)
cave=body+struct.pack("<I",ret)
spl=enc_jump(SPLICE_VA,CAVE_VA)
data=bytearray(open(SRC,"rb").read())
assert data[CAVE_FOFF:CAVE_FOFF+len(cave)]==b"\x00"*len(cave), "cave hole not zero / too big"
assert bytes(data[SPLICE_FOFF:SPLICE_FOFF+4])==bytes.fromhex("11406070"), "splice site not r17=r0"
data[CAVE_FOFF:CAVE_FOFF+len(cave)]=cave
data[SPLICE_FOFF:SPLICE_FOFF+4]=struct.pack("<I",spl)
open(OUT,"wb").write(data); open(os.path.join(tmp,"cave8.bin"),"wb").write(cave)
print(f"body {len(body)}B cave {len(cave)}B splice={spl:#010x} ret={ret:#010x} laststash={dst:#x} wrote {OUT}")
