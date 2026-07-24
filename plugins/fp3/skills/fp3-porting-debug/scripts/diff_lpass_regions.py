#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Word-by-word diff of two same-region MMIO dumps produced by dump_lpass_regions.py
# (the oracle/UT side vs the pmOS/dead side). This is the two-sided differential the
# whole SLIMbus investigation turns on: identical config words => the layer is NOT
# the differentiator; a lone differing STATUS word is usually an OUTPUT/marker, not a
# lever (prove causality with frm_causality.py before calling it a fix).
#
# Usage:
#   diff_lpass_regions.py <ut_prefix> <pmos_prefix>
#     where each <prefix>_{lpasscc,framer}.bin exists (dump_lpass_regions.py output)
#   diff_lpass_regions.py --pair <name> <base_hex> <a.bin> <b.bin>
#     diff one explicit file pair at a given phys base.
import struct, sys

def diff(name, base, a_path, b_path):
    a = open(a_path, "rb").read()
    b = open(b_path, "rb").read()
    n = min(len(a), len(b))
    diffs = []
    for o in range(0, n & ~3, 4):
        x = struct.unpack_from("<I", a, o)[0]
        y = struct.unpack_from("<I", b, o)[0]
        if x != y:
            diffs.append((o, x, y))
    print("==== %s (phys 0x%08x, %d bytes) : %d differing words ====" %
          (name, base, n, len(diffs)))
    for o, x, y in diffs:
        print("  +0x%05x (phys 0x%08x)  A=0x%08x  B=0x%08x  xor=0x%08x" %
              (o, base + o, x, y, x ^ y))
    print()
    return len(diffs)

def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "--pair":
        _, _, name, base, ap, bp = sys.argv
        diff(name, int(base, 16), ap, bp)
        return
    if len(sys.argv) != 3:
        print("usage: diff_lpass_regions.py <ut_prefix> <pmos_prefix>")
        print("   or: diff_lpass_regions.py --pair <name> <base_hex> <a.bin> <b.bin>")
        sys.exit(1)
    ut, pm = sys.argv[1], sys.argv[2]
    regions = [("lpasscc", 0x0c000000), ("framer", 0x0c140000)]
    tot = 0
    for name, base in regions:
        tot += diff(name, base, "%s_%s.bin" % (ut, name), "%s_%s.bin" % (pm, name))
    print("TOTAL differing words: %d" % tot)

main()
