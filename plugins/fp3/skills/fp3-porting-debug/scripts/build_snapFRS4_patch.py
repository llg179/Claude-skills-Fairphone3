#!/usr/bin/env python3
# snapFRS4 = WORKING-side framer register read (folyt.132, C2 baseline). FRS2's enumerate-timeout
# splice is dead-side-only (doesn't run on clean UT bring-up), so use the laddr-assign fn 0xf04c8b7c
# ("Assigning device logical address" @0xf04c8bdc) which DOES run on UT (wcd9335 gets a laddr after
# framing => FS=1 by then). framer_base is the FIXED absolute address 0xee140000 (FRS1) -> no ctx
# needed. Reads the SAME 16 offsets as FRS2 -> direct working(UT)<->dead(pmOS) comparison.
# Splice the 2-word prologue packet 0xf04c8b84 { r17:16=combine(r1,r2); r18=r0 } -> cave reads framer
# (scratch r3-r6, preserves r0/r1/r2) -> REPLICATES both words -> returns 0xf04c8b8c.
# Stash: +0x00 'FRS4' | +0x04 base | +0x08 count | +0x0c.. 16 vals (same order as FRS2):
#   [0x000,0x004,0x008,0x00c,0x010,0x014,0x018,0x01c, 0x600,0x604,0x608,0x60c,0x610,0x614,0x618,0x61c]
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os
SRC=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT=f"{FP3_ROOT}/adsp-snapFRS4.mbn"
DELTA=0xf00fd000
def foff(va): return va-DELTA
SPLICE_VA=0xf04c8b84; STOCK=0xf5014210     # { r17:16 = combine(r1,r2) ; r18 = r0 } -> replace 1st word
CAVE_VA=0xf064e098
RET_VA=0xf04c8b8c
FRAMER=0xee140000
OFFS=[0x000,0x004,0x008,0x00c,0x010,0x014,0x018,0x01c,0x600,0x604,0x608,0x60c,0x610,0x614,0x618,0x61c]
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
    {{ r4 = ##0x34535246 }}                 // 'FRS4'
    {{ memw(r3+#0x00) = r4 }}
    {{ r5 = ##{FRAMER:#010x} }}             // absolute framer base
    {{ memw(r3+#0x04) = r5 }}
    {{ r6 = #0 }}
    {{ memw(r3+#0x08) = r6 }}
{body}
.Lrep:
    {{ r17:16 = combine(r1,r2) }}           // replicate spliced word 1
    {{ r18 = r0 }}                          // replicate spliced word 2
    {{ r5 = ##{RET_VA:#010x} }}
    {{ jumpr r5 }}
"""
here=os.path.dirname(os.path.abspath(__file__))
a=os.path.join(here,"snapFRS4.s");o=os.path.join(here,"snapFRS4.o");b=os.path.join(here,"snapFRS4.bin")
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
