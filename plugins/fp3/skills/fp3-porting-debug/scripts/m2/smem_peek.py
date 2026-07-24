#!/usr/bin/env python3
# Read SMEM region base via /dev/mem (RAM read; blocked if STRICT_DEVMEM=y).
import mmap, os, sys
PG = 0x1000
def rdblock(pa, n):
    fd = os.open("/dev/mem", os.O_RDONLY | os.O_SYNC)
    base = pa & ~(PG - 1); off = pa - base
    span = ((off + n + PG - 1) // PG) * PG
    m = mmap.mmap(fd, span, mmap.MAP_SHARED, mmap.PROT_READ, offset=base)
    b = m[off:off + n]; m.close(); os.close(fd); return b
pa = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0x86300000
n  = int(sys.argv[2], 0) if len(sys.argv) > 2 else 256
try:
    b = rdblock(pa, n)
    print("OK read %#x (%d bytes)" % (pa, n))
    for i in range(0, min(n, 256), 16):
        print("%#010x " % (pa + i) + b[i:i+16].hex())
except Exception as e:
    print("SMEM read FAILED @%#x: %s" % (pa, e))
