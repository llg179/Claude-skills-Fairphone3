#!/usr/bin/env python3 -u
# stock_ulog_probe.py (runs ON pmOS device as root) — STOCK image, NO firmware patch.
#
# Goal: capture the ADSP's OWN boot-time ULOG (framer-mode / ref-clock / gear log
# lines) which decide the SLIMbus framer bring-up. The ULOG ring wrapped by +55s in
# the folyt.17 dump, so we regenerate it: SSR-restart the (stock) ADSP -> it re-runs
# framer bring-up (~200ms) -> fire ONE crash within ~1s -> the coredump contains the
# FRESH ULOG buffer. Then host-side we scan the coredump for the clock/framer strings.
#
# Fully reversible, stock throughout (no swap): SSR-restart of stock is proven safe
# (folyt.16). recovery=enabled + single crash -> single coredump -> clean auto-reload.
#
#   usage:  sudo python3 -u stock_ulog_probe.py <raw_coredump_out>

import os, sys, time, glob, struct, subprocess

FW  = "/lib/firmware/qcom/msm8953/fairphone/fp3/adsp.mbn"
BAK = FW + ".stockbak"
STOCK_MD5 = "3ed6924da0017c5027cd78a0998bf8c3"
RP  = "/sys/class/remoteproc/remoteproc2"
DBG = "/sys/kernel/debug/remoteproc/remoteproc2"

def log(*a): print(*a, flush=True)
def sh(c): return subprocess.run(c, shell=True, capture_output=True, text=True)
def md5(p): r=sh("md5sum %s"%p); return r.stdout.split()[0] if r.stdout else "?"
def rd(p):
    try: return open(p).read().strip()
    except OSError: return "?"
def wr(p,v): sh("echo %s > %s"%(v,p))
def clear_cd():
    for dd in glob.glob("/sys/class/devcoredump/devcd*"):
        try: wr(os.path.join(dd,"data"),"1")
        except Exception: pass
def grab(outp,timeout=35):
    t0=time.time()
    while time.time()-t0<timeout:
        ds=glob.glob("/sys/class/devcoredump/devcd*/data")
        if ds:
            data=open(ds[0],"rb").read(); open(outp,"wb").write(data); wr(ds[0],"1")
            return len(data),ds[0]
        time.sleep(0.2)
    return 0,None

def main():
    outp=sys.argv[1]
    log("[pre] fw=%s state=%s recovery=%s coredump=%s"%(md5(FW),rd(RP+"/state"),rd(RP+"/recovery"),rd(RP+"/coredump")))
    assert md5(FW)==STOCK_MD5, "fw not stock! refuse (this probe is stock-only)"
    wr(RP+"/coredump","enabled"); wr(RP+"/recovery","enabled")
    clear_cd()

    # SSR-restart stock ADSP so framer bring-up ULOG is FRESH
    log("[ssr] stop adsp"); sh("timeout 20 sh -c 'echo stop > %s/state'"%RP); time.sleep(0.8)
    log("[ssr] start adsp"); sh("timeout 25 sh -c 'echo start > %s/state'"%RP)
    # poll until running (fast) so we crash right after bring-up while ULOG is fresh
    t0=time.time(); st="?"
    while time.time()-t0<20:
        st=rd(RP+"/state")
        if st=="running": break
        time.sleep(0.1)
    log("[ssr] state=%s after %.2fs"%(st,time.time()-t0))
    if st!="running":
        log("[abort] adsp not running after SSR-restart; not crashing."); return
    # small settle so framer bring-up + its ULOG have emitted, but ring not yet wrapped
    time.sleep(0.6)

    clear_cd()
    log("[crash] firing crash (background) ...")
    sh("timeout 45 sh -c 'echo 1 > %s/crash' >/dev/null 2>&1 &"%DBG)
    n,path=grab(outp)
    if n: log("[coredump] %d bytes from %s -> %s"%(n,path,outp))
    else: log("[coredump] NONE within timeout")

    time.sleep(2.0)
    # recover: ensure adsp back (stock). If offline, SSR start.
    if rd(RP+"/state")!="running":
        sh("timeout 25 sh -c 'echo start > %s/state'"%RP); time.sleep(2.0)
    wr(RP+"/coredump","disabled")
    log("[post] fw=%s state=%s coredump=%s"%(md5(FW),rd(RP+"/state"),rd(RP+"/coredump")))

if __name__=="__main__": main()
