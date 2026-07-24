#!/usr/bin/env python3 -u
# SPDX-License-Identifier: MIT
# m2_c2_crash.py  (runs ON the pmOS device, as root) — Plan (C') exfil.
#
# DIFFERENCE vs m2stash_coredump.py (folyt.16 lesson):
#   The patched pure-stash image COLD-BOOTS (PAS) fine but its SSR-warm-reload
#   (echo stop; echo start) HANGS at start -> the original swap+SSR step wedged
#   the ADSP offline before the crash ever fired, and produced no coredump.
#
#   (C') therefore assumes the patched image is ALREADY COLD-BOOTED and running
#   (operator did: cp patched adsp.mbn; reboot; wait for pmOS). We do NOT swap or
#   SSR here. We just fire ONE crash: the qcom PAS coredump is created (from
#   rproc_trigger_recovery) BEFORE the auto-reload start (which will hang) -> so
#   the coredump appears, we grab it, then restore stock + recover.
#
#   Logging is UNBUFFERED (flush=True everywhere + `#!/usr/bin/env python3 -u`)
#   so a silent death still leaves a trace (folyt.16: buffered log was lost).
#
#   usage:  sudo python3 -u m2_c2_crash.py <patched.mbn> <raw_coredump_out>

import os, sys, time, glob, struct, subprocess

FW  = "/lib/firmware/qcom/msm8953/fairphone/fp3/adsp.mbn"
BAK = FW + ".stockbak"
STOCK_MD5 = "3ed6924da0017c5027cd78a0998bf8c3"
RP  = "/sys/class/remoteproc/remoteproc2"
DBG = "/sys/kernel/debug/remoteproc/remoteproc2"

MARKER = 0xC0DE7066
FIELDS = ["marker", "r17_detected", "ctx+0xe54_togglepoll", "ctx+0xe58_toggleinput",
          "FRM_CFG(+0x400)", "FRM_STAT(+0x404)", "diag_gate_byte", "ctx+0xe08",
          "ctx+0xdb4", "STATUS2(+0x804)", "ctx_ptr", "regbase"]

def log(*a): print(*a, flush=True)
def sh(cmd): return subprocess.run(cmd, shell=True, capture_output=True, text=True)
def md5(p):  r = sh("md5sum %s" % p); return r.stdout.split()[0] if r.stdout else "?"
def rd(p):
    try: return open(p).read().strip()
    except OSError: return "?"
def wr(p, v): sh("echo %s > %s" % (v, p))

def dmesg_tail(n=25): return sh("dmesg | tail -n %d" % n).stdout

def clear_old_coredumps():
    for d in glob.glob("/sys/class/devcoredump/devcd*"):
        try: wr(os.path.join(d, "data"), "1")
        except Exception: pass

def grab_coredump(outp, timeout=30):
    t0 = time.time()
    while time.time() - t0 < timeout:
        ds = glob.glob("/sys/class/devcoredump/devcd*/data")
        if ds:
            data = open(ds[0], "rb").read()
            open(outp, "wb").write(data)
            wr(ds[0], "1")   # free it
            return len(data), ds[0]
        time.sleep(0.3)
    return 0, None

