#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# m2stash_coredump.py  (runs ON the pmOS device, as root) — Plan (C) exfil.
#
# Deploy the PURE-STASH image (adsp-m2stash-signed.mbn) and read the early-boot
# stash out of the ADSP carveout via a *kernel-side* coredump (NOT /dev/mem,
# which faults on the carveout -> 900e/reboot; folyt.14 guardrail).
#
# Why a crash is needed & why it is safe here:
#   - The stash cave does ONLY loads+stores into bss 0xf0ca0000 (no diag emit,
#     no call, no frame). folyt.13 pt.2 proved this stash path runs clean (no
#     reboot). So the patched ADSP boots healthy; it does NOT self-crash.
#   - qcom PAS coredump is invoked from rproc_trigger_recovery -> so it only runs
#     when recovery is ENABLED. We therefore keep recovery=enabled and fire ONE
#     manual crash via the debugfs crash node. Single event -> single coredump ->
#     auto-reload of the (safe) patched fw. No crash-loop (unlike the emit image).
#   - 0xf0ca0000 lives in firmware PT_LOAD seg3 (VA 0xf07fc000, pa 0x8a900000,
#     memsz 0x4b1000, R+W). qcom adds each phdr as a dump segment with p_memsz,
#     so the coredump ELF contains our bss. Marker offset in seg = 0x4a4000.
#
# Flow (reversible): backup stock (once) -> coredump=enabled, recovery=enabled ->
#   swap patched fw + SSR -> verify ADSP up (no reboot) -> wait for framer bring-up
#   -> fire crash -> grab /sys/class/devcoredump/devcd*/data -> RESTORE stock + SSR
#   -> decode the stash (scan for marker 0xC0DE7066).
#
#   usage:  sudo python3 m2stash_coredump.py <patched.mbn> <raw_coredump_out>

import os, sys, time, glob, struct, subprocess

FW  = "/lib/firmware/qcom/msm8953/fairphone/fp3/adsp.mbn"
BAK = FW + ".stockbak"
STOCK_MD5 = "3ed6924da0017c5027cd78a0998bf8c3"
RP = "/sys/class/remoteproc/remoteproc2"
DBG = "/sys/kernel/debug/remoteproc/remoteproc2"

MARKER = 0xC0DE7066
FIELDS = ["marker", "r17_detected", "ctx+0xe54_togglepoll", "ctx+0xe58_toggleinput",
          "FRM_CFG(+0x400)", "FRM_STAT(+0x404)", "diag_gate_byte", "ctx+0xe08",
          "ctx+0xdb4", "STATUS2(+0x804)", "ctx_ptr", "regbase"]

def sh(cmd): return subprocess.run(cmd, shell=True, capture_output=True, text=True)
def md5(p):  r = sh("md5sum %s" % p); return r.stdout.split()[0] if r.stdout else "?"
def rd(p):
    try: return open(p).read().strip()
    except OSError: return "?"
def wr(p, v): sh("echo %s > %s" % (v, p))

def ssr():
    sh("timeout 20 sh -c 'echo stop > %s/state'" % RP); time.sleep(0.9)
    sh("timeout 20 sh -c 'echo start > %s/state'" % RP); time.sleep(0.4)

def dmesg_tail(n=25):
    return sh("dmesg | tail -n %d" % n).stdout

def clear_old_coredumps():
    for d in glob.glob("/sys/class/devcoredump/devcd*"):
        # writing 1 to .../data deletes the coredump device
        try: wr(os.path.join(d, "data"), "1")
        except Exception: pass

def grab_coredump(outp, timeout=25):
    t0 = time.time()
    while time.time() - t0 < timeout:
        ds = glob.glob("/sys/class/devcoredump/devcd*/data")
        if ds:
            data = open(ds[0], "rb").read()
            open(outp, "wb").write(data)
            # free it (allow the device to be removed)
            wr(ds[0], "1")
            return len(data), ds[0]
        time.sleep(0.3)
    return 0, None

