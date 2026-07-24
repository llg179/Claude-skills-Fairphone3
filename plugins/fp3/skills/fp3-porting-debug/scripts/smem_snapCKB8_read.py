#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# snapCKB8 reader: after the framer-branch enable, the bounded-poll CBCR readback (CLK_OFF=bit31)
# + root RCGR (0xee012000, ROOT_OFF=bit31). Confirms whether the branch is enabled-but-not-running,
# and whether the root/source is supplying.
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; HDR=0x2ab0
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA); buf=m.read(WIN); m.close()
mg=buf[HDR:HDR+4]
print("CB8 magic:", mg, "->", "HIT" if mg==b"CB8 " else "MISS")
if mg==b"CB8 ":
    (t14,c14,cbcr14,it14,root14,
     t18,c18,cbcr18,it18,
     lastany,root18)=struct.unpack_from("<11I",buf,HDR+0x04)
    def show(name,tgt,caller,cbcr,iters,root,expect):
        if tgt!=expect:
            print(f"  {name} ({expect:#010x}): not seen"); return
        clkoff=(cbcr>>31)&1; en=cbcr&1; rootoff=(root>>31)&1
        run="RUNNING (CLK_OFF=0)" if clkoff==0 else "NOT RUNNING (CLK_OFF=1)"
        rst="root SPINS (ROOT_OFF=0)" if rootoff==0 else "root OFF (ROOT_OFF=1)"
        cleared = "never cleared (K exhausted)" if iters==0 else f"cleared after {0x80000-iters} reads"
        print(f"  {name} ({expect:#010x}): ENABLED  caller={caller:#010x}")
        print(f"      CBCR={cbcr:#010x}  EN={en}  -> {run}  [{cleared}]")
        print(f"      RCGR(0xee012000)={root:#010x} -> {rst}")
    show("0xee012014", t14,c14,cbcr14,it14,root14, 0xee012014)
    show("0xee012018", t18,c18,cbcr18,it18,root18, 0xee012018)
    print(f"  last-any framer-block target = {lastany:#010x}")
