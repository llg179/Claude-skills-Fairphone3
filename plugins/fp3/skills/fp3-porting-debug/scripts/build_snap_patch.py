#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Stage-1 SMEM-snapshot patch for adsp.mbn.
# Hooks f04bfb68 ("turn on satellite ref clock") entry -> cave stub that stashes
# {magic, ctx+0x74, +0xe14, +0xe18, +0xe1c, +0x7c, +0x88, +0xdec} into SMEM
# item-469 slot#12 +0x40 (AP-readable at PA 0x86302ab0). Non-crashing, guarded.
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os, sys

SRC   = f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
OUT   = f"{FP3_ROOT}/adsp-snap.mbn"          # patched, pre-sign
SPLICE_VA   = 0xf04bfb68     # entry of f04bfb68
SPLICE_FOFF = 0x3c2b68
CAVE_VA     = 0xf064e098     # zero hole in ph4 (3952 B)
CAVE_FOFF   = 0x551098
RET_VA      = 0xf04bfb74     # resume point (after the displaced entry packet)

def enc_jump(pc, target):
    """J2_jump  { jump target }  parse=11. Verified against 0x599ecccc sample."""
    delta = target - pc
    assert delta % 4 == 0, hex(delta)
    imm = (delta // 4) & 0x3FFFFF          # 22-bit signed field
    # range check (+-8MB)
    s = delta // 4
    assert -(1<<21) <= s < (1<<21), f"jump out of range: {delta:#x}"
    hi = (imm >> 13) & 0x1FF               # imm[21:13] -> bits[24:16]
    lo = imm & 0x1FFF                      # imm[12:0]  -> bits[13:1]
    word = (0b0101100 << 25) | (hi << 16) | (0b11 << 14) | (lo << 1)
    return word & 0xFFFFFFFF

# self-test the encoder
assert enc_jump(0xf04bfc38, 0xf01b15d0) == 0x599ecccc, hex(enc_jump(0xf04bfc38,0xf01b15d0))

ASM = r"""
    { r1 = ##0xf090fcd4 }
    { r1 = memw(r1+#0) }
    { p0 = cmp.eq(r1,#0x0); if (p0.new) jump:nt .Lskip }
    { r1 = add(r1,#0x640) }
    { r2 = ##0x30504e53 }
    { memw(r1+#0x00) = r2 }
    { r2 = memw(r0+#0x74) }
    { memw(r1+#0x04) = r2 }
    { r2 = memw(r0+#0xe14) }
    { memw(r1+#0x08) = r2 }
    { r2 = memw(r0+#0xe18) }
    { memw(r1+#0x0c) = r2 }
    { r2 = memw(r0+#0xe1c) }
    { memw(r1+#0x10) = r2 }
    { r2 = memw(r0+#0x7c) }
    { memw(r1+#0x14) = r2 }
    { r2 = memw(r0+#0x88) }
    { memw(r1+#0x18) = r2 }
    { r2 = memw(r0+#0xdec) }
    { memw(r1+#0x1c) = r2 }
.Lskip:
    { r3 = #0x1
      r16 = r0
      memd(r29+#-0x10) = r17:16; allocframe(#0x10) }
"""

def main():
    tmp = "/tmp/claude-1000/-mnt-1TB-Fp3-Sailfish/1f56a429-b78f-4e19-a981-9475ce6ac58c/scratchpad"
    asm_f = os.path.join(tmp, "snap_body.s")
    obj_f = os.path.join(tmp, "snap_body.o")
    bin_f = os.path.join(tmp, "snap_body.bin")
    open(asm_f,"w").write(ASM)
    subprocess.run(["llvm-mc-21","--arch=hexagon","--mcpu=hexagonv60",
                    "--filetype=obj", asm_f, "-o", obj_f], check=True)
    subprocess.run(["llvm-objcopy-21","-O","binary","--only-section=.text",
                    obj_f, bin_f], check=True)
    body = open(bin_f,"rb").read()
    print(f"body len = {len(body)} bytes ({len(body)//4} words)")

    # append the return jump: placed at CAVE_VA + len(body)
    ret_pc  = CAVE_VA + len(body)
    ret_jmp = enc_jump(ret_pc, RET_VA)
    cave = body + struct.pack("<I", ret_jmp)
    print(f"return jump @ {ret_pc:#x} -> {RET_VA:#x} = {ret_jmp:#010x}")
    assert len(cave) < 3900, "cave too big"

    # splice jump at SPLICE_VA -> CAVE_VA
    spl_jmp = enc_jump(SPLICE_VA, CAVE_VA)
    print(f"splice jump @ {SPLICE_VA:#x} -> {CAVE_VA:#x} = {spl_jmp:#010x}")

    data = bytearray(open(SRC,"rb").read())
    # sanity: cave region must be all zero
    assert data[CAVE_FOFF:CAVE_FOFF+len(cave)] == b"\x00"*len(cave), "cave not zero!"
    # sanity: splice target currently the known entry word 23 40 00 78
    assert bytes(data[SPLICE_FOFF:SPLICE_FOFF+4]) == bytes.fromhex("23400078"), \
        data[SPLICE_FOFF:SPLICE_FOFF+4].hex()

    data[CAVE_FOFF:CAVE_FOFF+len(cave)] = cave
    data[SPLICE_FOFF:SPLICE_FOFF+4] = struct.pack("<I", spl_jmp)
    open(OUT,"wb").write(data)
    print(f"wrote {OUT} ({len(data)} bytes)")
    # emit the cave bytes for disasm verification
    open(os.path.join(tmp,"cave.bin"),"wb").write(cave)
    print("cave hex:", cave.hex())

if __name__ == "__main__":
    main()
