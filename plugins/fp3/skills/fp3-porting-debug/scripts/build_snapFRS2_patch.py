#!/usr/bin/env python3
# snapFRS2 = wider framer register window (folyt.131b, C2). FRS1 found framer_base=0xee140000, safe,
# +0x604=0 (FS/SFS/MS=0 dead), +0x600=1. Now read config 0x000-0x01c + control 0x600-0x61c (16 regs)
# to characterise the dead framer block and locate the framing-enable control. Same splice as FRS1
# (0xf04c3540 {r16=r0}, enumerate-timeout prologue, ctx=r0). base 0xee140000 is one mapped clocked
# 4KB page -> any offset in it is safe. Per-read count (+0x08) = bounded probe (if a read hangs, count
# tells which offset in the fixed order). Total write kept <=0x50B (SMEM-stash size lesson).
# Stash: +0x00 'FRS2' | +0x04 base | +0x08 count | +0x0c.. 16 values in this fixed order:
#   [0x000,0x004,0x008,0x00c,0x010,0x014,0x018,0x01c, 0x600,0x604,0x608,0x60c,0x610,0x614,0x618,0x61c]
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os
SRC=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT=f"{FP3_ROOT}/adsp-snapFRS2.mbn"
DELTA=0xf00fd000
def foff(va): return va-DELTA
SPLICE_VA=0xf04c3540; STOCK=0x7060c010
CAVE_VA=0xf064e098
RET_VA=0xf04c3544
OFFS=[0x000,0x004,0x008,0x00c,0x010,0x014,0x018,0x01c,0x600,0x604,0x608,0x60c,0x610,0x614,0x618,0x61c]
def enc_jump(pc,t):
    d=t-pc; assert d%4==0; s=d//4; assert -(1<<21)<=s<(1<<21)
    imm=s&0x3FFFFF; return ((0b0101100<<25)|(((imm>>13)&0x1FF)<<16)|(0b11<<14)|((imm&0x1FFF)<<1))&0xFFFFFFFF
# build the read/store/count body
body=[]
for i,off in enumerate(OFFS):
    slot=0x0c+i*4
    body.append(f"    {{ r4 = memw(r5+#{off:#x}) }}")
    body.append(f"    {{ memw(r3+#{slot:#x}) = r4 }}")
    body.append(f"    {{ r6 = add(r6,#1) }}")
    body.append(f"    {{ memw(r3+#0x08) = r6 }}")   # running count after each read
body="\n".join(body)
ASM=fr"""
    {{ r3 = ##0xf090fcd4 }}
    {{ r3 = memw(r3+#0) }}
    {{ p0 = cmp.eq(r3,#0x0); if (p0.new) jump:nt .Lset }}
    {{ r3 = add(r3,#0x640) }}
    {{ r4 = ##0x32535246 }}                 // 'FRS2'
    {{ memw(r3+#0x00) = r4 }}
    {{ r5 = memw(r0+#0x5c) }}               // framer base
    {{ memw(r3+#0x04) = r5 }}
    {{ r6 = #0 }}
    {{ memw(r3+#0x08) = r6 }}
    {{ p0 = cmp.eq(r5,#0x0); if (p0.new) jump:nt .Lset }}
{body}
.Lset:
    {{ r16 = r0 }}
    {{ r5 = ##{RET_VA:#010x} }}
    {{ jumpr r5 }}
"""
here=os.path.dirname(os.path.abspath(__file__))
a=os.path.join(here,"snapFRS2.s");o=os.path.join(here,"snapFRS2.o");b=os.path.join(here,"snapFRS2.bin")
open(a,"w").write(ASM)
MC=subprocess.run(["bash","-lc","command -v llvm-mc-21 || command -v llvm-mc"],capture_output=True,text=True).stdout.strip()
OC=subprocess.run(["bash","-lc","command -v llvm-objcopy-21 || command -v llvm-objcopy"],capture_output=True,text=True).stdout.strip()
subprocess.run([MC,"--arch=hexagon","--mcpu=hexagonv60","--filetype=obj",a,"-o",o],check=True)
subprocess.run([OC,"-O","binary","--only-section=.text",o,b],check=True)
cave=open(b,"rb").read()
data=bytearray(open(SRC,"rb").read())
assert struct.unpack_from("<I",data,foff(SPLICE_VA))[0]==STOCK, "splice stock mismatch"
assert data[foff(CAVE_VA):foff(CAVE_VA)+len(cave)]==b"\x00"*len(cave), "cave region not zero/too big"
data[foff(CAVE_VA):foff(CAVE_VA)+len(cave)]=cave
j=enc_jump(SPLICE_VA,CAVE_VA); data[foff(SPLICE_VA):foff(SPLICE_VA)+4]=struct.pack("<I",j)
open(OUT,"wb").write(data)
print(f"cave={len(cave)}B@{CAVE_VA:#x} splice={j:#010x} last-slot=+{0x0c+15*4:#x} -> {OUT}")