def decode(outp):
    d = open(outp, "rb").read()
    pat = struct.pack("<I", MARKER)
    i = d.find(pat)
    if i < 0:
        print("[decode] marker 0xC0DE7066 NOT found in coredump (%d bytes)" % len(d))
        print("         -> stash may not have run, or seg not dumped. Inspect ELF phdrs.")
        # dump phdrs for diagnosis if it's an ELF
        if d[:4] == b"\x7fELF":
            phoff = struct.unpack_from("<I", d, 0x1c)[0]
            phn   = struct.unpack_from("<H", d, 0x2c)[0]
            phes  = struct.unpack_from("<H", d, 0x2a)[0]
            print("         ELF phdrs (type,off,vaddr,paddr,filesz,memsz):")
            for k in range(phn):
                t,o,v,pa,fs,ms,fl,al = struct.unpack_from("<8I", d, phoff+k*phes)
                if t == 1:
                    print("           off=0x%08x va=0x%08x pa=0x%08x fs=0x%x ms=0x%x" % (o,v,pa,fs,ms))
        return False
    vals = struct.unpack_from("<12I", d, i)
    print("[decode] marker found at coredump offset 0x%x" % i)
    print("         %-24s = 0x%08x" % (FIELDS[0], vals[0]))
    for k in range(1, 12):
        print("         %-24s = 0x%08x  (%d)" % (FIELDS[k], vals[k], vals[k]))
    print()
    print("  ==> THE ANSWER (r17 detected-bit): %s"
          % ("1 = ADSP SEES external clock toggle" if vals[1] == 1
             else "0 = ADSP does NOT detect toggle" if vals[1] == 0
             else "0x%08x (unexpected)" % vals[1]))
    print("  ==> FRM_STAT = 0x%08x (UT golden 0x060D1901 / pmOS-dead 0x0)" % vals[5])
    print("  ==> FRM_CFG  = 0x%08x (expected 0x000D0C83 both)" % vals[4])
    print("  ==> diag_gate_byte = 0x%02x (0 = diag was down at framer-bring-up)" % (vals[6] & 0xff))
    return True

def main():
    patched, outp = sys.argv[1], sys.argv[2]
    assert md5(FW) == STOCK_MD5 or os.path.exists(BAK), "current fw not stock and no .stockbak!"
    assert md5(patched) != STOCK_MD5, "patched image identical to stock?!"
    if not os.path.exists(BAK):
        sh("cp %s %s" % (FW, BAK)); print("[bak] stock -> %s" % BAK)

    print("[state] pre: fw=%s remoteproc2=%s recovery=%s coredump=%s"
          % (md5(FW), rd(RP+"/state"), rd(RP+"/recovery"), rd(RP+"/coredump")))

    clear_old_coredumps()
    wr(RP + "/coredump", "enabled")
    wr(RP + "/recovery", "enabled")   # REQUIRED: coredump runs from recovery path
    print("[cfg] coredump=%s recovery=%s" % (rd(RP+"/coredump"), rd(RP+"/recovery")))

    # swap patched fw + SSR
    sh("cp %s %s" % (patched, FW)); sh("sync")
    print("[swap] patched md5=%s -> SSR" % md5(FW))
    ssr()
    time.sleep(2.0)   # let framer bring-up (and our early stash) complete
    state = rd(RP + "/state")
    print("[boot] remoteproc2=%s" % state)
    print("---- dmesg after patched boot ----")
    print(dmesg_tail(18))
    if state != "running":
        print("!! ADSP not running after swap — restoring stock and aborting.")
        sh("cp %s %s" % (BAK, FW)); sh("sync"); ssr()
        return

    # fire ONE crash -> coredump
    clear_old_coredumps()
    print("[crash] firing %s/crash ..." % DBG)
    wr(DBG + "/crash", "1")
    n, path = grab_coredump(outp)
    if n:
        print("[coredump] %d bytes from %s -> %s" % (n, path, outp))
    else:
        print("[coredump] NONE appeared within timeout (check recovery/coredump attrs)")

    # wait for auto-recovery of the (safe) patched fw, then restore stock
    time.sleep(3.0)
    print("[post-crash] remoteproc2=%s" % rd(RP + "/state"))
    sh("cp %s %s" % (BAK, FW)); sh("sync"); ssr(); time.sleep(2.0)
    print("[restore] fw=%s (stock=%s) remoteproc2=%s recovery=%s"
          % (md5(FW), STOCK_MD5, rd(RP+"/state"), rd(RP+"/recovery")))

    if n:
        print(); decode(outp)

if __name__ == "__main__":
    main()
