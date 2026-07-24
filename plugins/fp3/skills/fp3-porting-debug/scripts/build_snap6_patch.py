#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Stage-6 (SNP6): RING-capture at the proven-clean caller splice f04bfba0.
# NO guessed-pointer deref (that faulted the ADSP in Stage-5). Only reads r0 (=rc
# of the f0191c68 clock-op call at f04bfb94), ctx+0xe14 (clock id arg), ctx+0x74
# (gate) -- all from live r16/r0. Ring of 4 entries + header, to see how many
# clock-ops run on the slim path (caller f04ce37c) and which id gives nonzero rc.
# Stash @ item-469 slot#12+0x40 (SMEM PA 0x86302ab0), 64 bytes usable:
#   +0x00 "SNP6" | +0x04 count | +0x08.. ring[4] x {id, rc, gate} (12B each)
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os
SRC=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT=f"{FP3_ROOT}/adsp-snap6.mbn"
SPLICE_VA=0xf04bfba0; SPLICE_FOFF=0x3c2ba0
CAVE_VA=0xf064e098;   CAVE_FOFF=0x551098
RET_VA=0xf04bfbd8
def enc_jump(pc,t):
    d=t-pc; assert d%4==0; s=d//4; assert -(1<<21)<=s<(1<<21)
    imm=s&0x3FFFFF; return ((0b0101100<<25)|(((imm>>13)&0x1FF)<<16)|(0b11<<14)|((imm&0x1FFF)<<1))&0xFFFFFFFF
assert enc_jump(0xf04bfc38,0xf01b15d0)==0x599ecccc
ASM=r"""
    { r1 = ##0xf090fcd4 }
    { r1 = memw(r1+#0) }
    { p0 = cmp.eq(r1,#0x0); if (p0.new) jump:nt .Lend }
    { r1 = add(r1,#0x640) }
    { r3 = memw(r1+#0x00) }
    { r2 = memw(r1+#0x04) }
    { r4 = ##0x36504e53 }
    { p0 = cmp.eq(r3,r4); if (!p0.new) r2 = #0x0 }
    { memw(r1+#0x00) = r4 }
    { p0 = cmp.gtu(r2,#0x3); if (p0.new) jump:nt .Lbump }
    { r5 = asl(r2,#0x3) }
    { r6 = asl(r2,#0x2) }
    { r5 = add(r5,r6) }
    { r5 = add(r5,r1) }
    { r7 = memw(r16+#0xe14) }
    { memw(r5+#0x08) = r7 }
    { memw(r5+#0x0c) = r0 }
    { r7 = memw(r16+#0x74) }
    { memw(r5+#0x10) = r7 }
.Lbump:
    { r2 = add(r2,#0x1) }
    { memw(r1+#0x04) = r2 }
.Lend:
    { r17 = r0 }
"""
tmp="/tmp/claude-1000/-mnt-1TB-Fp3-Sailfish/dd323baf-a481-4cdd-8106-416f327bbc92/scratchpad"
a=os.path.join(tmp,"snap6.s");o=os.path.join(tmp,"snap6.o");b=os.path.join(tmp,"snap6.bin")
open(a,"w").write(ASM)
subprocess.run(["llvm-mc-21","--arch=hexagon","--mcpu=hexagonv60","--filetype=obj",a,"-o",o],check=True)
subprocess.run(["llvm-objcopy-21","-O","binary","--only-section=.text",o,b],check=True)
body=open(b,"rb").read()
ret=enc_jump(CAVE_VA+len(body),RET_VA)
cave=body+struct.pack("<I",ret)
spl=enc_jump(SPLICE_VA,CAVE_VA)
data=bytearray(open(SRC,"rb").read())
assert data[CAVE_FOFF:CAVE_FOFF+len(cave)]==b"\x00"*len(cave), "cave hole not zero / too big"
assert bytes(data[SPLICE_FOFF:SPLICE_FOFF+4])==bytes.fromhex("11406070"), "splice site not r17=r0"
data[CAVE_FOFF:CAVE_FOFF+len(cave)]=cave
data[SPLICE_FOFF:SPLICE_FOFF+4]=struct.pack("<I",spl)
open(OUT,"wb").write(data); open(os.path.join(tmp,"cave6.bin"),"wb").write(cave)
print(f"body {len(body)}B cave {len(cave)}B splice={spl:#010x} ret={ret:#010x} wrote {OUT}")
