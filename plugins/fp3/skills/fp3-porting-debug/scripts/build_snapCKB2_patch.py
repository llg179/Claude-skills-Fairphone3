#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# snapCKB2 = POST-ENABLE framer-clock RCGR capture (folyt.119 phase-4, the latch test).
# Phase-3 (snapCKB) spliced at 0xf04df260 (pre-write) -> saw reset state CMD=0x80000000 (ROOT_OFF).
# The method then writes CFG/M/N/D and SPIN-POLLS CMD_RCGR bit0(UPDATE) at 0xf04df2e4<->0xf04df2e8
# until it clears (ADSP does NOT hang -> UPDATE clears -> update completes). This splices the
# poll-read 0xf04df2e4 (`r2=memw(r17+0)`, single-word pkt) and, ONLY for the framer base
# r17==0xee012000 (known from phase-2), captures the settled RCGR block. Decisive bit: CMD_RCGR
# bit31 = ROOT_OFF (1=root clock off). If dead-side ROOT_OFF stays 1 post-enable => the RCG root
# never turns on => parent PLL/source absent = the physical divergence. Single external exit
# (0xf04df2e8), snapCGP-style hand-encoded tail jump. Magic 'CKB2' written LAST (completion).
#   +0x30 CMD_RCGR +0x34 CFG_RCGR +0x38 M +0x3c N +0x40 D +0x44 'CKB2'
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os
SRC=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT=f"{FP3_ROOT}/adsp-snapCKB2.mbn"
DELTA=0xf00fd000
SPLICE_VA=0xf04df2e4; SPLICE_FOFF=SPLICE_VA-DELTA; STOCK=struct.pack("<I",0x9191c002)
CAVE_VA=0xf064e098;   CAVE_FOFF=CAVE_VA-DELTA
RET_VA=0xf04df2e8
FRAMER_BASE=0xee012000
def enc_jump(pc,t):
    d=t-pc; assert d%4==0; s=d//4; assert -(1<<21)<=s<(1<<21)
    imm=s&0x3FFFFF; return ((0b0101100<<25)|(((imm>>13)&0x1FF)<<16)|(0b11<<14)|((imm&0x1FFF)<<1))&0xFFFFFFFF
ASM=r"""
    { p0 = cmp.eq(r17,##0xee012000); if (!p0.new) jump:nt .Lrep }   // only the framer clock
    { r1 = ##0xf090fcd4 }
    { r1 = memw(r1+#0) }
    { p0 = cmp.eq(r1,#0x0); if (p0.new) jump:nt .Lrep }
    { r1 = add(r1,#0x640) }
    { r2 = memw(r17+#0x00) } { memw(r1+#0x30) = r2 }   // CMD_RCGR (settled: bit31=ROOT_OFF)
    { r2 = memw(r17+#0x04) } { memw(r1+#0x34) = r2 }   // CFG_RCGR (src-sel[10:8], div[4:0])
    { r2 = memw(r17+#0x08) } { memw(r1+#0x38) = r2 }   // M
    { r2 = memw(r17+#0x0c) } { memw(r1+#0x3c) = r2 }   // N
    { r2 = memw(r17+#0x10) } { memw(r1+#0x40) = r2 }   // D
    { r2 = ##0x32424b43 } { memw(r1+#0x44) = r2 }      // 'CKB2' completion sentinel (LAST)
.Lrep:
    { r2 = memw(r17+#0x00) }                           // replicate original poll-read
"""
here=os.path.dirname(os.path.abspath(__file__))
a=os.path.join(here,"snapCKB2.s");o=os.path.join(here,"snapCKB2.o");b=os.path.join(here,"snapCKB2.bin")
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
print(f"cave {len(cave)}B splice={spl:#010x} ret={ret:#010x} framer_base={FRAMER_BASE:#x} -> {OUT}")
