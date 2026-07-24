#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# frm.py — SLIMbus framer + NGD register reader (the §2 "hard fact" table).
#
# Canonical device-side reader for the WCD9335/SLIMbus framer investigation. Reads
# the SLIMbus core block at 0x0c140000 over /dev/mem and prints framer/NGD state on
# BOTH the UT oracle and pmOS SUT (same physical addresses). Run as root on-device:
#     echo <pw> | sudo -S python3 /tmp/frm.py [label]
#
# WHY a Python mmap reader (not dd/devmem): on a hardened kernel dd/busybox-devmem
# silently return 0 (STRICT_DEVMEM read-path) — that masquerades as "reads 0". mmap
# PROT_READ works. (fp3-kernel-test rule 6.)
#
# ☠️ SAFETY (fp3-kernel-test rules 4/5): only reads the SLIMbus wrapper block
# (0x0c140000), which is AP-mapped and safe to read. Do NOT extend this to gated
# LPASS/LPASS_CC blocks at idle (→ bus hang → 900e crash-dump) or to the ADSP
# carveout (0x8d6xxxxx, XPU → wedge). These 5 registers are safe any time.
#
# ☠️ READING NOTE (folyt.96): when the NGD/SLIMbus block is runtime-SUSPENDED (idle
# autosuspend on UT), every word reads a CONSTANT 0x40/0x50 — that is NOT zero and
# NOT a hang, just the gated block. To see the true framer state, read during a
# fresh boot window or after forcing the block active:
#     echo on > /sys/devices/platform/soc*/c140000.slim*/power/control
#
# Reference values (§2):
#   framing/UP (UT/PIL):  FRM_STAT=0x060D1901 NGD_CFG=0x7 NGD_STATUS=0x000D040E
#   dead    (pmOS/PAS):   FRM_STAT=0x00000000 NGD_CFG=0x0 NGD_STATUS=0x0000040C
#   gated (suspended):    every reg = 0x40 / 0x50
import mmap, struct, sys

REGS = [
    (0x0c140400, "FRM_CFG   "),   # framer config (0x000D0C83 both slots when set)
    (0x0c140404, "FRM_STAT  "),   # framer status: 0x060D1901 = framing, 0 = dead
    (0x0c141000, "NGD_CFG   "),   # 0x7 = NGD enabled, 0 = not
    (0x0c141004, "NGD_STATUS"),   # 0x000D040E = laddr'd, 0x40C = no framer/no laddr
    (0x0c141014, "NGD_INTS  "),   # NGD_INT_EN/STAT: 0xBE000000 active, 0 = none
]

def rd(fd, a):
    pa = a & ~0xfff
    m = mmap.mmap(fd.fileno(), 4096, mmap.MAP_SHARED, mmap.PROT_READ, offset=pa)
    v = struct.unpack("<I", m[a - pa:a - pa + 4])[0]
    m.close()
    return v

def main():
    label = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        fd = open("/dev/mem", "rb")
    except PermissionError:
        sys.exit("need root: echo <pw> | sudo -S python3 %s" % sys.argv[0])
    vals = {}
    with fd:
        for addr, name in REGS:
            vals[name.strip()] = rd(fd, addr)
            print("%s @0x%08x = 0x%08X" % (name, addr, vals[name.strip()]))
    frm = vals["FRM_STAT"]
    ngd = vals["NGD_STATUS"]
    if frm in (0x40, 0x50) and ngd in (0x40, 0x50):
        verdict = "GATED (runtime-suspended — force 'power/control=on' or read at boot)"
    elif frm & 0x06000000 and (ngd & 0x400):
        verdict = "FRAMING (framer alive, bus clocked)"
    elif frm == 0:
        verdict = "DEAD (framer not framing — the pmOS/PAS symptom)"
    else:
        verdict = "UNKNOWN (see reference values in header)"
    print("%-14s => %s" % (label or "verdict", verdict))

if __name__ == "__main__":
    main()
