#!/usr/bin/env python3
# snapCKB6 = LEVER test: force the framer branch CBCR (0xee00d01c) ENABLE bit on and see if the
# framer frames (folyt.124 -> marker-vs-lever). folyt.122: framer CBCR reads 0x80000000 (ENABLE=0,
# CLK_OFF=1) = off. The CBCR-enable code is elusive (runtime-dispatched, accessors don't run,
# static caller search fails). So instead of finding it, TEST causality: at the framer clock
# enable-method (pkt5 splice 0xf04df260, r0=handle, filter handle+0x04==0xf0821de8), set
# memw(memw(handle+0x1c)) |= 1 (force CBCR ENABLE). Capture pre/post. Then check dmesg: if the NGD
# STATUS leaves 0x40c / framer frames -> the off CBCR was the cause = fix candidate; if still dead
# -> the branch clock is not the sole cause. Guarded (CBCR addr must be in the LPASS-CC range, a
# PROVEN-safe addr). Same pkt5 splice+trampolines as CKB3 (offline-verified). Magic 'CKB6'.
#   +0x00 'CKB6' +0x04 handle +0x08 CBCR addr +0x0c CBCR pre +0x10 CBCR post
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os
SRC=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT=f"{FP3_ROOT}/adsp-snapCKB6.mbn"
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
    { r3 = r0 }
    { r4 = #0x0 }
.Lscan:
    { r5 = memw(r3+#0x0) }
    { p0 = cmp.eq(r5,##0xf0821de8); if (p0.new) jump:nt .Lhit }
    { r3 = add(r3,#0x4) ; r4 = add(r4,#0x1) }
    { p0 = cmp.eq(r4,#0x10); if (!p0.new) jump:nt .Lscan }
    { jump .Lexit }
.Lhit:
    { r5 = memw(r0+#0x1c) }           // CBCR addr = handle+0x1c
    { r2 = ##0xee000000 }
    { p0 = cmp.gtu(r2,r5); if (p0.new) jump:nt .Lexit }   // r5 < 0xee000000 -> skip
    { r2 = ##0xee100000 }
    { p0 = cmp.gtu(r2,r5); if (!p0.new) jump:nt .Lexit }  // r5 >= 0xee100000 -> skip
    { r2 = ##0x36424b43 }             // 'CKB6'
    { memw(r1+#0x00) = r2 }
    { memw(r1+#0x04) = r0 }           // handle
    { memw(r1+#0x08) = r5 }           // CBCR addr
    { r4 = memw(r5+#0x0) }            // CBCR pre
    { memw(r1+#0x0c) = r4 }
    { r4 = or(r4,#0x1) }             // set ENABLE bit0
    { memw(r5+#0x0) = r4 }           // ★ FORCE CBCR ENABLE
    { r4 = memw(r5+#0x0) }           // CBCR post
    { memw(r1+#0x10) = r4 }
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
a=os.path.join(here,"snapCKB6.s");o=os.path.join(here,"snapCKB6.o");b=os.path.join(here,"snapCKB6.bin")
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
