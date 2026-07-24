#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Stage-5 (SNP5): at the PROVEN-CLEAN caller splice f04bfba0 (same as Stage-2b),
# after the slim-core clock enable has returned (rc in r0), walk the DAL handle
# (ctx+0xe18) to the CBCR reg_addr the enable-stub used and read *reg_addr back,
# to test whether the CBCR actually got set despite rc=0 (FALSE-SUCCESS probe).
#   enable-stub f04df0ac: reg = memw(handle+0xc) ?: memw(handle+0x4); *reg |= mask
#   DAL f019f134 calls stub with r0 = handle (= worker ctx+0xe18).
# Every deref NULL-guarded; *reg is safe (fw just RMW'd it). Straight-line cave
# with internal branches (llvm-mc resolves) + one UNCONDITIONAL jump to return.
# Stash @ item-469 slot#12+0x40 (SMEM PA 0x86302ab0):
#   +0x00 "SNP5" | +0x04 rc | +0x08 handle | +0x0c reg_addr | +0x10 *reg | +0x14 ctx+0xe14
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os
SRC=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT=f"{FP3_ROOT}/adsp-snap5.mbn"
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
    { r2 = ##0x35504e53 }
    { memw(r1+#0x00) = r2 }
    { memw(r1+#0x04) = r0 }
    { r2 = memw(r16+#0xe18) }
    { memw(r1+#0x08) = r2 }
    { r3 = memw(r16+#0xe14) }
    { memw(r1+#0x14) = r3 }
    { p0 = cmp.eq(r2,#0x0); if (p0.new) jump:nt .Lhnull }
    { r4 = memw(r2+#0xc) }
    { p0 = cmp.eq(r4,#0x0) }
    { if (p0) r4 = memw(r2+#0x4) }
    { memw(r1+#0x0c) = r4 }
    { p0 = cmp.eq(r4,#0x0); if (p0.new) jump:nt .Lrnull }
    { r5 = memw(r4+#0x0) }
    { memw(r1+#0x10) = r5 }
    { jump .Lend }
.Lrnull:
    { r5 = ##0xBAD00000 }
    { memw(r1+#0x10) = r5 }
    { jump .Lend }
.Lhnull:
    { r5 = ##0xBAD0BAD0 }
    { memw(r1+#0x0c) = r5 }
    { memw(r1+#0x10) = r5 }
.Lend:
    { r17 = r0 }
"""
tmp="/tmp/claude-1000/-mnt-1TB-Fp3-Sailfish/dd323baf-a481-4cdd-8106-416f327bbc92/scratchpad"
a=os.path.join(tmp,"snap5.s");o=os.path.join(tmp,"snap5.o");b=os.path.join(tmp,"snap5.bin")
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
open(OUT,"wb").write(data); open(os.path.join(tmp,"cave5.bin"),"wb").write(cave)
print(f"body {len(body)}B cave {len(cave)}B splice={spl:#010x} ret={ret:#010x} wrote {OUT}")
