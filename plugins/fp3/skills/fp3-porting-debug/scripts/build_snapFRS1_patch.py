#!/usr/bin/env python3
# snapFRS1 = framer HW register-state capture at the enumerate-timeout handler (folyt.131, C2).
# mode=active (FMD2) + clock runs (CKB9) yet no framing => read the framer HW block directly.
# Framer MMIO base = memw(ctx+0x5c); status reg = base+0x604 (FS bit0xb / SFS 0xc / MS 0xd) — proven
# derefable by 0xf04c0218/0224/0230. Splice the enumerate-timeout fn PROLOGUE 0xf04c3540 `{r16=r0}`
# (stock 0x7060c010, single word, ctx=r0 fresh) -> capture -> replicate r16=r0 -> return 0xf04c3544.
# This fn runs on the failing bring-up (it logs "Hardware failed to enumerate after timeout"); at that
# point the framer clock runs (folyt.128d) so the MMIO read is safe. Base null-guarded; if an adjacent
# offset were unsafe the ADSP faults and SSR-heals (bounded probe, recoverable).
# Stash (SMEM +0x640): +0x00 'FRS1' | +0x04 ctx | +0x08 memw(ctx+0x78) mode | +0x0c memw(ctx+0xdfc) gate
#   | +0x10 memw(ctx+0xe00) DevId | +0x14 framer_base=memw(ctx+0x5c) | +0x18 base+0x600 | +0x1c base+0x604
#   | +0x20 base+0x608 | +0x24 base+0x60c | +0x28 0xF00D (reached-after-MMIO marker)
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os
SRC=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT=f"{FP3_ROOT}/adsp-snapFRS1.mbn"
DELTA=0xf00fd000
def foff(va): return va-DELTA
SPLICE_VA=0xf04c3540; STOCK=0x7060c010          # { r16 = r0 }
CAVE_VA=0xf064e098
RET_VA=0xf04c3544
def enc_jump(pc,t):
    d=t-pc; assert d%4==0; s=d//4; assert -(1<<21)<=s<(1<<21), f"range {s}"
    imm=s&0x3FFFFF; return ((0b0101100<<25)|(((imm>>13)&0x1FF)<<16)|(0b11<<14)|((imm&0x1FFF)<<1))&0xFFFFFFFF
ASM=fr"""
    // entry: r0=ctx (incoming). scratch r3,r4,r5; preserve r0.
    {{ r3 = ##0xf090fcd4 }}
    {{ r3 = memw(r3+#0) }}
    {{ p0 = cmp.eq(r3,#0x0); if (p0.new) jump:nt .Lset }}
    {{ r3 = add(r3,#0x640) }}
    {{ r4 = ##0x31535246 }}                 // 'FRS1'
    {{ memw(r3+#0x00) = r4 }}
    {{ memw(r3+#0x04) = r0 }}
    {{ r4 = memw(r0+#0x78) }}
    {{ memw(r3+#0x08) = r4 }}
    {{ r4 = memw(r0+#0xdfc) }}
    {{ memw(r3+#0x0c) = r4 }}
    {{ r4 = memw(r0+#0xe00) }}
    {{ memw(r3+#0x10) = r4 }}
    {{ r5 = memw(r0+#0x5c) }}               // framer MMIO base
    {{ memw(r3+#0x14) = r5 }}
    {{ p0 = cmp.eq(r5,#0x0); if (p0.new) jump:nt .Lset }}   // null-guard the MMIO reads
    {{ r4 = memw(r5+#0x600) }}
    {{ memw(r3+#0x18) = r4 }}
    {{ r4 = memw(r5+#0x604) }}
    {{ memw(r3+#0x1c) = r4 }}
    {{ r4 = memw(r5+#0x608) }}
    {{ memw(r3+#0x20) = r4 }}
    {{ r4 = memw(r5+#0x60c) }}
    {{ memw(r3+#0x24) = r4 }}
    {{ r4 = ##0x0000f00d }}
    {{ memw(r3+#0x28) = r4 }}
.Lset:
    {{ r16 = r0 }}
    {{ r5 = ##{RET_VA:#010x} }}
    {{ jumpr r5 }}
"""
here=os.path.dirname(os.path.abspath(__file__))
a=os.path.join(here,"snapFRS1.s");o=os.path.join(here,"snapFRS1.o");b=os.path.join(here,"snapFRS1.bin")
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
