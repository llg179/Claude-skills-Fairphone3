#!/usr/bin/env python3
# snapFRS6 = WHOLE-PAGE reconnaissance of the framer register block (folyt.134, C2 extension).
# folyt.133 proved the 16 regs {+0x000..+0x01c, +0x600..+0x61c} are BYTE-IDENTICAL working<->dead
# except +0x604 (status/output). FRS6 surveys the REST of the proven-clocked page
# 0xee140000..0xee140fff (stay in ONE mapped MMIO page -> safe) for any SECOND differing register
# that could be the non-config lever. Same both-sides splice as FRS5 (mode-update entry 0xf04c36e8,
# FMD2-proven: fires on dead bring-up AND on UT after framer-activation => FS=1). framer_base is the
# FIXED absolute 0xee140000 (FRS1) -> no ctx needed. +0x604 kept as slot[0] = per-run side anchor
# (dead FS=0 / UT FS=1). Stash: +0x00 'FRS6' | +0x04 base | +0x08 count | +0x0c.. 16 vals (OFFS order).
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os
SRC=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT=f"{FP3_ROOT}/adsp-snapFRS6.mbn"
DELTA=0xf00fd000
def foff(va): return va-DELTA
SPLICE_VA=0xf04c36e8; STOCK=0x7060c010     # { r16 = r0 } single-word (mode-update entry, FMD2/FRS5-proven)
CAVE_VA=0xf064e098
RET_VA=0xf04c36ec
FRAMER=0xee140000
# Reconnaissance offsets — spread across the whole first page, all within 0xee140000..0xee140fff.
# slot0 = +0x604 side-anchor (FS/SFS/MS); rest survey the gaps + upper regions folyt.133 never read.
OFFS=[0x604, 0x020, 0x040, 0x080, 0x0c0, 0x100, 0x180, 0x200, 0x280, 0x300, 0x400, 0x500,
      0x620, 0x680, 0x700, 0x7c0]
assert len(OFFS)==16 and all(o<=0xffc for o in OFFS)
def enc_jump(pc,t):
    d=t-pc; assert d%4==0; s=d//4; assert -(1<<21)<=s<(1<<21)
    imm=s&0x3FFFFF; return ((0b0101100<<25)|(((imm>>13)&0x1FF)<<16)|(0b11<<14)|((imm&0x1FFF)<<1))&0xFFFFFFFF
body=[]
for i,off in enumerate(OFFS):
    slot=0x0c+i*4
    body.append(f"    {{ r4 = memw(r5+#{off:#x}) }}")
    body.append(f"    {{ memw(r3+#{slot:#x}) = r4 }}")
    body.append(f"    {{ r6 = add(r6,#1) }}")
    body.append(f"    {{ memw(r3+#0x08) = r6 }}")
body="\n".join(body)
ASM=fr"""
    // entry: r0/r1/r2 = incoming args (PRESERVE). scratch r3,r4,r5,r6.
    {{ r3 = ##0xf090fcd4 }}
    {{ r3 = memw(r3+#0) }}
    {{ p0 = cmp.eq(r3,#0x0); if (p0.new) jump:nt .Lrep }}
    {{ r3 = add(r3,#0x640) }}
    {{ r4 = ##0x36535246 }}                 // 'FRS6'  (bytes 46 52 53 36 LE)
    {{ memw(r3+#0x00) = r4 }}
    {{ r5 = ##{FRAMER:#010x} }}             // absolute framer base
    {{ memw(r3+#0x04) = r5 }}
    {{ r6 = #0 }}
    {{ memw(r3+#0x08) = r6 }}
{body}
.Lrep:
    {{ r16 = r0 }}                          // replicate spliced word
    {{ r5 = ##{RET_VA:#010x} }}
    {{ jumpr r5 }}
"""
here=os.path.dirname(os.path.abspath(__file__))
a=os.path.join(here,"snapFRS6.s");o=os.path.join(here,"snapFRS6.o");b=os.path.join(here,"snapFRS6.bin")
open(a,"w").write(ASM)
MC=subprocess.run(["bash","-lc","command -v llvm-mc-21 || command -v llvm-mc"],capture_output=True,text=True).stdout.strip()
OC=subprocess.run(["bash","-lc","command -v llvm-objcopy-21 || command -v llvm-objcopy"],capture_output=True,text=True).stdout.strip()
subprocess.run([MC,"--arch=hexagon","--mcpu=hexagonv60","--filetype=obj",a,"-o",o],check=True)
subprocess.run([OC,"-O","binary","--only-section=.text",o,b],check=True)
cave=open(b,"rb").read()
data=bytearray(open(SRC,"rb").read())
assert struct.unpack_from("<I",data,foff(SPLICE_VA))[0]==STOCK, f"splice stock mismatch: {struct.unpack_from('<I',data,foff(SPLICE_VA))[0]:#x}"
assert data[foff(CAVE_VA):foff(CAVE_VA)+len(cave)]==b"\x00"*len(cave), "cave region not zero"
data[foff(CAVE_VA):foff(CAVE_VA)+len(cave)]=cave
j=enc_jump(SPLICE_VA,CAVE_VA); data[foff(SPLICE_VA):foff(SPLICE_VA)+4]=struct.pack("<I",j)
open(OUT,"wb").write(data)
print(f"cave={len(cave)}B@{CAVE_VA:#x} splice={j:#010x}@{SPLICE_VA:#x} ret={RET_VA:#x} -> {OUT}")
