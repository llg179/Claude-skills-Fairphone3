#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Step-1 (SNPA): resolve the DAL physical-clock LEAF + device-object slice.
# Reuses the PROVEN Stage-2b splice site f04bfba0 (`r17=r0`, stock 11406070),
# where r16 = slim driver ctx is live and f04bfaa0 (the DAL core-clk enable via
# f019f134) has ALREADY run, so the handle ctx+0xe18 and the vtable behind it are
# populated. Captures {SNPA, f0191c68-rc=r0, handle, memw(handle+0x48)=LEAF fn ptr,
# handle+{0x08,0x0c,0x40,0x44,0x18} device-object fields}. Handle-NULL-guarded
# (Stage-5 lesson: never deref a possibly-zero pointer). Same cave/return as 2b.
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os
SRC=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT=f"{FP3_ROOT}/adsp-snapA.mbn"
SPLICE_VA=0xf04bfba0; SPLICE_FOFF=0x3c2ba0
CAVE_VA=0xf064e098;   CAVE_FOFF=0x551098
RET_VA=0xf04bfbd8     # unconditional return point (proven safe by Stage-2b)
def enc_jump(pc,t):
    d=t-pc; assert d%4==0; s=d//4; assert -(1<<21)<=s<(1<<21)
    imm=s&0x3FFFFF; return ((0b0101100<<25)|(((imm>>13)&0x1FF)<<16)|(0b11<<14)|((imm&0x1FFF)<<1))&0xFFFFFFFF
assert enc_jump(0xf04bfc38,0xf01b15d0)==0x599ecccc
ASM=r"""
    { r1 = ##0xf090fcd4 }
    { r1 = memw(r1+#0) }
    { p0 = cmp.eq(r1,#0x0); if (p0.new) jump:nt .Lskip }
    { r1 = add(r1,#0x640) }
    { r2 = ##0x41504e53 }
    { memw(r1+#0x00) = r2 }
    { memw(r1+#0x04) = r0 }
    { r3 = memw(r16+#0xe18) }
    { memw(r1+#0x08) = r3 }
    { p0 = cmp.eq(r3,#0x0); if (p0.new) jump:nt .Lskip }
    { r4 = memw(r3+#0x48) }
    { memw(r1+#0x0c) = r4 }
    { r4 = memw(r3+#0x08) }
    { memw(r1+#0x10) = r4 }
    { r4 = memw(r3+#0x0c) }
    { memw(r1+#0x14) = r4 }
    { r4 = memw(r3+#0x40) }
    { memw(r1+#0x18) = r4 }
    { r4 = memw(r3+#0x44) }
    { memw(r1+#0x1c) = r4 }
    { r4 = memw(r3+#0x18) }
    { memw(r1+#0x20) = r4 }
.Lskip:
    { r17 = r0 }
"""
tmp="/tmp/claude-1000/-mnt-1TB-Fp3-Sailfish/dd323baf-a481-4cdd-8106-416f327bbc92/scratchpad"
a=os.path.join(tmp,"snapA.s");o=os.path.join(tmp,"snapA.o");b=os.path.join(tmp,"snapA.bin")
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
open(OUT,"wb").write(data); open(os.path.join(tmp,"caveA.bin"),"wb").write(cave)
print(f"body {len(body)}B cave {len(cave)}B splice={spl:#010x} ret={ret:#010x} wrote {OUT}")