def decode(outp):
    d = open(outp, "rb").read()
    pat = struct.pack("<I", MARKER)
    i = d.find(pat)
    if i < 0:
        log("[decode] marker 0xC0DE7066 NOT found in coredump (%d bytes)" % len(d))
        log("         -> stash may not have run, or seg not dumped. ELF phdrs:")
        if d[:4] == b"\x7fELF":
            phoff = struct.unpack_from("<I", d, 0x1c)[0]
            phn   = struct.unpack_from("<H", d, 0x2c)[0]
            phes  = struct.unpack_from("<H", d, 0x2a)[0]
            for k in range(phn):
                t,o,v,pa,fs,ms,fl,al = struct.unpack_from("<8I", d, phoff+k*phes)
                if t == 1:
                    log("           off=0x%08x va=0x%08x pa=0x%08x fs=0x%x ms=0x%x" % (o,v,pa,fs,ms))
        return False
    vals = struct.unpack_from("<12I", d, i)
    log("[decode] marker found at coredump offset 0x%x" % i)
    log("         %-24s = 0x%08x" % (FIELDS[0], vals[0]))
    for k in range(1, 12):
        log("         %-24s = 0x%08x  (%d)" % (FIELDS[k], vals[k], vals[k]))
    log("")
    log("  ==> THE ANSWER (r17 detected-bit): %s"
        % ("1 = ADSP SEES external clock toggle" if vals[1] == 1
           else "0 = ADSP does NOT detect toggle" if vals[1] == 0
           else "0x%08x (unexpected)" % vals[1]))
    log("  ==> FRM_STAT = 0x%08x (UT golden 0x060D1901 / pmOS-dead 0x0)" % vals[5])
    log("  ==> FRM_CFG  = 0x%08x (expected 0x000D0C83 both)" % vals[4])
    log("  ==> diag_gate_byte = 0x%02x (0 = diag down at framer-bring-up)" % (vals[6] & 0xff))
    return True

def recover_stock():
    log("[recover] restoring stock fw + bringing ADSP back")
    sh("cp %s %s" % (BAK, FW)); sh("sync")
    # adsp is likely offline (hung auto-reload); a plain start of STOCK works
    # (folyt.16 control). Try stop (harmless if already stopped) then start.
    sh("timeout 20 sh -c 'echo stop > %s/state'" % RP); time.sleep(0.8)
    r = sh("timeout 30 sh -c 'echo start > %s/state'" % RP); time.sleep(2.0)
    log("[recover] fw=%s (stock=%s) remoteproc2=%s" % (md5(FW), STOCK_MD5, rd(RP+"/state")))
    if rd(RP+"/state") != "running":
        log("[recover] !! ADSP still not running via SSR-start -> REBOOT NEEDED (cold PAS boot of stock).")

def main():
    patched, outp = sys.argv[1], sys.argv[2]
    cur = md5(FW)
    log("[pre] fw=%s state=%s recovery=%s coredump=%s uptime=%s"
        % (cur, rd(RP+"/state"), rd(RP+"/recovery"), rd(RP+"/coredump"), rd("/proc/uptime")))

    # (C') preconditions: the PATCHED image must be the one currently cold-booted.
    assert os.path.exists(BAK), "no .stockbak — refusing (need stock to restore)!"
    if cur == STOCK_MD5:
        log("[abort] current fw is STOCK, not the patched image. (C') needs the patched")
        log("        image COLD-BOOTED first:  cp %s %s; sync; reboot" % (patched, FW))
        return
    if cur != md5(patched):
        log("[abort] current fw (%s) != expected patched (%s)." % (cur, md5(patched)))
        return
    if rd(RP+"/state") != "running":
        log("[abort] remoteproc2 not running (%s) — patched image not healthy; nothing to dump." % rd(RP+"/state"))
        return
    log("[ok] patched image is cold-booted and running. proceeding to single-crash exfil.")

    wr(RP + "/coredump", "enabled")
    wr(RP + "/recovery", "enabled")   # coredump is generated from the recovery path
    log("[cfg] coredump=%s recovery=%s" % (rd(RP+"/coredump"), rd(RP+"/recovery")))

    clear_old_coredumps()

    # Fire the crash in the BACKGROUND: the write may block on the hung auto-reload
    # start, but the coredump is created BEFORE that -> we poll for it concurrently.
    log("[crash] firing %s/crash (backgrounded) ..." % DBG)
    sh("timeout 45 sh -c 'echo 1 > %s/crash' >/dev/null 2>&1 &" % DBG)

    n, path = grab_coredump(outp, timeout=35)
    if n:
        log("[coredump] %d bytes from %s -> %s" % (n, path, outp))
    else:
        log("[coredump] NONE within timeout. dmesg tail:")
        log(dmesg_tail(20))

    log("[post-crash] remoteproc2=%s" % rd(RP + "/state"))
    recover_stock()

    if n:
        log("")
        decode(outp)

if __name__ == "__main__":
    main()
