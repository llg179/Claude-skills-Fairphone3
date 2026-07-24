#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# SNPD: resolve the physical APPLY/set_rate fn. f01a12bc's 2nd callr is the HW
# apply: r3=memw(subobj+0x04); r3=memw(r3+0x04); callr r3. subobj+0x04=0xf09b2e50
# (fixed BSS singleton). So apply_fn = memw(memw(0xf09b2e50+0x04))... actually
# apply_fn = memw(0xf09b2e50 + 0x04). Walk handle->subobj->obj2=memw(subobj+4),
# stash obj2[0x00..0x1c] + obj2's apply-fn candidates. Also stash the fixed
# 0xf09b2e50 region directly as cross-check. Null-guarded. Magic 'SNPD'.
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os
SRC=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT=f"{FP3_ROOT}/adsp-snapD.mbn"
SPLICE_VA=0xf04bfba0; SPLICE_FOFF=0x3c2ba0
CAVE_VA=0xf064e098;   CAVE_FOFF=0x551098
RET_VA=0xf04bfbd8
def enc_jump(pc,t):
    d=t-pc; assert d%4==0; s=d//4; assert -(1<<21)<=s<(1<<21)
    imm=s&0x3FFFFF; return ((0b0101100<<25)|(((imm>>13)&0x1FF)<<16)|(0b11<<14)|((imm&0x1FFF)<<1))&0xFFFFFFFF
ASM=r"""
    { r1 = ##0xf090fcd4 }
    { r1 = memw(r1+#0) }
    { p0 = cmp.eq(r1,#0x0); if (p0.new) jump:nt .Lskip }
    { r1 = add(r1,#0x640) }
    { r2 = ##0x44504e53 }
    { memw(r1+#0x00) = r2 }
    { r3 = memw(r16+#0xe18) }
    { memw(r1+#0x04) = r3 }
    { p0 = cmp.eq(r3,#0x0); if (p0.new) jump:nt .Lskip }
    { r3 = memw(r3+#0x10) }
    { memw(r1+#0x08) = r3 }
    { p0 = cmp.eq(r3,#0x0); if (p0.new) jump:nt .Lskip }
    { r4 = memw(r3+#0x04) }
    { memw(r1+#0x0c) = r4 }
    { p0 = cmp.eq(r4,#0x0); if (p0.new) jump:nt .Lwalkfix }
    { r5 = memw(r4+#0x00) }
    { memw(r1+#0x10) = r5 }
    { r5 = memw(r4+#0x04) }
    { memw(r1+#0x14) = r5 }
    { r5 = memw(r4+#0x08) }
    { memw(r1+#0x18) = r5 }
    { r5 = memw(r4+#0x0c) }
    { memw(r1+#0x1c) = r5 }
    { r5 = memw(r4+#0x10) }
    { memw(r1+#0x20) = r5 }
    { r5 = memw(r4+#0x14) }
    { memw(r1+#0x24) = r5 }
    { r5 = memw(r4+#0x18) }
    { memw(r1+#0x28) = r5 }
    { r5 = memw(r4+#0x1c) }
    { memw(r1+#0x2c) = r5 }
.Lwalkfix:
    { r6 = ##0xf09b2e50 }
    { r7 = memw(r6+#0x00) }
    { memw(r1+#0x30) = r7 }
    { r7 = memw(r6+#0x04) }
    { memw(r1+#0x34) = r7 }
    { r7 = memw(r6+#0x08) }
    { memw(r1+#0x38) = r7 }
    { r7 = memw(r6+#0x0c) }
    { memw(r1+#0x3c) = r7 }
    { r3 = memw(r16+#0xe18) }
    { p0 = cmp.eq(r3,#0x0); if (p0.new) jump:nt .Lskip }
    { r3 = memw(r3+#0x10) }
    { p0 = cmp.eq(r3,#0x0); if (p0.new) jump:nt .Lskip }
    { r7 = memw(r3+#0x1c) }
    { memw(r1+#0x40) = r7 }
    { r7 = memw(r3+#0x20) }
    { memw(r1+#0x44) = r7 }
    { r7 = memw(r3+#0x24) }
    { memw(r1+#0x48) = r7 }
    { r7 = memw(r3+#0x28) }
    { memw(r1+#0x4c) = r7 }
    { r7 = memw(r3+#0x2c) }
    { memw(r1+#0x50) = r7 }
    { r7 = memw(r3+#0x54) }
    { memw(r1+#0x54) = r7 }
.Lskip:
    { r17 = r0 }
"""
tmp=os.path.dirname(os.path.abspath(__file__))
a=os.path.join(tmp,"snapD.s");o=os.path.join(tmp,"snapD.o");b=os.path.join(tmp,"snapD.bin")
open(a,"w").write(ASM)
subprocess.run(["llvm-mc-21","--arch=hexagon","--mcpu=hexagonv60","--filetype=obj",a,"-o",o],check=True)
subprocess.run(["llvm-objcopy-21","-O","binary","--only-section=.text",o,b],check=True)
body=open(b,"rb").read()
ret=enc_jump(CAVE_VA+len(body),RET_VA)
cave=body+struct.pack("<I",ret)
spl=enc_jump(SPLICE_VA,CAVE_VA)
data=bytearray(open(SRC,"rb").read())
assert data[CAVE_FOFF:CAVE_FOFF+len(cave)]==b"\x00"*len(cave), "cave not zero/too small"
assert bytes(data[SPLICE_FOFF:SPLICE_FOFF+4])==bytes.fromhex("11406070"), "splice stock mismatch"
data[CAVE_FOFF:CAVE_FOFF+len(cave)]=cave
data[SPLICE_FOFF:SPLICE_FOFF+4]=struct.pack("<I",spl)
open(OUT,"wb").write(data)
print(f"body {len(body)}B cave {len(cave)}B splice={spl:#010x} ret={ret:#010x} wrote {OUT}")
