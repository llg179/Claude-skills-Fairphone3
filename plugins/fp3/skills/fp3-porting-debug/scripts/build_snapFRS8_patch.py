#!/usr/bin/env python3
# snapFRS8 = FILTERED ctx-struct scan (folyt.135->136, C1/C3 target-finder).
# folyt.135 proved the framer base 0xee140000 / clock 0xee012014 are NOT firmware literals -- they are
# config/property-supplied at runtime and live in the framer ctx struct (framer base = memw(ctx+0x5c), FRS1).
# folyt.136 (FRS7): the framer ctx holds ONLY the framer base (0xee140000) as a DIRECT LPASS pointer in
# ctx+0..0xdfc -> the clock/pad must be reached INDIRECTLY via a parent/device struct pointer (a DDR/image
# address, filtered OUT by FRS7's 0xee-only test). FRS8 broadens the filter to ALSO catch ADSP image/data
# pointers (val & 0xff000000 == 0xf0000000) -> surfaces the parent-struct pointer to chase next. Instead: at the both-sides mode-update
# anchor 0xf04c36e8 (r0 = framer ctx; FMD2 proved ctx+0x78 = mode there, same struct as FRS1's r0), walk
# ctx+0x00..0xdfc (FRS1-proven-safe DDR range -- these are PLAIN MEMORY reads of pointer *values*, no MMIO
# deref, zero bus-hazard) and stash every field whose value is in the LPASS MMIO range (val & 0xff000000 ==
# 0xee000000). That reveals EVERY base pointer the framer holds: framer base @+0x5c PLUS any clock/pad base
# at another offset -> the C1 (second clock) / C3 (PHY-pad) target address, both-sides-comparable.
# Splice/ret/cave identical to FRS6 (both-sides anchor). Stash (SMEM +0x640, AP reads PA 0x86300000+0x2ab0):
#   +0x00 'FRS8' | +0x04 count | +0x08.. up to 8 pairs of (offset,value) [8 bytes each].
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os
SRC=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT=f"{FP3_ROOT}/adsp-snapFRS8.mbn"
DELTA=0xf00fd000
def foff(va): return va-DELTA
SPLICE_VA=0xf04c36e8; STOCK=0x7060c010     # { r16 = r0 }  (mode-update entry, FMD2/FRS5/FRS6-proven; r0=ctx)
CAVE_VA=0xf064e098
RET_VA=0xf04c36ec
SCAN_MAX=0xdfc                              # last ctx offset read (FRS1 proved ctx+0xdfc/0xe00 safe)
MAX_PAIRS=8
def enc_jump(pc,t):
    d=t-pc; assert d%4==0; s=d//4; assert -(1<<21)<=s<(1<<21)
    imm=s&0x3FFFFF; return ((0b0101100<<25)|(((imm>>13)&0x1FF)<<16)|(0b11<<14)|((imm&0x1FFF)<<1))&0xFFFFFFFF
ASM=fr"""
    // entry: r0 = framer ctx (PRESERVE for replication). scratch r3,r4,r5,r6,r7,r8.
    {{ r3 = ##0xf090fcd4 }}
    {{ r3 = memw(r3+#0) }}
    {{ p0 = cmp.eq(r3,#0x0); if (p0.new) jump:nt .Lrep }}     // SMEM ptr null -> can't stash, just return
    {{ r3 = add(r3,#0x640) }}                                 // stash base
    {{ r4 = ##0x38535246 }}                                   // 'FRS8'
    {{ memw(r3+#0x00) = r4 }}
    {{ r6 = #0 }}                                             // pair count
    {{ p0 = cmp.eq(r0,#0x0); if (p0.new) jump:nt .Ldone }}    // ctx null -> store count=0
    {{ r7 = #0 }}                                             // ctx offset iterator
.Lloop:
    {{ r5 = memw(r0+r7<<#0) }}                                // val = *(ctx + off)  [DDR read, not MMIO]
    {{ r4 = and(r5,##0xff000000) }}
    {{ p0 = cmp.eq(r4,##0xee000000) }}                               // A: LPASS MMIO pointer (0xee..)
    {{ p1 = cmp.eq(r4,##0xf0000000) }}                               // B: ADSP image/data pointer (0xf0..)
    {{ p0 = or(p0,p1) }}
    {{ if (!p0) jump:nt .Lnext }}                                    // neither -> skip
    {{ p1 = cmp.gtu(r6,#0x7); if (p1.new) jump:nt .Lnext }}   // already have MAX_PAIRS=8 -> skip store
    {{ r4 = asl(r6,#0x3) }}                                   // pair byte-offset = count*8
    {{ r4 = add(r4,#0x08) }}                                  // + 8-byte header (magic+count)
    {{ r8 = add(r3,r4) }}
    {{ memw(r8+#0x00) = r7 }}                                 // store ctx offset
    {{ memw(r8+#0x04) = r5 }}                                 // store LPASS pointer value
    {{ r6 = add(r6,#0x1) }}
.Lnext:
    {{ r7 = add(r7,#0x4) }}
    {{ p0 = cmp.gtu(r7,##{SCAN_MAX:#x}); if (!p0.new) jump:nt .Lloop }}   // loop while off <= SCAN_MAX
.Ldone:
    {{ memw(r3+#0x04) = r6 }}                                 // count
.Lrep:
    {{ r16 = r0 }}                                            // replicate spliced word
    {{ r5 = ##{RET_VA:#010x} }}
    {{ jumpr r5 }}
"""
here=os.path.dirname(os.path.abspath(__file__))
a=os.path.join(here,"snapFRS8.s");o=os.path.join(here,"snapFRS8.o");b=os.path.join(here,"snapFRS8.bin")
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
print(f"cave={len(cave)}B@{CAVE_VA:#x} splice={j:#010x}@{SPLICE_VA:#x} ret={RET_VA:#x} scan=0..{SCAN_MAX:#x} -> {OUT}")
