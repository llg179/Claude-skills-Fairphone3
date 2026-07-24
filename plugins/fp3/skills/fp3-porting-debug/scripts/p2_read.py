#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# P2 reader — works on pmOS (mainline) and UT (downstream 4.9).
# Reads: enabled clocks (ec>0), focusing on lpass/slim/audio; codec+slimbus enum state.
import os,glob,re,sys
def clk_summary():
    p="/sys/kernel/debug/clk/clk_summary"
    out=[]
    if os.path.exists(p):
        for ln in open(p):
            c=ln.split()
            if len(c)<7: continue
            try: ec=int(c[1])
            except: continue
            if ec>0: out.append((c[0],c[1],(c[4] if len(c)>4 else "?")))
    else:  # fallback: per-clock dirs (older framework)
        for d in glob.glob("/sys/kernel/debug/clk/*/enable_count"):
            try: ec=int(open(d).read())
            except: continue
            if ec>0:
                name=d.split("/")[-2]
                rate="?"
                rp=os.path.join(os.path.dirname(d),"rate")
                if os.path.exists(rp): rate=open(rp).read().strip()
                out.append((name,str(ec),rate))
    return out
cl=clk_summary()
print("=== ENABLED clocks (ec>0): %d total ==="%len(cl))
key=[c for c in cl if re.search("lpass|slim|audio|q6|mclk|bb_clk|div_clk|osr",c[0],re.I)]
print("--- lpass/slim/audio/mclk related (%d) ---"%len(key))
for n,e,r in key: print("  %-45s ec=%s rate=%s"%(n,e,r))
if not key: print("  (none)")
print("--- ALL enabled (name ec rate) ---")
for n,e,r in sorted(cl): print("  %-45s %s %s"%(n,e,r))
print("\n=== slimbus enumeration ===")
for d in sorted(glob.glob("/sys/bus/slimbus/devices/*")):
    la=os.path.join(d,"laddr")
    lav=open(la).read().strip() if os.path.exists(la) else "n/a"
    print("  %s laddr=%s"%(os.path.basename(d),lav))
print("\n=== sound cards ===")
try: print("  "+open("/proc/asound/cards").read().replace("\n","\n  "))
except: print("  none")
