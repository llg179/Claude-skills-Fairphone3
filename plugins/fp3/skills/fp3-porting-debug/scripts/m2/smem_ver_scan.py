#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Scan the SAFE legacy-SMEM window for the ADSP image-version string, and report
# which SMEM TOC item it lands in. Read-only mmap(PROT_READ) of 0x86300000 — the
# proven exfil region (no carveout, no wedge). Run on device as root.
import mmap, struct
BASE = 0x86300000; SZ = 0x200000
f = open("/dev/mem", "rb")
m = mmap.mmap(f.fileno(), SZ, mmap.MAP_SHARED, mmap.PROT_READ, offset=BASE)
data = m[:]

def item_of(off):
    # legacy TOC at +0xD0, 16B/entry: alloc, offset, size, aux
    for i in range(512):
        a, o, s, _ = struct.unpack_from("<IIII", data, 0xD0 + i*16)
        if a and s and o <= off < o + s:
            return i, o, s
    return None, None, None

for pat in (b"ADSP.VT", b"QC_IMAGE_VERSION_STRING", b"C0DED"):
    i = data.find(pat)
    n = 0
    while i != -1 and n < 8:
        end = data.find(b"\x00", i)
        s = data[i:end if 0 <= end < i+80 else i+80]
        it, io, isz = item_of(i)
        print("off=0x%08x (PA 0x%08x) item=%s [off=0x%x size=0x%x]  %r" % (
            i, BASE + i, it, io or 0, isz or 0, s))
        i = data.find(pat, i + 1); n += 1
    if n == 0:
        print("%r: not found" % pat)
m.close()
print("OK-SCAN-DONE")
