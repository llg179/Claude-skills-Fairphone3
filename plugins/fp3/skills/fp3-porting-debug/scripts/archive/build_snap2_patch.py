#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Stage-2: capture the clock-enable rc. Splice over f04bfba0 (the `r17=r0 ;
# if(rc==0) jump 0xf04bfbd8` packet). Cave stashes {SNP1, rc, ctx+0xe14,
# ctx+0x88, ctx+0xdfc, ctx+0xdec} then replicates the conditional via two
# hand-encoded J2 trampolines (rc==0 -> 0xf04bfbd8, rc!=0 -> 0xf04bfba8).
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os

SRC = f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT = f"{FP3_ROOT}/adsp-snap2.mbn"
SPLICE_VA=0xf04bfba0; SPLICE_FOFF=0x3c2ba0    # f04bfba0 = 0x3c2b68 + 0x38
CAVE_VA=0xf064e098;   CAVE_FOFF=0x551098
RET_SUCC=0xf04bfbd8   # rc==0
RET_CONT=0xf04bfba8   # rc!=0 (fall-through / error path)

def enc_jump(pc,target):
    delta=target-pc; assert delta%4==0,hex(delta)
    s=delta//4; assert -(1<<21)<=s<(1<<21),f"range {delta:#x}"
    imm=s&0x3FFFFF; hi=(imm>>13)&0x1FF; lo=imm&0x1FFF
    return ((0b0101100<<25)|(hi<<16)|(0b11<<14)|(lo<<1))&0xFFFFFFFF
assert enc_jump(0xf04bfc38,0xf01b15d0)==0x599ecccc

ASM=r"""
    { r1 = ##0xf090fcd4 }
    { r1 = memw(r1+#0) }
    { p0 = cmp.eq(r1,#0x0); if (p0.new) jump:nt .Lskip }
    { r1 = add(r1,#0x640) }
    { r2 = ##0x31504e53 }
    { memw(r1+#0x00) = r2 }
    { memw(r1+#0x04) = r0 }
    { r2 = memw(r16+#0xe14) }
    { memw(r1+#0x08) = r2 }
    { r2 = memw(r16+#0x88) }
    { memw(r1+#0x0c) = r2 }
    { r2 = memw(r16+#0xdfc) }
    { memw(r1+#0x10) = r2 }
    { r2 = memw(r16+#0xdec) }
    { memw(r1+#0x14) = r2 }
.Lskip:
    { r17 = r0; if (cmp.eq(r17.new,#0x0)) jump:nt .Ltramp }
    { jump .Lend }
.Ltramp:
    { jump .Lend }
.Lend:
"""

tmp="/tmp/claude-1000/-mnt-1TB-Fp3-Sailfish/1f56a429-b78f-4e19-a981-9475ce6ac58c/scratchpad"
a=os.path.join(tmp,"snap2.s"); o=os.path.join(tmp,"snap2.o"); b=os.path.join(tmp,"snap2.bin")
open(a,"w").write(ASM)
subprocess.run(["llvm-mc-21","--arch=hexagon","--mcpu=hexagonv60","--filetype=obj",a,"-o",o],check=True)
subprocess.run(["llvm-objcopy-21","-O","binary","--only-section=.text",o,b],check=True)
body=bytearray(open(b,"rb").read())
L=len(body); print("body",L,"bytes")
# word A = fall-through (rc!=0) at L-8 -> RET_CONT ; word B = .Ltramp (rc==0) at L-4 -> RET_SUCC
wA_va=CAVE_VA+(L-8); wB_va=CAVE_VA+(L-4)
body[L-8:L-4]=struct.pack("<I",enc_jump(wA_va,RET_CONT))
body[L-4:L]  =struct.pack("<I",enc_jump(wB_va,RET_SUCC))
print(f"wordA @{wA_va:#x}->{RET_CONT:#x}  wordB @{wB_va:#x}->{RET_SUCC:#x}")
cave=bytes(body)
spl=enc_jump(SPLICE_VA,CAVE_VA)
data=bytearray(open(SRC,"rb").read())
assert data[CAVE_FOFF:CAVE_FOFF+len(cave)]==b"\x00"*len(cave),"cave not zero"
# f04bfba0 original first word = 11 40 60 70 (r17=r0)
assert bytes(data[SPLICE_FOFF:SPLICE_FOFF+4])==bytes.fromhex("11406070"),data[SPLICE_FOFF:SPLICE_FOFF+4].hex()
data[CAVE_FOFF:CAVE_FOFF+len(cave)]=cave
data[SPLICE_FOFF:SPLICE_FOFF+4]=struct.pack("<I",spl)
open(OUT,"wb").write(data)
open(os.path.join(tmp,"cave2.bin"),"wb").write(cave)
print(f"splice @{SPLICE_VA:#x}->{CAVE_VA:#x}={spl:#010x}; wrote {OUT}; cave {len(cave)}B")
