#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# HWL0 = the HalHwIo/PLL-lock LEAF trace (deeper than snapT3's config-group splice).
# Splices the CGC-enable+poll leaf's RETURN packet (f019abb0, the dead immext word of
# {immext; r0=0; jump 0xf001a864}) and, for EVERY clock enabled through this leaf,
# ring-captures the physical-realization state that the config-group path only *delegates*:
#   handle(r16), runtime HWIO base (memw r16+8), reg offset (memw 0xf0914258),
#   enable value/mask (memw r16+0xc), poll/lock mask (memw r16+0x14), descriptor+0x10.
# v2: NO cave-issued MMIO. (v1 re-read base+offset and HUNG the ADSP on UT — a *posted write*
#     to that reg succeeds fire-and-forget, but a *read* needs a response and stalls if the block
#     isn't fully clocked. So the cave only does struct/.bss loads + SMEM stores now.)
#     The runtime HWIO base differential (UT vs pmOS) is the target; capturing the hardware
#     status safely needs a splice at the leaf's OWN read (f019ab18/poll), done separately if needed.
# Two rings: A = last 16 of ALL invocations; B = last 4 with pollmask!=0 (lock-bearing clocks,
# e.g. the LPAPLL1-sourced framer core clk) so a flood of trivial gates can't evict them.
# Straight-line, null/base-guarded, single exit re-creating the original return (r0=0; jump f001a864).
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os
SRC=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT=f"{FP3_ROOT}/adsp-snapHWL.mbn"
SPLICE_VA=0xf019abb0; SPLICE_FOFF=0x9dbb0        # stock = immext(#0xffe7fc80) = f25ffe0f
CAVE_VA=0xf064e098;   CAVE_FOFF=0x551098          # known-zero hole (3952B free)
STOCK=bytes.fromhex("f25ffe0f")

def enc_jump(pc,t):
    d=t-pc; assert d%4==0; s=d//4; assert -(1<<21)<=s<(1<<21), f"jump out of range {s:#x}"
    imm=s&0x3FFFFF; return ((0b0101100<<25)|(((imm>>13)&0x1FF)<<16)|(0b11<<14)|((imm&0x1FFF)<<1))&0xFFFFFFFF

ASM=r"""
    { r1 = ##0xf090fcd4 }
    { r1 = memw(r1+#0) }
    { p0 = cmp.eq(r1,#0x0); if (p0.new) jump:nt .Lexit }
    { r14 = add(r1,#0x640) }              // stash base
    // --- read leaf params (r16 = handle, still live at return) ---
    { r2 = memw(r16+#0x8) }               // runtime HWIO base
    { r3 = ##0xf0914258 }
    { r3 = memw(r3+#0) }                  // reg offset
    { r4 = memw(r16+#0xc) }               // enable value/mask
    { r5 = memw(r16+#0x14) }              // poll/lock mask
    { r6 = add(r2,r3) }                   // reg addr = base+offset (NOT dereferenced)
    { r7 = memw(r16+#0x10) }              // extra descriptor field (pure struct read; NO cave MMIO)
    // --- header ---
    { r8 = ##0x304c5748 }                 // 'H''W''L''0'
    { memw(r14+#0x00) = r8 }
    // --- ring A: slot = totalA & 15 ---
    { r9 = memw(r14+#0x04) }
    { r10 = and(r9,#0xf) }
    { r10 = asl(r10,#5) }
    { r11 = add(r14,#0x40) }
    { r11 = add(r11,r10) }
    { memw(r11+#0x00) = r16 }
    { memw(r11+#0x04) = r2 }
    { memw(r11+#0x08) = r3 }
    { memw(r11+#0x0c) = r4 }
    { memw(r11+#0x10) = r5 }
    { memw(r11+#0x14) = r7 }
    { memw(r11+#0x18) = r9 }
    { memw(r11+#0x1c) = r6 }
    { r9 = add(r9,#1) }
    { memw(r14+#0x04) = r9 }
    // --- ring B: only pollmask != 0 ---
    { p0 = cmp.eq(r5,#0x0); if (p0.new) jump:nt .Lexit }
    { r12 = memw(r14+#0x08) }
    { r13 = and(r12,#0x3) }
    { r13 = asl(r13,#5) }
    { r15 = add(r14,#0x240) }
    { r15 = add(r15,r13) }
    { memw(r15+#0x00) = r16 }
    { memw(r15+#0x04) = r2 }
    { memw(r15+#0x08) = r3 }
    { memw(r15+#0x0c) = r4 }
    { memw(r15+#0x10) = r5 }
    { memw(r15+#0x14) = r7 }
    { memw(r15+#0x18) = r12 }
    { memw(r15+#0x1c) = r6 }
    { r12 = add(r12,#1) }
    { memw(r14+#0x08) = r12 }
.Lexit:
    { r0 = #0x0 }
"""
RET_VA=0xf001a864   # original return target of the displaced {immext; r0=0; jump 0xf001a864}
here=os.path.dirname(os.path.abspath(__file__))
a=os.path.join(here,"snapHWL.s");o=os.path.join(here,"snapHWL.o");b=os.path.join(here,"snapHWL.bin")
open(a,"w").write(ASM)
MC=subprocess.run(["bash","-lc","command -v llvm-mc-21 || command -v llvm-mc"],capture_output=True,text=True).stdout.strip()
OC=subprocess.run(["bash","-lc","command -v llvm-objcopy-21 || command -v llvm-objcopy"],capture_output=True,text=True).stdout.strip()
subprocess.run([MC,"--arch=hexagon","--mcpu=hexagonv60","--filetype=obj",a,"-o",o],check=True)
subprocess.run([OC,"-O","binary","--only-section=.text",o,b],check=True)
body=open(b,"rb").read()
ret=enc_jump(CAVE_VA+len(body),RET_VA)   # re-create original return: jump 0xf001a864
cave=body+struct.pack("<I",ret)
spl=enc_jump(SPLICE_VA,CAVE_VA)
data=bytearray(open(SRC,"rb").read())
assert bytes(data[SPLICE_FOFF:SPLICE_FOFF+4])==STOCK, f"splice stock mismatch {bytes(data[SPLICE_FOFF:SPLICE_FOFF+4]).hex()}"
assert data[CAVE_FOFF:CAVE_FOFF+len(cave)]==b"\x00"*len(cave), "cave region not zero/too small"
data[CAVE_FOFF:CAVE_FOFF+len(cave)]=cave
data[SPLICE_FOFF:SPLICE_FOFF+4]=struct.pack("<I",spl)
open(OUT,"wb").write(data)
print(f"cave {len(cave)}B  splice={spl:#010x} @foff {SPLICE_FOFF:#x}  cave@foff {CAVE_FOFF:#x} -> {OUT}")
