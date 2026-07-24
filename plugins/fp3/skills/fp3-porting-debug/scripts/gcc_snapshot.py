#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Zero-risk full GCC block snapshot for UT<->pmOS environmental diff (context §9 step 1).
# GCC (msm8953 qcom,gcc-msm8953) reg = <0x01800000 0x80000> is always-on / AHB-clocked,
# so reading any offset within it is safe (unlike gated LPASS/SLIMbus blocks, rule 4).
# Emits every NONZERO word as "offset=value" so two snapshots diff cleanly.
import mmap, os, struct, sys

BASE = 0x01800000
SIZE = 0x80000  # 512 KiB

def main():
    fd = os.open("/dev/mem", os.O_RDONLY | os.O_SYNC)
    m = mmap.mmap(fd, SIZE, mmap.MAP_SHARED, mmap.PROT_READ, offset=BASE)
    out = []
    for off in range(0, SIZE, 4):
        v = struct.unpack_from("<I", m, off)[0]
        if v != 0:
            out.append("%06x=%08x" % (off, v))
    m.close(); os.close(fd)
    sys.stdout.write("# GCC snapshot base=%#x size=%#x nonzero=%d\n" % (BASE, SIZE, len(out)))
    sys.stdout.write("\n".join(out) + "\n")

if __name__ == "__main__":
    main()
