#!/usr/bin/env python3
# snapFMD1 = framer-MODE decision capture (folyt.130). Tests hypothesis (C1): under PAS(pmOS) the
# ADSP framer switches to EXTERNAL framer mode ("due to external clock toggle") -> never drives the
# SLIMbus framer -> enumeration timeout -> silent; under PIL(UT) it goes ACTIVE ("lack of external
# clock toggle") -> drives framer -> works.
#
# Two clean single-word splices, both `{ call 0xf01ac468 }` (the MSG-logger), mutually-exclusive
# branches of the mode-decision fn 0xf04c36e4 (ctx=r16 live at both):
#   - ACTIVE  log call  @0xf04c3804 (logs 0xf0726e27) -> cave-A, stamp 'FMDA', return 0xf04c3808
#   - EXTERNAL log call @0xf04c37a8 (logs 0xf0726de1) -> cave-E, stamp 'FMDE', return 0xf04c37ac
# The log line itself is SKIPPED (pure diagnostic; framer behaviour unchanged). ctx fields captured
# are EXACTLY the ones the detector 0xf04d14cc dereferences -> guardrail-safe.
#
# Capture (SMEM stash + 0x640), per branch block:
#   cave-A base +0x00: 'FMDA' | +0x04 ctx | +0x08 memw(ctx+0x78) mode-flag | +0x0c memw(ctx+0xe08)
#              +0x10 memw(ctx+0xe58) | +0x14 memw(ctx+0xdb4) | +0x18 memw(ctx+0x6c) | +0x1c caller r31
#   cave-E base +0x40: 'FMDE' | +0x44 ctx | +0x48 mode | +0x4c ctx+0xe08 | +0x50 ctx+0xe58
#              +0x54 ctx+0xdb4 | +0x58 ctx+0x6c | +0x5c caller
# PASS/FAIL (pre-declared):
#   UT(working): FMDA present (active taken) -> baseline inputs. FMDE absent.
#   pmOS(dead):  FMDE present (external taken) => (C1) CONFIRMED, wall localised to mode-decision;
#                lever = the ctx fields the detector reads. If instead FMDA present with inputs ==
#                UT's -> mode is NOT the divergence (frame falls, move upstream).
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os
SRC=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT=f"{FP3_ROOT}/adsp-snapFMD1.mbn"
DELTA=0xf00fd000
def foff(va): return va-DELTA
CAVE_A_VA=0xf064e098
CAVE_E_VA=0xf064e118      # +0x80, inside the 0xf70 free run
def enc_jump(pc,t):
    d=t-pc; assert d%4==0; s=d//4; assert -(1<<21)<=s<(1<<21), f"jump range {s}"
    imm=s&0x3FFFFF; return ((0b0101100<<25)|(((imm>>13)&0x1FF)<<16)|(0b11<<14)|((imm&0x1FFF)<<1))&0xFFFFFFFF

# cave templates: STASH via global 0xf090fcd4 (holds stash base ptr), +0x640, per CKB proven path.
# scratch r3,r4,r5 only (r16=ctx preserved; r0-r2 dead since log skipped; r18 preserved for active tail).
def cave_asm(magic, base_off, ret_va):
    return f"""
    {{ r3 = ##0xf090fcd4 }}
    {{ r3 = memw(r3+#0) }}
    {{ p0 = cmp.eq(r3,#0x0); if (p0.new) jump:nt .Lx }}
    {{ r3 = add(r3,#0x640) }}
    {{ r4 = ##{magic:#010x} }}
    {{ memw(r3+#{base_off+0x00}) = r4 }}
    {{ memw(r3+#{base_off+0x04}) = r16 }}
    {{ r4 = memw(r16+#0x78) }}
    {{ memw(r3+#{base_off+0x08}) = r4 }}
    {{ r4 = memw(r16+#0xe08) }}
    {{ memw(r3+#{base_off+0x0c}) = r4 }}
    {{ r4 = memw(r16+#0xe58) }}
    {{ memw(r3+#{base_off+0x10}) = r4 }}
    {{ r4 = memw(r16+#0xdb4) }}
    {{ memw(r3+#{base_off+0x14}) = r4 }}
    {{ r4 = memw(r16+#0x6c) }}
    {{ memw(r3+#{base_off+0x18}) = r4 }}
    {{ memw(r3+#{base_off+0x1c}) = r31 }}
.Lx:
    {{ r5 = ##{ret_va:#010x} }}
    {{ jumpr r5 }}
"""

here=os.path.dirname(os.path.abspath(__file__))
MC=subprocess.run(["bash","-lc","command -v llvm-mc-21 || command -v llvm-mc"],capture_output=True,text=True).stdout.strip()
OC=subprocess.run(["bash","-lc","command -v llvm-objcopy-21 || command -v llvm-objcopy"],capture_output=True,text=True).stdout.strip()
def assemble(name,asm):
    a=os.path.join(here,name+".s"); o=os.path.join(here,name+".o"); b=os.path.join(here,name+".bin")
    open(a,"w").write(asm)
    subprocess.run([MC,"--arch=hexagon","--mcpu=hexagonv60","--filetype=obj",a,"-o",o],check=True)
    subprocess.run([OC,"-O","binary","--only-section=.text",o,b],check=True)
    return open(b,"rb").read()

# 'FMDA' LE = 0x41444d46 ; 'FMDE' = 0x45444d46
caveA=assemble("snapFMD1_A", cave_asm(0x41444d46, 0x00, 0xf04c3808))
caveE=assemble("snapFMD1_E", cave_asm(0x45444d46, 0x40, 0xf04c37ac))
assert len(caveA)<=0x80 and len(caveE)<=0x80, f"cave too big A={len(caveA)} E={len(caveE)}"

data=bytearray(open(SRC,"rb").read())
# splice sites
for va,stock in [(0xf04c3804,0x5b9dc632),(0xf04c37a8,0x5b9dc660)]:
    assert struct.unpack_from("<I",data,foff(va))[0]==stock, f"splice stock mismatch @{va:#x}"
# cave regions must be zero
for cva,cave in [(CAVE_A_VA,caveA),(CAVE_E_VA,caveE)]:
    cf=foff(cva); assert data[cf:cf+len(cave)]==b"\x00"*len(cave), f"cave region not zero @{cva:#x}"
# write caves
for cva,cave in [(CAVE_A_VA,caveA),(CAVE_E_VA,caveE)]:
    cf=foff(cva); data[cf:cf+len(cave)]=cave
# write splice jumps
jA=enc_jump(0xf04c3804,CAVE_A_VA); data[foff(0xf04c3804):foff(0xf04c3804)+4]=struct.pack("<I",jA)
jE=enc_jump(0xf04c37a8,CAVE_E_VA); data[foff(0xf04c37a8):foff(0xf04c37a8)+4]=struct.pack("<I",jE)
open(OUT,"wb").write(data)
print(f"caveA={len(caveA)}B@{CAVE_A_VA:#x} spliceA={jA:#010x}  caveE={len(caveE)}B@{CAVE_E_VA:#x} spliceE={jE:#010x}")
print(f"-> {OUT}")
