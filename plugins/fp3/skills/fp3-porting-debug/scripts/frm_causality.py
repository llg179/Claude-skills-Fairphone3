#!/usr/bin/env python3
# Causality test on the framer state bits that differ working(UT)->dead(pmOS):
#   +0x804 bit23 (UT=1,pmOS=0)  and  +0x430 bit4 (UT=1,pmOS=0).
# Set each from the AP via /dev/mem and watch FRM_STAT(+0x404). If FRM_STAT goes
# nonzero, the bit is an AP-settable LEVER (breakthrough). If the write doesn't
# latch, the block rejects AP writes there. If it latches but FRM_STAT stays 0,
# it's an inert status/marker. Reversible (we only OR bits; report read-backs).
import mmap, os, struct, glob, time

BASE = 0x0c140000; PGSZ = 0x1000
def ctrls():
    c = glob.glob("/sys/devices/platform/soc*/c140000.slim*/power/control")
    c += glob.glob("/sys/devices/platform/soc*/c140000.slim*/*slim-ngd*/power/control")
    return c
def force(v):
    for p in ctrls():
        try: open(p,"w").write(v)
        except Exception: pass

def mem(prot):
    return os.open("/dev/mem", os.O_RDWR|os.O_SYNC if (prot & mmap.PROT_WRITE) else os.O_RDONLY|os.O_SYNC)

def rd(off):
    f=os.open("/dev/mem",os.O_RDONLY|os.O_SYNC)
    try:
        m=mmap.mmap(f,PGSZ,mmap.MAP_SHARED,mmap.PROT_READ,offset=(BASE+off)&~0xfff)
        v=struct.unpack_from("<I",m,(BASE+off)&0xfff)[0]; m.close()
    finally: os.close(f)
    return v
def setbit(off,bit):
    f=os.open("/dev/mem",os.O_RDWR|os.O_SYNC)
    try:
        pg=(BASE+off)&~0xfff; d=(BASE+off)&0xfff
        m=mmap.mmap(f,PGSZ,mmap.MAP_SHARED,mmap.PROT_READ|mmap.PROT_WRITE,offset=pg)
        cur=struct.unpack_from("<I",m,d)[0]
        struct.pack_into("<I",m,d,cur|bit)
        m.flush(); rb=struct.unpack_from("<I",m,d)[0]; m.close()
    finally: os.close(f)
    return cur, rb

force("on"); time.sleep(0.3)
print("# frm causality", time.strftime("%H:%M:%S"))
print("baseline: +0x404 FRM_STAT=0x%08x +0x430=0x%08x +0x804=0x%08x"%(rd(0x404),rd(0x430),rd(0x804)))
for off,bit,name in [(0x804,0x00800000,"+0x804 bit23"),(0x430,0x00000010,"+0x430 bit4")]:
    cur,rb=setbit(off,bit)
    time.sleep(0.2)
    st=rd(0x404)
    print("set %s: before=0x%08x readback=0x%08x latched=%s -> FRM_STAT=0x%08x %s"%(
        name,cur,rb,("YES" if rb==(cur|bit) else "NO"),st,
        ("<<< LEVER! FRAMER ACTIVATED" if st!=0 else "(no framing)")))
print("final: +0x404 FRM_STAT=0x%08x +0x804=0x%08x"%(rd(0x404),rd(0x804)))
force("auto")
print("FRM-CAUSALITY-DONE")
