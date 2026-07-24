#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Method-matched /dev/mem region dumper for the framer + LPASS clock-controller,
# usable IDENTICALLY on UT (downstream) and pmOS (mainline). Auto-force-resumes
# the NGD so the LPASS_AP alias window is clocked (folyt.139), reads both regions,
# writes them to files, and prints key regs. Read-only except the reversible
# power/control write (restored to 'auto' at the end).
#
# Usage: dump_regions.py <outprefix>   e.g. dump_regions.py /home/.../pmos
import mmap, os, struct, sys, glob, time

REGIONS = [("lpasscc", 0x0c000000, 0x14000),
           ("framer",  0x0c140000, 0x2c000)]

def find_ngd_ctrl():
    # UT downstream: /sys/devices/platform/soc/c140000.slim/power/control
    # pmOS mainline: .../c140000.slim-ngd/qcom,slim-ngd.1/power/control (or similar)
    cands = []
    cands += glob.glob("/sys/devices/platform/soc*/c140000.slim*/power/control")
    cands += glob.glob("/sys/devices/platform/soc*/c140000.slim*/*slim-ngd*/power/control")
    cands += glob.glob("/sys/devices/platform/soc*/*slim*/*/power/control")
    return cands

def set_ctrl(paths, val):
    done = []
    for p in paths:
        try:
            open(p, "w").write(val); done.append(p)
        except Exception:
            pass
    return done

def read_region(base, size):
    f = os.open("/dev/mem", os.O_RDONLY | os.O_SYNC)
    try:
        m = mmap.mmap(f, size, mmap.MAP_SHARED, mmap.PROT_READ, offset=base)
        data = m.read(size); m.close()
    finally:
        os.close(f)
    return data

def w32(b, o):
    return struct.unpack_from("<I", b, o)[0]

def main():
    if len(sys.argv) < 2:
        print("usage: dump_regions.py <outprefix>"); sys.exit(1)
    pref = sys.argv[1]
    ctrls = find_ngd_ctrl()
    print("# dump_regions", time.strftime("%Y-%m-%d %H:%M:%S"))
    print("# ngd ctrl nodes:", ctrls)
    forced = set_ctrl(ctrls, "on"); time.sleep(0.3)
    print("# forced 'on':", forced)
    blobs = {}
    for name, base, size in REGIONS:
        try:
            d = read_region(base, size)
            blobs[name] = d
            path = "%s_%s.bin" % (pref, name)
            open(path, "wb").write(d)
            print("  %-8s 0x%08x/0x%x -> %s (%d bytes)" % (name, base, size, path, len(d)))
        except Exception as e:
            print("  %-8s READ-ERR %s" % (name, e))
    fr = blobs.get("framer"); ck = blobs.get("lpasscc")
    if fr:
        print("  framer +0x400 FRM_CFG=0x%08x +0x404 FRM_STAT=0x%08x +0x604=0x%08x"
              % (w32(fr,0x400), w32(fr,0x404), w32(fr,0x604)))
    if ck:
        print("  clk RCGR_CFG(+0x12004)=0x%08x framer_CBCR(+0x12014)=0x%08x"
              % (w32(ck,0x12004), w32(ck,0x12014)))
    set_ctrl(ctrls, "auto")
    print("DUMP-REGIONS-OK")

main()
