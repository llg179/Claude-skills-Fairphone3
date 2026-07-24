#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# m2emit_capture.py  (runs ON the pmOS device, as root)
# NON-CRASHING deploy+capture for adsp-m2emit-signed.mbn (toggle-return trace).
#
# Flow (fully reversible, NO coredump):
#   1. back up stock adsp.mbn -> .stockbak (once),
#   2. start continuous DIAG capture: arm F3 mask ALL_ENABLED on every DIAG_CNTL,
#      re-discover rpmsg nodes by NAME across the SSR (they renumber),
#   3. at t=1.5s: cp the PATCHED fw over adsp.mbn, then SSR (stop/start
#      remoteproc2) => the patched ADSP reloads and re-runs framer bring-up ->
#      toggle-detection -> our hook (stash + self-gated f01b161c try-emit),
#   4. keep capturing to <secs> (covers the ~5s NGD capability exchange, where
#      the framer code may re-run with diag already up => LIVE emit),
#   5. RESTORE stock fw + SSR back to a clean ADSP,
#   6. health check + grep the capture for our emit ("Rx iovec" descriptor +
#      the 5 arg words = detected, ctx+0xe54, ctx+0xe58, FRM_CFG, FRM_STAT).
#
#   usage:  python3 m2emit_capture.py <secs> <patched.mbn> <outfile>
import os, sys, time, glob, struct, select, subprocess, re

FW = "/lib/firmware/qcom/msm8953/fairphone/fp3/adsp.mbn"
BAK = FW + ".stockbak"
STOCK_MD5 = "3ed6924da0017c5027cd78a0998bf8c3"

def feature_mask():
    # DIAG_CTRL_FEATURE_MASK id=8 — REQUIRED handshake before the ADSP streams F3
    # (diagtap.py sends this first; without it the ADSP diag emits nothing).
    return struct.pack("<III", 8, 6, 2) + bytes([0x01, 0x00])

def f3_ctrl_mask():
    return struct.pack("<IIBBBHHII", 11, 11+4, 1, 2, 0, 0, 0, 1, 0xFFFFFFFF)

def sh(cmd): return subprocess.run(cmd, shell=True, capture_output=True, text=True)

def md5(p):
    r = sh("md5sum %s" % p); return r.stdout.split()[0] if r.stdout else "?"

def ssr():
    # timeout-guarded so a wedged remoteproc stop/start can never hang the script
    sh("timeout 20 sh -c 'echo stop > /sys/class/remoteproc/remoteproc2/state'"); time.sleep(0.9)
    sh("timeout 20 sh -c 'echo start > /sys/class/remoteproc/remoteproc2/state'"); time.sleep(0.3)

def discover():
    d, c = [], []
    for nf in glob.glob("/sys/class/rpmsg/rpmsg*/name"):
        try: name = open(nf).read().strip()
        except OSError: continue
        node = "/dev/" + nf.split("/")[-2]
        if not os.path.exists(node): continue
        if name == "DIAG": d.append(node)
        elif name == "DIAG_CNTL": c.append(node)
    return sorted(set(d)), sorted(set(c))

def unescape(r):
    u = bytearray(); esc = False
    for b in r:
        if esc: u.append(b ^ 0x20); esc = False
        elif b == 0x7d: esc = True
        else: u.append(b)
    return bytes(u)

def main():
    secs = float(sys.argv[1]); patched = sys.argv[2]; outp = sys.argv[3]
    assert md5(FW) == STOCK_MD5 or os.path.exists(BAK), "current fw not stock and no .stockbak!"
    if not os.path.exists(BAK):
        sh("cp %s %s" % (FW, BAK)); print("[bak] stock -> %s" % BAK)
    assert md5(patched) != STOCK_MD5, "patched image is identical to stock?!"

    raw = open(outp, "wb"); dfds = {}; cfds = {}
    def openall():
        d, c = discover()
        for p in d:
            if p not in dfds:
                try: dfds[p] = os.open(p, os.O_RDWR | os.O_NONBLOCK)
                except OSError: pass
        for p in c:
            if p not in cfds:
                try: cfds[p] = os.open(p, os.O_RDWR | os.O_NONBLOCK)
                except OSError: pass
    def arm():
        for p, fd in list(cfds.items()):
            try:
                os.write(fd, feature_mask())   # feature handshake FIRST
                os.write(fd, f3_ctrl_mask())   # then F3 ALL_ENABLED
            except OSError:
                try: os.close(fd)
                except OSError: pass
                del cfds[p]
    openall(); arm()
    t0 = time.time(); last_arm = t0; swapped = False; total = 0
    while time.time() - t0 < secs:
        now = time.time()
        if now - t0 > 1.5 and not swapped:
            # ☠️ recovery=disabled FIRST: a crash of the patched fw stays a single
            # event (no auto-reload crash-loop -> no watchdog reboot). This is the
            # guardrail whose omission rebooted the device last time.
            sh("echo disabled > /sys/class/remoteproc/remoteproc2/recovery")
            print("[recovery] disabled=%s" % open("/sys/class/remoteproc/remoteproc2/recovery").read().strip())
            sh("cp %s %s" % (patched, FW)); sh("sync")
            print("[swap] patched fw md5=%s -> SSR" % md5(FW)); ssr(); swapped = True
        if now - last_arm > 0.15:
            openall(); arm(); last_arm = now
        rl = list(dfds.values())
        if rl:
            r, _, _ = select.select(rl, [], [], 0.1)
            for fd in r:
                try: b = os.read(fd, 1 << 16)
                except (BlockingIOError, OSError):
                    for p, f in list(dfds.items()):
                        if f == fd:
                            try: os.close(f)
                            except OSError: pass
                            del dfds[p]
                    continue
                if b: raw.write(b); total += len(b)
        else:
            time.sleep(0.05)
    raw.close()
    # --- restore stock, SSR clean, re-enable recovery ---
    sh("cp %s %s" % (BAK, FW)); sh("sync"); ssr(); time.sleep(2.0)
    sh("echo enabled > /sys/class/remoteproc/remoteproc2/recovery")
    state = open("/sys/class/remoteproc/remoteproc2/state").read().strip()
    rec = open("/sys/class/remoteproc/remoteproc2/recovery").read().strip()
    print("[restore] fw md5=%s (stock=%s)  remoteproc2=%s  recovery=%s" % (md5(FW), STOCK_MD5, state, rec))
    print("[done] %d bytes -> %s" % (total, outp))

    # --- grep for our emit ---
    d = open(outp, "rb").read()
    frames = [unescape(fr) for fr in d.split(b"\x7e") if len(fr) > 4]
    hit = 0
    for f in frames:
        if b"iovec" in f or b"Rx iov" in f:
            hit += 1
            print("  EMIT frame len=%d hex=%s" % (len(f), f[:64].hex()))
            for m in re.finditer(rb"[ -~]{5,}", f):
                print("    STR:", m.group().decode("ascii", "replace")[:120])
    # also raw scan for the descriptor hash 0xde5a9f51 (LE 51 9f 5a de)
    hh = bytes.fromhex("519f5ade")
    for i, f in enumerate(frames):
        j = f.find(hh)
        if j >= 0:
            args = f[j+4:j+4+20]
            print("  HASH-hit frame#%d: 5 args = %s" % (i, args.hex()))
    print("[grep] %d frames, %d iovec-emit hits" % (len(frames), hit))
    if hit == 0:
        print("  (no live emit -> diag was down at every framer-toggle run; "
              "the values ARE in bss 0xf0ca0000 -> needs the dedicated late-replay hook)")

if __name__ == "__main__":
    main()
