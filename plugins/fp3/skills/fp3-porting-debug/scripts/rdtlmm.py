# SPDX-License-Identifier: GPL-2.0-or-later
import mmap, struct
PAGE=0x1000
def rd(pa):
    base=pa & ~(PAGE-1); off=pa & (PAGE-1)
    f=open("/dev/mem","r+b",0); m=mmap.mmap(f.fileno(),PAGE,offset=base)
    v=struct.unpack("<I", m[off:off+4])[0]; m.close(); f.close(); return v
for g in (70,71,72):
    ctl=0x01000000 + 0x1000*g
    v=rd(ctl); mux=(v>>2)&0xF; pull=v&0x3; drv=(v>>6)&0x7; oe=(v>>9)&1
    print("gpio%d ctl=0x%08x val=0x%08x mux=%d pull=%d drv=%d oe=%d  (lpass_slimbus wants mux=1)"%(g,ctl,v,mux,pull,drv,oe))
