#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Trigger slim-ngd rebind, then sample pipe3 RX + NGD over 8s with 150ms heartbeat,
# to see (a) how long the RX pipe stays connected vs the 1s capability wait, and
# (b) whether p3_EVNT (HW write ptr) ever advances = framer writing capability.
import mmap, os, struct, time, subprocess
PG=0x1000
fd=os.open("/dev/mem", os.O_RDONLY|os.O_SYNC)
def page(pa): return mmap.mmap(fd,PG,mmap.MAP_SHARED,mmap.PROT_READ,offset=pa&~(PG-1))
ngd=page(0xc141000); p3=page(0xc11a000)
def r(m,o): return struct.unpack("<I",m[o:o+4])[0]
REG=[("NGD_CFG",ngd,0),("NGD_STAT",ngd,4),("p3_CTRL",p3,0),("p3_EVNT",p3,0x818),
     ("p3_SWOF",p3,0x800),("p3_DESC",p3,0x81c)]
D="/sys/bus/platform/drivers/qcom,slim-ngd-ctrl"
os.system("echo c140000.slim-ngd > %s/unbind 2>/dev/null" % D)
time.sleep(0.3)
t0=time.time()
subprocess.Popen("echo c140000.slim-ngd > %s/bind 2>/dev/null" % D, shell=True)
last={n:None for n,_,_ in REG}; nexthb=0.0
while time.time()-t0 < 8.0:
    now=(time.time()-t0)*1000
    cur={n:r(m,o) for n,m,o in REG}
    for n in last:
        if cur[n]!=last[n]:
            print("%6.0f  CHG %-9s %s -> 0x%08x"%(now,n,("0x%08x"%last[n]) if last[n] is not None else "init",cur[n]))
            last[n]=cur[n]
    if now>=nexthb:
        print("%6.0f  HB  CFG=0x%x STAT=0x%x p3CTRL=0x%x p3EVNT=0x%x p3DESC=0x%x"%(
            now,cur["NGD_CFG"],cur["NGD_STAT"],cur["p3_CTRL"],cur["p3_EVNT"],cur["p3_DESC"]))
        nexthb=now+150
    time.sleep(0.003)
print("done")
