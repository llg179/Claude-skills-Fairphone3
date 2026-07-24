# SPDX-License-Identifier: MIT
import mmap, struct, sys
PAGE=0x1000
base=0x0c141000
off=base & (PAGE-1)
pa=base & ~(PAGE-1)
try:
    f=open("/dev/mem","r+b",0)
    m=mmap.mmap(f.fileno(), PAGE, offset=pa)
    for name,a in [("CFG",0x000),("STATUS",0x004),("RX_MSGQ_CFG",0x008)]:
        v=struct.unpack("<I", m[off+a:off+a+4])[0]
        print("%s @0x%08x = 0x%08x"%(name, base+a, v))
    rx=struct.unpack("<I", m[off+0x008:off+0x008+4])[0]
    pipe=(rx & 0x3FC)>>2
    print("RX pipe_offset = %d  -> TX pipe = %d  (mainline hardcodes rx=3,tx=4)"%(pipe, pipe+1))
except Exception as e:
    print("ERR:", e)
