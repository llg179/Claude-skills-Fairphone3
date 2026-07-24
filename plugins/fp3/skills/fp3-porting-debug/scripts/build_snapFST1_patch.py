#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# snapFST1 = LIVE framing-START capability-wait TRACE (folyt.148->149).
# The framing-START routine 0xf04d14cc posts capability request(s) (opcodes 0xf/0x10 via the ctx+0xe08
# callable, in 0xf04d166c) then blocks on the QuRT queue-recv-with-timeout 0xf0174eb4 (r2=#0x1388=5000ms).
# The coredump only shows the RESTING ctx (tea-leaves: 0x80000022 is likely a record type-tag, not a clean
# per-exchange status). This cave captures the LIVE result of the wait, on the DEAD side, during SSR re-init:
# splice at 0xf04d15bc (single-word packet `r0=memw(r16+0xe54)`, executed RIGHT AFTER the wait returns, so
# r0 still holds the WAIT RETURN VALUE and r16=ctx). Stash r0 + the status fields, then replicate + return.
# Answers: did the wait return timeout vs error vs success, and what did ctx+0xe54/eb0/eb4 hold live.
# Stash (SMEM +0x640, AP reads PA 0x86300000+0x2ab0):
#   +0x00 'FST1' | +0x04 wait-return(r0) | +0x08 ctx+0xe54 | +0x0c ctx+0xe0c | +0x10 ctx+0xe08
#   +0x14 ctx+0xeb0 | +0x18 ctx+0xeb4 | +0x1c ctx+0x5c(framer base) | +0x20 reached-count
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os
SRC=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT=f"{FP3_ROOT}/adsp-snapFST1.mbn"
DELTA=0xf00fd000
def foff(va): return va-DELTA
SPLICE_VA=0xf04d15bc; STOCK=0x9390f2a0      # { r0 = memw(r16+#0xe54) }  (executed just after the wait returns)
CAVE_VA=0xf064e098
RET_VA=0xf04d15c0
def enc_jump(pc,t):
    d=t-pc; assert d%4==0; s=d//4; assert -(1<<21)<=s<(1<<21)
    imm=s&0x3FFFFF; return ((0b0101100<<25)|(((imm>>13)&0x1FF)<<16)|(0b11<<14)|((imm&0x1FFF)<<1))&0xFFFFFFFF
ASM=fr"""
    // entry: r0 = wait-return value, r16 = ctx (PRESERVE r16). scratch r3,r4,r5.
    {{ r5 = r0 }}                                             // save wait-return before clobbering r0
    {{ r3 = ##0xf090fcd4 }}
    {{ r3 = memw(r3+#0) }}                                    // SMEM base ptr (ADSP side)
    {{ p0 = cmp.eq(r3,#0x0); if (p0.new) jump:nt .Lrep }}     // null -> just replicate + return
    {{ r3 = add(r3,#0x640) }}
    {{ r4 = ##0x31545346 }}                                   // 'FST1'
    {{ memw(r3+#0x00) = r4 }}
    {{ memw(r3+#0x04) = r5 }}                                 // wait-return (r0 at entry)
    {{ r4 = memw(r16+#0xe54) }}
    {{ memw(r3+#0x08) = r4 }}
    {{ r4 = memw(r16+#0xe0c) }}
    {{ memw(r3+#0x0c) = r4 }}
    {{ r4 = memw(r16+#0xe08) }}
    {{ memw(r3+#0x10) = r4 }}
    {{ r4 = memw(r16+#0xeb0) }}
    {{ memw(r3+#0x14) = r4 }}
    {{ r4 = memw(r16+#0xeb4) }}
    {{ memw(r3+#0x18) = r4 }}
    {{ r4 = memw(r16+#0x5c) }}
    {{ memw(r3+#0x1c) = r4 }}
    {{ r4 = memw(r3+#0x20) }}                                 // reached-count++
    {{ r4 = add(r4,#0x1) }}
    {{ memw(r3+#0x20) = r4 }}
.Lrep:
    {{ r0 = memw(r16+#0xe54) }}                               // replicate spliced stock instruction
    {{ r5 = ##{RET_VA:#010x} }}
    {{ jumpr r5 }}
"""
here=os.path.dirname(os.path.abspath(__file__))
a=os.path.join(here,"snapFST1.s");o=os.path.join(here,"snapFST1.o");b=os.path.join(here,"snapFST1.bin")
open(a,"w").write(ASM)
MC=subprocess.run(["bash","-lc","command -v llvm-mc-21 || command -v llvm-mc"],capture_output=True,text=True).stdout.strip()
OC=subprocess.run(["bash","-lc","command -v llvm-objcopy-21 || command -v llvm-objcopy"],capture_output=True,text=True).stdout.strip()
subprocess.run([MC,"--arch=hexagon","--mcpu=hexagonv60","--filetype=obj",a,"-o",o],check=True)
subprocess.run([OC,"-O","binary","--only-section=.text",o,b],check=True)
cave=open(b,"rb").read()
data=bytearray(open(SRC,"rb").read())
got=struct.unpack_from("<I",data,foff(SPLICE_VA))[0]
assert got==STOCK, f"splice stock mismatch: {got:#x} != {STOCK:#x}"
assert data[foff(CAVE_VA):foff(CAVE_VA)+len(cave)]==b"\x00"*len(cave), "cave region not zero"
data[foff(CAVE_VA):foff(CAVE_VA)+len(cave)]=cave
j=enc_jump(SPLICE_VA,CAVE_VA); data[foff(SPLICE_VA):foff(SPLICE_VA)+4]=struct.pack("<I",j)
open(OUT,"wb").write(data)
print(f"cave={len(cave)}B@{CAVE_VA:#x} splice={j:#010x}@{SPLICE_VA:#x} ret={RET_VA:#x} -> {OUT}")
