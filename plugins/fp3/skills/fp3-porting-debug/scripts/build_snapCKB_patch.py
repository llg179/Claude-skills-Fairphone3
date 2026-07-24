#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# snapCKB = runtime capture of the framer-clock (0x12014) RCGR/CBCR MMIO BASE (folyt.118 next).
# (a) proved: enable-method 0xf04df244 reads r17=memw(handle+0)=base (data field, NO immediate).
# This splices at 0xf04df260 (pkt5), where r0=handle AND r17=base are both live (r0 is clobbered
# only at 0xf04df268). It scans handle[0..0x40] for the framer clock ID 0x12014; on a hit it
# records base=memw(handle+0) WITHOUT dereferencing it (CGP2b lesson: never deref an uncertain
# ptr on the dead side). An always-on SMPL block records the last invocation's handle layout so
# we learn where the ID lives even if the scan misses. Faithful replication of pkt5's conditional
# exit via two trampolines: r2=memw(r0+0xc); if(r2==0) jump 0xf04df2ec else jump 0xf04df268.
# Stash *(0xf090fcd4)+0x640. Magic 'CKB1'(hit) / 'SMPL'(sample). SAFE: no base deref, guarded.
#   +0x00 'CKB1' +0x04 handle +0x08 ★BASE=memw(h+0) +0x0c matched-word-index
#   +0x10 h+0x04 +0x14 h+0x08 +0x18 h+0x0c
#   +0x20 'SMPL' +0x24 handle +0x28 base  +0x2c..+0x48 handle[0x00..0x1c] (8 words)
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os
SRC=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT=f"{FP3_ROOT}/adsp-snapCKB.mbn"
DELTA=0xf00fd000
SPLICE_VA=0xf04df260; SPLICE_FOFF=SPLICE_VA-DELTA; STOCK=struct.pack("<I",0x91804062)
CAVE_VA=0xf064e098;   CAVE_FOFF=CAVE_VA-DELTA
RET_CONT=0xf04df268   # fall-through (r2!=0): pkt6
RET_TAKEN=0xf04df2ec  # taken (r2==0): the method's 0xa8 error/exit target
def enc_jump(pc,t):
    d=t-pc; assert d%4==0; s=d//4; assert -(1<<21)<=s<(1<<21), f"jump range {s}"
    imm=s&0x3FFFFF; return ((0b0101100<<25)|(((imm>>13)&0x1FF)<<16)|(0b11<<14)|((imm&0x1FFF)<<1))&0xFFFFFFFF
ASM=r"""
    { r1 = ##0xf090fcd4 }
    { r1 = memw(r1+#0) }
    { p0 = cmp.eq(r1,#0x0); if (p0.new) jump:nt .Lexit }
    { r1 = add(r1,#0x640) }               // r1 = SMEM stash
    // ---- scan: find framer registry-entry ptr 0xf0821de8 in handle[0..0x40] ----
    // (folyt.119: runtime handle+0x04 = registry-entry ptr; framer entry=0xf0821de8, id 0x12014)
    { r3 = r0 }
    { r4 = #0x0 }
.Lscan:
    { r5 = memw(r3+#0x0) }
    { p0 = cmp.eq(r5,##0xf0821de8); if (p0.new) jump:nt .Lhit }
    { r3 = add(r3,#0x4) ; r4 = add(r4,#0x1) }
    { p0 = cmp.eq(r4,#0x10); if (!p0.new) jump:nt .Lscan }
    { jump .Lexit }                       // no framer this invocation -> leave CKB1 slot untouched
.Lhit:
    // BASE=0xee012000 is a clock-controller reg (always accessible; the method itself
    // reads/writes memw(r17+..) 2 packets later) -> safe to read the RCGR block here.
    { r2 = ##0x31424b43 }                 // 'CKB1'
    { memw(r1+#0x00) = r2 }
    { memw(r1+#0x04) = r0 }               // handle
    { memw(r1+#0x08) = r17 }              // ★ BASE = memw(handle+0)
    { memw(r1+#0x0c) = r4 }               // matched word index
    { r2 = memw(r17+#0x00) } { memw(r1+#0x10) = r2 }   // CMD_RCGR
    { r2 = memw(r17+#0x04) } { memw(r1+#0x14) = r2 }   // CFG_RCGR (src-select+div)
    { r2 = memw(r17+#0x08) } { memw(r1+#0x18) = r2 }   // M
    { r2 = memw(r17+#0x0c) } { memw(r1+#0x1c) = r2 }   // N
    { r2 = memw(r17+#0x10) } { memw(r1+#0x20) = r2 }   // D
    { r2 = memw(r17+#0x14) } { memw(r1+#0x24) = r2 }   // (next reg)
    { r2 = memw(r0+#0x08) }  { memw(r1+#0x28) = r2 }   // handle+0x08 (state)
.Lexit:
    // ---- faithful replication of pkt5: r2=memw(r0+0xc); if(r2==0) ->0xf04df2ec else ->0xf04df268
    { r2 = memw(r0+#0xc) }
    { p0 = cmp.eq(r2,#0x0) }
    { if (p0) jump:nt .Ltramp_taken }
    { jump .Ltramp_fall }
.Ltramp_taken:
    { r17 = r17 }                         // PATCHED -> jump RET_TAKEN (0xf04df2ec)
.Ltramp_fall:
    { r17 = r17 }                         // PATCHED -> jump RET_CONT  (0xf04df268)
"""
here=os.path.dirname(os.path.abspath(__file__))
a=os.path.join(here,"snapCKB.s");o=os.path.join(here,"snapCKB.o");b=os.path.join(here,"snapCKB.bin")
open(a,"w").write(ASM)
MC=subprocess.run(["bash","-lc","command -v llvm-mc-21 || command -v llvm-mc"],capture_output=True,text=True).stdout.strip()
OC=subprocess.run(["bash","-lc","command -v llvm-objcopy-21 || command -v llvm-objcopy"],capture_output=True,text=True).stdout.strip()
subprocess.run([MC,"--arch=hexagon","--mcpu=hexagonv60","--filetype=obj",a,"-o",o],check=True)
subprocess.run([OC,"-O","binary","--only-section=.text",o,b],check=True)
cave=bytearray(open(b,"rb").read())
# patch the two trailing trampoline words (last=fall, second-last=taken)
n=len(cave)
pos_taken=n-8; pos_fall=n-4
cave[pos_taken:pos_taken+4]=struct.pack("<I",enc_jump(CAVE_VA+pos_taken,RET_TAKEN))
cave[pos_fall:pos_fall+4]=struct.pack("<I",enc_jump(CAVE_VA+pos_fall,RET_CONT))
spl=enc_jump(SPLICE_VA,CAVE_VA)
data=bytearray(open(SRC,"rb").read())
assert bytes(data[SPLICE_FOFF:SPLICE_FOFF+4])==STOCK, "splice stock mismatch"
assert data[CAVE_FOFF:CAVE_FOFF+len(cave)]==b"\x00"*len(cave), "cave region not zero/too small"
data[CAVE_FOFF:CAVE_FOFF+len(cave)]=cave
data[SPLICE_FOFF:SPLICE_FOFF+4]=struct.pack("<I",spl)
open(OUT,"wb").write(data)
print(f"cave {len(cave)}B  splice={spl:#010x} taken@{pos_taken}->{RET_TAKEN:#x} fall@{pos_fall}->{RET_CONT:#x} -> {OUT}")
