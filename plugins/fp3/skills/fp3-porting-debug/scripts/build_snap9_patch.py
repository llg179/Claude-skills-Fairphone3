#!/usr/bin/env python3
# Stage-9 (SNP9): dump the f0191c68 config-struct window at the caller splice
# f04bfba0. The clock-op is called (f04bfb94) as f0191c68(r0=id, r1=##0xf0c85450);
# f0191c68 reads r1+0x0/+0x4/+0x8/+0xc and early-returns if +0x8==0 or +0xc==0.
# We got rc=0, so it passed those -> dump 12 words from 0xf0c85440 to see the
# struct (covers 0xf0c85450+0x0..+0x1c). All reads are of the fw's OWN fixed
# config pointer (mapped bss) -> safe, no guessed deref (Stage-5 lesson).
# Stash @ SMEM PA 0x86302ab0 (64B): +0x00 "SNP7" | +0x04 id | +0x08 rc |
#   +0x0c..+0x38 = cfg[0..11] (12 words from 0xf0c85440)
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os
SRC=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT=f"{FP3_ROOT}/adsp-snap9.mbn"
SPLICE_VA=0xf04bfba0; SPLICE_FOFF=0x3c2ba0
CAVE_VA=0xf064e098;   CAVE_FOFF=0x551098
RET_VA=0xf04bfbd8
CFG_BASE=0xf0c85400;  NWORDS=12
def enc_jump(pc,t):
    d=t-pc; assert d%4==0; s=d//4; assert -(1<<21)<=s<(1<<21)
    imm=s&0x3FFFFF; return ((0b0101100<<25)|(((imm>>13)&0x1FF)<<16)|(0b11<<14)|((imm&0x1FFF)<<1))&0xFFFFFFFF
assert enc_jump(0xf04bfc38,0xf01b15d0)==0x599ecccc
dump=""
for i in range(NWORDS):
    dump+=f"    {{ r2 = memw(r3+#{i*4:#x}) }}\n    {{ memw(r1+#{0x0c+i*4:#x}) = r2 }}\n"
ASM=f"""
    {{ r1 = ##0xf090fcd4 }}
    {{ r1 = memw(r1+#0) }}
    {{ p0 = cmp.eq(r1,#0x0); if (p0.new) jump:nt .Lend }}
    {{ r1 = add(r1,#0x640) }}
    {{ r2 = ##0x39504e53 }}
    {{ memw(r1+#0x00) = r2 }}
    {{ r2 = memw(r16+#0xe14) }}
    {{ memw(r1+#0x04) = r2 }}
    {{ memw(r1+#0x08) = r0 }}
    {{ r3 = ##0x{CFG_BASE:08x} }}
{dump}.Lend:
    {{ r17 = r0 }}
"""
tmp="/tmp/claude-1000/-mnt-1TB-Fp3-Sailfish/dd323baf-a481-4cdd-8106-416f327bbc92/scratchpad"
a=os.path.join(tmp,"snap9.s");o=os.path.join(tmp,"snap9.o");b=os.path.join(tmp,"snap9.bin")
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
open(OUT,"wb").write(data); open(os.path.join(tmp,"cave9.bin"),"wb").write(cave)
print(f"body {len(body)}B cave {len(cave)}B splice={spl:#010x} ret={ret:#010x} wrote {OUT}")
