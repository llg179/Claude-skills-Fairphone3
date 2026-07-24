#!/usr/bin/env python3
# snapFMD2 = UNCONDITIONAL entry-capture of the framer mode-update fn 0xf04c36e0 (folyt.130b).
# FMD1 spliced the transition-gated LOG calls -> neither fired on pmOS SSR (a mode-update that
# doesn't CHANGE mode emits no log). FMD2 splices the fn ENTRY (0xf04c36e8 `{ r16 = r0 }`, single
# word) so it fires EVERY time the fn runs, regardless of transition. Captures the detector inputs
# (exactly the fields 0xf04d14cc dereferences) + current mode-flag + caller r31 (which of the 5
# callers) + an entry counter.
#   Splice 0xf04c36e8 stock=0x7060c010 (`r16=r0`) -> cave: capture (r0=ctx incoming) -> replicate
#   r16=r0 -> return 0xf04c36ec.
# Stash (SMEM +0x640): +0x00 'FMD2' | +0x04 ctx | +0x08 memw(ctx+0x78) mode | +0x0c memw(ctx+0xe08)
#   | +0x10 memw(ctx+0xe58) | +0x14 memw(ctx+0xdb4) | +0x18 memw(ctx+0x6c) | +0x1c caller r31 (LAST)
#   | +0x20 entry-count
# PASS/FAIL: fires on pmOS SSR => mode-update IS on the failing bring-up path; inputs+caller localise.
#   Diff UT vs pmOS inputs => the divergent field (the lever). If it never fires => mode-update is
#   NOT reached on the failing path; wall is elsewhere (capability-receive handler 0xf072a501).
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os
SRC=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT=f"{FP3_ROOT}/adsp-snapFMD2.mbn"
DELTA=0xf00fd000
def foff(va): return va-DELTA
SPLICE_VA=0xf04c36e8; STOCK=0x7060c010          # { r16 = r0 }
CAVE_VA=0xf064e098
RET_VA=0xf04c36ec
def enc_jump(pc,t):
    d=t-pc; assert d%4==0; s=d//4; assert -(1<<21)<=s<(1<<21), f"range {s}"
    imm=s&0x3FFFFF; return ((0b0101100<<25)|(((imm>>13)&0x1FF)<<16)|(0b11<<14)|((imm&0x1FFF)<<1))&0xFFFFFFFF
ASM=fr"""
    // entry: r0=ctx (incoming arg), frame allocated. scratch r3,r4,r5; preserve r0.
    {{ r3 = ##0xf090fcd4 }}
    {{ r3 = memw(r3+#0) }}
    {{ p0 = cmp.eq(r3,#0x0); if (p0.new) jump:nt .Lset }}
    {{ r3 = add(r3,#0x640) }}
    {{ r4 = ##0x32444d46 }}                 // 'FMD2'
    {{ memw(r3+#0x00) = r4 }}
    {{ memw(r3+#0x04) = r0 }}
    {{ r4 = memw(r0+#0x78) }}
    {{ memw(r3+#0x08) = r4 }}
    {{ r4 = memw(r0+#0xe08) }}
    {{ memw(r3+#0x0c) = r4 }}
    {{ r4 = memw(r0+#0xe58) }}
    {{ memw(r3+#0x10) = r4 }}
    {{ r4 = memw(r0+#0xdb4) }}
    {{ memw(r3+#0x14) = r4 }}
    {{ r4 = memw(r0+#0x6c) }}
    {{ memw(r3+#0x18) = r4 }}
    {{ memw(r3+#0x1c) = r31 }}
    {{ r4 = memw(r3+#0x20) }}
    {{ r4 = add(r4,#1) }}
    {{ memw(r3+#0x20) = r4 }}
.Lset:
    {{ r16 = r0 }}
    {{ r5 = ##{RET_VA:#010x} }}
    {{ jumpr r5 }}
"""
here=os.path.dirname(os.path.abspath(__file__))
a=os.path.join(here,"snapFMD2.s");o=os.path.join(here,"snapFMD2.o");b=os.path.join(here,"snapFMD2.bin")
open(a,"w").write(ASM)
MC=subprocess.run(["bash","-lc","command -v llvm-mc-21 || command -v llvm-mc"],capture_output=True,text=True).stdout.strip()
OC=subprocess.run(["bash","-lc","command -v llvm-objcopy-21 || command -v llvm-objcopy"],capture_output=True,text=True).stdout.strip()
subprocess.run([MC,"--arch=hexagon","--mcpu=hexagonv60","--filetype=obj",a,"-o",o],check=True)
subprocess.run([OC,"-O","binary","--only-section=.text",o,b],check=True)
cave=open(b,"rb").read()
data=bytearray(open(SRC,"rb").read())
assert struct.unpack_from("<I",data,foff(SPLICE_VA))[0]==STOCK, "splice stock mismatch"
assert data[foff(CAVE_VA):foff(CAVE_VA)+len(cave)]==b"\x00"*len(cave), "cave region not zero"
data[foff(CAVE_VA):foff(CAVE_VA)+len(cave)]=cave
j=enc_jump(SPLICE_VA,CAVE_VA); data[foff(SPLICE_VA):foff(SPLICE_VA)+4]=struct.pack("<I",j)
open(OUT,"wb").write(data)
print(f"cave={len(cave)}B@{CAVE_VA:#x} splice={j:#010x}@{SPLICE_VA:#x} ret={RET_VA:#x} -> {OUT}")
