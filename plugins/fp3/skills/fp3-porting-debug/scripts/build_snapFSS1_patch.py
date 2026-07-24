#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# snapFSS1 = privileged-side FRAMER-STATUS snapshot at the capability-timeout instant (staged 2026-07-14).
#
# WHY: two-sided AP-alias /dev/mem dumps proved the framer register file is byte-identical except its
# STATUS/output words (FRM_STAT group stays 0 on the DEAD side). But every prior framer read was AP-side
# through the LPASS_AP alias. This cave reads the framer MMIO **directly from the ADSP's own privileged
# view** (framer base = ctx+0x5c = 0xee140000) at the moment the capability wait times out, and re-reads
# the two dynamic status words after a short delay to catch a slow oscillation. It answers, from the
# co-processor side:
#   - Does the ADSP itself see FRM_STAT/FS/running = 0 (→ framer HW never started; wall confirmed
#     privileged-side, below the register file), OR does it see non-zero while the AP alias read 0
#     (→ the AP-alias/XPU read was masking a framer that DID partially come up → redirect to codec/bus)?
#   - Is the enable bit (+0x600) actually 1 and control (+0x610) actually 7 from the privileged side?
#   - Do the re-reads differ from the first reads (→ status is oscillating → PHY start-then-die)?
#
# SAFETY: reuses the PROVEN, verified FST1 splice site 0xf04d15bc (single-word packet `r0=memw(r16+0xe54)`,
# executed right after the wait returns; stock 0x9390f2a0). This is a bring-up-once code point (NOT the hot
# register HAL 0xf04bfe54 that stalled SSR in FWT1, folyt.152 / kernel-test rule 11). Reading framer MMIO
# from the fw is what the stock code already does here (0xf04d1530 calls the framer HAL-read), and the
# framer clock is running on the dead side (LPASS-CC RCG/CBCR enabled, folyt.142) → the read cannot hang.
#
# Stash (SMEM +0x640, AP reads PA 0x86300000+0x2ab0 -- same slot as FST1; onboard zeroes 0x60 there):
#   +0x00 'FSS1' | +0x04 wait-return(r0, sanity vs FST1 -2) | +0x08 framer base(ctx+0x5c, expect 0xee140000)
#   +0x0c fr+0x204 | +0x10 fr+0x404 FRM_STAT | +0x14 fr+0x430 | +0x18 fr+0x604 FS/SFS/MS | +0x1c fr+0x804 run-bit
#   +0x20 fr+0x600 enable(exp 1) | +0x24 fr+0x610 ctrl(exp 7) | +0x28 fr+0x604 re-read | +0x2c fr+0x804 re-read
#   +0x30 reached-count
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os
SRC=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT=f"{FP3_ROOT}/adsp-snapFSS1.mbn"
DELTA=0xf00fd000
def foff(va): return va-DELTA
SPLICE_VA=0xf04d15bc; STOCK=0x9390f2a0      # { r0 = memw(r16+#0xe54) }  (executed just after the wait returns)
CAVE_VA=0xf064e098                          # >=1024B contiguous zero in .text (shared w/ FST1; single-mbn)
RET_VA=0xf04d15c0
def enc_jump(pc,t):
    d=t-pc; assert d%4==0; s=d//4; assert -(1<<21)<=s<(1<<21)
    imm=s&0x3FFFFF; return ((0b0101100<<25)|(((imm>>13)&0x1FF)<<16)|(0b11<<14)|((imm&0x1FFF)<<1))&0xFFFFFFFF
ASM=fr"""
    // entry: r0 = wait-return value, r16 = ctx (PRESERVE r16). scratch r2,r3,r4,r5,r6.
    {{ r5 = r0 }}                                             // save wait-return before clobbering r0
    {{ r3 = ##0xf090fcd4 }}
    {{ r3 = memw(r3+#0) }}                                    // SMEM base ptr (ADSP side)
    {{ p0 = cmp.eq(r3,#0x0); if (p0.new) jump:nt .Lrep }}     // null -> just replicate + return
    {{ r3 = add(r3,#0x640) }}
    {{ r4 = ##0x31535346 }}                                   // 'FSS1'
    {{ memw(r3+#0x00) = r4 }}
    {{ memw(r3+#0x04) = r5 }}                                 // wait-return (r0 at entry)
    {{ r2 = memw(r16+#0x5c) }}                                // framer base (0xee140000)
    {{ memw(r3+#0x08) = r2 }}
    {{ r4 = memw(r2+#0x204) }}
    {{ memw(r3+#0x0c) = r4 }}
    {{ r4 = memw(r2+#0x404) }}                                // FRM_STAT
    {{ memw(r3+#0x10) = r4 }}
    {{ r4 = memw(r2+#0x430) }}
    {{ memw(r3+#0x14) = r4 }}
    {{ r4 = memw(r2+#0x604) }}                                // FS/SFS/MS
    {{ memw(r3+#0x18) = r4 }}
    {{ r4 = memw(r2+#0x804) }}                                // running bit
    {{ memw(r3+#0x1c) = r4 }}
    {{ r4 = memw(r2+#0x600) }}                                // enable (expect 1)
    {{ memw(r3+#0x20) = r4 }}
    {{ r4 = memw(r2+#0x610) }}                                // control (expect 7)
    {{ memw(r3+#0x24) = r4 }}
    {{ r6 = #0x800 }}                                         // short delay to sample a second time
.Ldly:
    {{ r6 = add(r6,#-0x1); p0 = cmp.gt(r6,#0x1); if (p0.new) jump:nt .Ldly }}
    {{ r4 = memw(r2+#0x604) }}                                // FS/SFS/MS re-read
    {{ memw(r3+#0x28) = r4 }}
    {{ r4 = memw(r2+#0x804) }}                                // running bit re-read
    {{ memw(r3+#0x2c) = r4 }}
    {{ r4 = memw(r3+#0x30) }}                                 // reached-count++
    {{ r4 = add(r4,#0x1) }}
    {{ memw(r3+#0x30) = r4 }}
.Lrep:
    {{ r0 = memw(r16+#0xe54) }}                               // replicate spliced stock instruction
    {{ r5 = ##{RET_VA:#010x} }}
    {{ jumpr r5 }}
"""
here=os.path.dirname(os.path.abspath(__file__))
a=os.path.join(here,"snapFSS1.s");o=os.path.join(here,"snapFSS1.o");b=os.path.join(here,"snapFSS1.bin")
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
