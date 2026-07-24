#!/usr/bin/env python3
# Stage-3: SAME proven-clean entry splice on f04bfb68 as Stage-1, but the cave
# captures the DAL-clock driver global cluster 0xf0913640..0xf0913658 (steers
# get/enable to bypass vs real) plus ctx+0xe14/0x74. Non-crashing entry trace.
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os
SRC=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT=f"{FP3_ROOT}/adsp-snap3.mbn"
SPLICE_VA=0xf04bfb68; SPLICE_FOFF=0x3c2b68
CAVE_VA=0xf064e098;   CAVE_FOFF=0x551098
RET_VA=0xf04bfb74
def enc_jump(pc,t):
    d=t-pc; assert d%4==0; s=d//4; assert -(1<<21)<=s<(1<<21)
    imm=s&0x3FFFFF; return ((0b0101100<<25)|(((imm>>13)&0x1FF)<<16)|(0b11<<14)|((imm&0x1FFF)<<1))&0xFFFFFFFF
assert enc_jump(0xf04bfc38,0xf01b15d0)==0x599ecccc

# capture: magic, ctx+0xe14, ctx+0x74, then 7 globals 0xf0913640..0xf0913658
GLOBALS=[0xf0913640,0xf0913644,0xf0913648,0xf091364c,0xf0913650,0xf0913654,0xf0913658]
lines=[
 "{ r1 = ##0xf090fcd4 }",
 "{ r1 = memw(r1+#0) }",
 "{ p0 = cmp.eq(r1,#0x0); if (p0.new) jump:nt .Lskip }",
 "{ r1 = add(r1,#0x640) }",
 "{ r2 = ##0x33504e53 }",          # "SNP3"
 "{ memw(r1+#0x00) = r2 }",
 "{ r2 = memw(r0+#0xe14) }",
 "{ memw(r1+#0x04) = r2 }",
 "{ r2 = memw(r0+#0x74) }",
 "{ memw(r1+#0x08) = r2 }",
]
off=0x0c
for g in GLOBALS:
    lines.append(f"{{ r2 = ##{g:#x} }}")
    lines.append("{ r2 = memw(r2+#0) }")
    lines.append(f"{{ memw(r1+#{off:#x}) = r2 }}")
    off+=4
lines.append(".Lskip:")
lines.append("{ r3 = #0x1\n  r16 = r0\n  memd(r29+#-0x10) = r17:16; allocframe(#0x10) }")
ASM="\n".join(lines)+"\n"

tmp="/tmp/claude-1000/-mnt-1TB-Fp3-Sailfish/1f56a429-b78f-4e19-a981-9475ce6ac58c/scratchpad"
a=os.path.join(tmp,"snap3.s");o=os.path.join(tmp,"snap3.o");b=os.path.join(tmp,"snap3.bin")
open(a,"w").write(ASM)
subprocess.run(["llvm-mc-21","--arch=hexagon","--mcpu=hexagonv60","--filetype=obj",a,"-o",o],check=True)
subprocess.run(["llvm-objcopy-21","-O","binary","--only-section=.text",o,b],check=True)
body=open(b,"rb").read()
ret=enc_jump(CAVE_VA+len(body),RET_VA)
cave=body+struct.pack("<I",ret)
assert len(cave)<3900
spl=enc_jump(SPLICE_VA,CAVE_VA)
data=bytearray(open(SRC,"rb").read())
assert data[CAVE_FOFF:CAVE_FOFF+len(cave)]==b"\x00"*len(cave)
assert bytes(data[SPLICE_FOFF:SPLICE_FOFF+4])==bytes.fromhex("23400078")
data[CAVE_FOFF:CAVE_FOFF+len(cave)]=cave
data[SPLICE_FOFF:SPLICE_FOFF+4]=struct.pack("<I",spl)
open(OUT,"wb").write(data)
open(os.path.join(tmp,"cave3.bin"),"wb").write(cave)
print(f"body {len(body)}B cave {len(cave)}B; splice={spl:#010x} ret={ret:#010x}; wrote {OUT}")
