#!/usr/bin/env python3
# snapCKB3 = framer BRANCH-CLOCK (CBCR) capture (folyt.121 next: the real gate).
# folyt.119-121: the framer-clock RCGR (base 0xee012000) is byte-identical working<->dead
# (CMD=0x80000000, CFG src=5/div=9); CMD ROOT_EN(bit1)=0 => this RCG is gated at the BRANCH
# clock (CBCR), a SEPARATE register. From the handle layout, +0x1c = a 2nd MMIO ptr (ibit_clk
# sibling had 0xee026004 there) = the CBCR. Splice pkt5 @ 0xf04df260 (r0=handle live), filter
# handle by the framer registry-entry ptr 0xf0821de8, capture handle[0x0c..0x20] to pin the
# CBCR address, then GUARDED-read the CBCR value (only if in the LPASS-CC range 0xee0xxxxx —
# always-accessible CC regs; guard prevents a wild deref on the dead side). Same proven pkt5
# splice + trampolines as snapCKB (offline-verified). Magic 'CKB3'.
#   +0x00 'CKB3' +0x04 handle +0x08 h+0x0c(ops) +0x0c h+0x10 +0x10 h+0x14 +0x14 h+0x18
#   +0x18 ★h+0x1c(CBCR addr) +0x1c h+0x20 +0x20 CBCR=memw([h+0x1c]+0) +0x24 memw([h+0x1c]+4)
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os
SRC=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT=f"{FP3_ROOT}/adsp-snapCKB3.mbn"
DELTA=0xf00fd000
SPLICE_VA=0xf04df260; SPLICE_FOFF=SPLICE_VA-DELTA; STOCK=struct.pack("<I",0x91804062)
CAVE_VA=0xf064e098;   CAVE_FOFF=CAVE_VA-DELTA
RET_CONT=0xf04df268; RET_TAKEN=0xf04df2ec
def enc_jump(pc,t):
    d=t-pc; assert d%4==0; s=d//4; assert -(1<<21)<=s<(1<<21)
    imm=s&0x3FFFFF; return ((0b0101100<<25)|(((imm>>13)&0x1FF)<<16)|(0b11<<14)|((imm&0x1FFF)<<1))&0xFFFFFFFF
ASM=r"""
    { r1 = ##0xf090fcd4 }
    { r1 = memw(r1+#0) }
    { p0 = cmp.eq(r1,#0x0); if (p0.new) jump:nt .Lexit }
    { r1 = add(r1,#0x640) }
    // scan handle[0..0x40] for framer registry-entry ptr 0xf0821de8
    { r3 = r0 }
    { r4 = #0x0 }
.Lscan:
    { r5 = memw(r3+#0x0) }
    { p0 = cmp.eq(r5,##0xf0821de8); if (p0.new) jump:nt .Lhit }
    { r3 = add(r3,#0x4) ; r4 = add(r4,#0x1) }
    { p0 = cmp.eq(r4,#0x10); if (!p0.new) jump:nt .Lscan }
    { jump .Lexit }
.Lhit:
    { r2 = ##0x33424b43 }                 // 'CKB3'
    { memw(r1+#0x00) = r2 }
    { memw(r1+#0x04) = r0 }               // handle
    { r2 = memw(r0+#0x0c) } { memw(r1+#0x08) = r2 }   // ops-vtable (sanity)
    { r2 = memw(r0+#0x10) } { memw(r1+#0x0c) = r2 }
    { r2 = memw(r0+#0x14) } { memw(r1+#0x10) = r2 }
    { r2 = memw(r0+#0x18) } { memw(r1+#0x14) = r2 }
    { r5 = memw(r0+#0x1c) } { memw(r1+#0x18) = r5 }   // ★ CBCR addr candidate
    { r2 = memw(r0+#0x20) } { memw(r1+#0x1c) = r2 }
    // GUARDED CBCR read: only if 0xee000000 <= r5 < 0xee100000 (LPASS-CC always-on range)
    { r2 = ##0xee000000 }
    { p0 = cmp.gtu(r2,r5); if (p0.new) jump:nt .Lexit }   // r5 < 0xee000000 -> skip
    { r2 = ##0xee100000 }
    { p0 = cmp.gtu(r2,r5); if (!p0.new) jump:nt .Lexit }  // r5 >= 0xee100000 -> skip
    { r2 = memw(r5+#0x00) } { memw(r1+#0x20) = r2 }   // ★ CBCR value (bit0=ENABLE, bit31=CLK_OFF)
    { r2 = memw(r5+#0x04) } { memw(r1+#0x24) = r2 }
.Lexit:
    { r2 = memw(r0+#0xc) }
    { p0 = cmp.eq(r2,#0x0) }
    { if (p0) jump:nt .Ltramp_taken }
    { jump .Ltramp_fall }
.Ltramp_taken:
    { r17 = r17 }
.Ltramp_fall:
    { r17 = r17 }
"""
here=os.path.dirname(os.path.abspath(__file__))
a=os.path.join(here,"snapCKB3.s");o=os.path.join(here,"snapCKB3.o");b=os.path.join(here,"snapCKB3.bin")
open(a,"w").write(ASM)
MC=subprocess.run(["bash","-lc","command -v llvm-mc-21 || command -v llvm-mc"],capture_output=True,text=True).stdout.strip()
OC=subprocess.run(["bash","-lc","command -v llvm-objcopy-21 || command -v llvm-objcopy"],capture_output=True,text=True).stdout.strip()
subprocess.run([MC,"--arch=hexagon","--mcpu=hexagonv60","--filetype=obj",a,"-o",o],check=True)
subprocess.run([OC,"-O","binary","--only-section=.text",o,b],check=True)
cave=bytearray(open(b,"rb").read())
n=len(cave); pos_taken=n-8; pos_fall=n-4
cave[pos_taken:pos_taken+4]=struct.pack("<I",enc_jump(CAVE_VA+pos_taken,RET_TAKEN))
cave[pos_fall:pos_fall+4]=struct.pack("<I",enc_jump(CAVE_VA+pos_fall,RET_CONT))
spl=enc_jump(SPLICE_VA,CAVE_VA)
data=bytearray(open(SRC,"rb").read())
assert bytes(data[SPLICE_FOFF:SPLICE_FOFF+4])==STOCK, "splice stock mismatch"
assert data[CAVE_FOFF:CAVE_FOFF+len(cave)]==b"\x00"*len(cave), "cave region not zero/too small"
data[CAVE_FOFF:CAVE_FOFF+len(cave)]=cave
data[SPLICE_FOFF:SPLICE_FOFF+4]=struct.pack("<I",spl)
open(OUT,"wb").write(data)
print(f"cave {len(cave)}B splice={spl:#010x} taken@{pos_taken}->{RET_TAKEN:#x} fall@{pos_fall}->{RET_CONT:#x} -> {OUT}")
