#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Keep pages mapped, sample fast, log every register transition during a re-triggered power_up.
import mmap, os, struct, time
PG = 0x1000
fd = os.open("/dev/mem", os.O_RDONLY | os.O_SYNC)
def page(pa): return mmap.mmap(fd, PG, mmap.MAP_SHARED, mmap.PROT_READ, offset=pa & ~(PG-1))
ngd = page(0xc141000)   # NGD regs
p3  = page(0xc11a000)   # BAM pipe3 (RX) block 0xc11a000..fff
p4  = page(0xc11b000)   # BAM pipe4 (TX) block
def r(m, off): return struct.unpack("<I", m[off:off+4])[0]
# (label, mmap, page-offset)
REG = [
 ("NGD_CFG",    ngd, 0x000),
 ("NGD_STATUS", ngd, 0x004),
 ("p3_CTRL",    p3,  0x000),
 ("p3_SWOFS",   p3,  0x800),
 ("p3_EVNT",    p3,  0x818),
 ("p3_DESC",    p3,  0x81c),
 ("p3_FIFOSZ",  p3,  0x820),
 ("p4_CTRL",    p4,  0x000),
 ("p4_EVNT",    p4,  0x818),
 ("p4_DESC",    p4,  0x81c),
]
last = {n: None for n,_,_ in REG}
t0 = time.time()
end = t0 + 12.0
n = 0
print("t=ms  reg            old        -> new")
while time.time() < end:
    for name, m, off in REG:
        v = r(m, off)
        if v != last[name]:
            ms = (time.time()-t0)*1000
            print("%6.0f %-12s %s -> 0x%08x" % (ms, name, ("0x%08x"%last[name]) if last[name] is not None else "  init    ", v))
            last[name] = v
    n += 1
    time.sleep(0.002)
print("samples=%d done" % n)
