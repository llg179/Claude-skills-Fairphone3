#!/usr/bin/env python3
# snapFWT1 = framer register WRITE tracer (folyt.152). Hooks the framer register-write HAL 0xf04bfe54:
# its tail 0xf04bfe80 `{ r3 = add(r1,r0) }` computes the target address (r0=base, r1=offset) right before
# the store `memw(r3)=r2` at 0xf04bfe88. Splice there, filter to the framer aperture (0xee14xxxx), and
# append (addr,value) to a ring buffer in SMEM. Reveals the LIVE sequence of framer HW writes during the
# (failed) SLIMbus bring-up on the dead side -> shows whether a frame-start/enable write is even attempted
# before the capability timeout, and its exact target/value (incl. self-clearing trigger writes that never
# show in a resting register diff). Registers: r0,r1 dead after (r3 computed), r2 must survive (downstream
# store), r4-r7 scratch (leaf fn returns after the store). Ring @ SMEM+0x680 (AP PA 0x86300000+0x2af0):
#   +0x00 'FWTF' | +0x04 count | +0x08.. up to 64 (addr,value) pairs [8 bytes each]
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os
SRC=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT=f"{FP3_ROOT}/adsp-snapFWT1.mbn"
DELTA=0xf00fd000
def foff(va): return va-DELTA
SPLICE_VA=0xf04bfe80; STOCK=0xf301c003     # { r3 = add(r1,r0) }
CAVE_VA=0xf064e098; RET_VA=0xf04bfe84
def enc_jump(pc,t):
    d=t-pc; assert d%4==0; s=d//4; assert -(1<<21)<=s<(1<<21)
    imm=s&0x3FFFFF; return ((0b0101100<<25)|(((imm>>13)&0x1FF)<<16)|(0b11<<14)|((imm&0x1FFF)<<1))&0xFFFFFFFF
ASM=fr"""
    {{ r3 = add(r1,r0) }}                                     // replicate: r3 = target addr
    {{ r4 = and(r3,##0xffff0000) }}
    {{ p0 = cmp.eq(r4,##0xee140000); if (!p0.new) jump:nt .Lout }}   // framer aperture only
    {{ r4 = ##0xf090fcd4 }}
    {{ r4 = memw(r4+#0) }}
    {{ p0 = cmp.eq(r4,#0x0); if (p0.new) jump:nt .Lout }}
    {{ r4 = add(r4,#0x680) }}                                 // ring base
    {{ r6 = ##0x46545746 }}                                   // 'FWTF'
    {{ memw(r4+#0x00) = r6 }}
    {{ r5 = memw(r4+#0x04) }}                                 // count
    {{ p0 = cmp.gtu(r5,#0x3f); if (p0.new) jump:nt .Lout }}   // cap 64 entries
    {{ r6 = asl(r5,#0x3) }}
    {{ r6 = add(r6,#0x08) }}
    {{ r7 = add(r4,r6) }}
    {{ memw(r7+#0x00) = r3 }}                                 // addr
    {{ memw(r7+#0x04) = r2 }}                                 // value written
    {{ r5 = add(r5,#0x1) }}
    {{ memw(r4+#0x04) = r5 }}
.Lout:
    {{ r5 = ##{RET_VA:#010x} }}
    {{ jumpr r5 }}
"""
here=os.path.dirname(os.path.abspath(__file__))
a=os.path.join(here,"snapFWT1.s");o=os.path.join(here,"snapFWT1.o");b=os.path.join(here,"snapFWT1.bin")
open(a,"w").write(ASM)
MC=subprocess.run(["bash","-lc","command -v llvm-mc-21 || command -v llvm-mc"],capture_output=True,text=True).stdout.strip()
OC=subprocess.run(["bash","-lc","command -v llvm-objcopy-21 || command -v llvm-objcopy"],capture_output=True,text=True).stdout.strip()
subprocess.run([MC,"--arch=hexagon","--mcpu=hexagonv60","--filetype=obj",a,"-o",o],check=True)
subprocess.run([OC,"-O","binary","--only-section=.text",o,b],check=True)
cave=open(b,"rb").read()
data=bytearray(open(SRC,"rb").read())
got=struct.unpack_from("<I",data,foff(SPLICE_VA))[0]
assert got==STOCK, f"splice stock mismatch: {got:#x}"
assert data[foff(CAVE_VA):foff(CAVE_VA)+len(cave)]==b"\x00"*len(cave), "cave not zero"
data[foff(CAVE_VA):foff(CAVE_VA)+len(cave)]=cave
j=enc_jump(SPLICE_VA,CAVE_VA); data[foff(SPLICE_VA):foff(SPLICE_VA)+4]=struct.pack("<I",j)
open(OUT,"wb").write(data)
print(f"FWT1 cave={len(cave)}B@{CAVE_VA:#x} splice={j:#010x}@{SPLICE_VA:#x} ret={RET_VA:#x} -> {OUT}")
