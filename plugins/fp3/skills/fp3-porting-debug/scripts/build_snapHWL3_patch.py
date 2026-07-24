#!/usr/bin/env python3
# HWL1 (v3) = MINIMAL, SMEM-safe HalHwIo CGC-enable leaf trace.
# v2's 704-byte ring likely OVERRAN the SMEM stash item (snapT3 proved only ~0x50B safe)
# and degraded the ADSP/audio -> UT container fell to File-Stor. v3 writes a single tiny
# record (0x24B, inside the proven-safe window) at the leaf return (f019abb0):
#   +0x00 magic 'HWL1'
#   +0x04 total   = every leaf invocation (proves the register-poke leaf runs AT ALL)
#   +0x08 pm_nz   = count of pollmask!=0 (lock-bearing) invocations
#   +0x0c.. last pollmask!=0 record: handle, base(runtime HWIO), offset(memw 0xf0914258),
#           value/mask, pollmask, desc+0x10
# NO cave-issued MMIO (v2 lesson). Null-guarded, single exit re-creating jump 0xf001a864.
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os
SRC=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT=f"{FP3_ROOT}/adsp-snapHWL3.mbn"
SPLICE_VA=0xf019abb0; SPLICE_FOFF=0x9dbb0; STOCK=bytes.fromhex("f25ffe0f")
CAVE_VA=0xf064e098;   CAVE_FOFF=0x551098
RET_VA=0xf001a864
def enc_jump(pc,t):
    d=t-pc; assert d%4==0; s=d//4; assert -(1<<21)<=s<(1<<21); imm=s&0x3FFFFF
    return ((0b0101100<<25)|(((imm>>13)&0x1FF)<<16)|(0b11<<14)|((imm&0x1FFF)<<1))&0xFFFFFFFF
ASM=r"""
    { r1 = ##0xf090fcd4 }
    { r1 = memw(r1+#0) }
    { p0 = cmp.eq(r1,#0x0); if (p0.new) jump:nt .Lexit }
    { r14 = add(r1,#0x640) }
    { r8 = ##0x314c5748 }             // 'H''W''L''1'
    { memw(r14+#0x00) = r8 }
    { r9 = memw(r14+#0x04) }          // total invocations
    { r9 = add(r9,#1) }
    { memw(r14+#0x04) = r9 }
    { r5 = memw(r16+#0x14) }          // pollmask
    { p0 = cmp.eq(r5,#0x0); if (p0.new) jump:nt .Lexit }
    { r2 = memw(r16+#0x8) }           // base
    { r3 = ##0xf0914258 }
    { r3 = memw(r3+#0) }              // offset
    { r4 = memw(r16+#0xc) }           // value
    { r7 = memw(r16+#0x10) }          // desc+0x10
    { r10 = memw(r14+#0x08) }         // pm_nz count
    { r10 = add(r10,#1) }
    { memw(r14+#0x08) = r10 }
    { memw(r14+#0x0c) = r16 }         // handle
    { memw(r14+#0x10) = r2 }          // base
    { memw(r14+#0x14) = r3 }          // offset
    { memw(r14+#0x18) = r4 }          // value
    { memw(r14+#0x1c) = r5 }          // pollmask
    { memw(r14+#0x20) = r7 }          // desc+0x10
.Lexit:
    { r0 = #0x0 }
"""
here=os.path.dirname(os.path.abspath(__file__))
a=os.path.join(here,"snapHWL3.s");o=os.path.join(here,"snapHWL3.o");b=os.path.join(here,"snapHWL3.bin")
open(a,"w").write(ASM)
MC=subprocess.run(["bash","-lc","command -v llvm-mc-21 || command -v llvm-mc"],capture_output=True,text=True).stdout.strip()
OC=subprocess.run(["bash","-lc","command -v llvm-objcopy-21 || command -v llvm-objcopy"],capture_output=True,text=True).stdout.strip()
subprocess.run([MC,"--arch=hexagon","--mcpu=hexagonv60","--filetype=obj",a,"-o",o],check=True)
subprocess.run([OC,"-O","binary","--only-section=.text",o,b],check=True)
body=open(b,"rb").read()
ret=enc_jump(CAVE_VA+len(body),RET_VA)
cave=body+struct.pack("<I",ret)
spl=enc_jump(SPLICE_VA,CAVE_VA)
data=bytearray(open(SRC,"rb").read())
assert bytes(data[SPLICE_FOFF:SPLICE_FOFF+4])==STOCK, "splice stock mismatch"
assert data[CAVE_FOFF:CAVE_FOFF+len(cave)]==b"\x00"*len(cave), "cave region not zero"
data[CAVE_FOFF:CAVE_FOFF+len(cave)]=cave
data[SPLICE_FOFF:SPLICE_FOFF+4]=struct.pack("<I",spl)
open(OUT,"wb").write(data)
print(f"cave {len(cave)}B (writes 0x24B to SMEM)  splice={spl:#010x} -> {OUT}")
