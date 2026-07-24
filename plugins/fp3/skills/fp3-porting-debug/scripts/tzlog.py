#!/usr/bin/env python3
# tzlog.py — TrustZone (TZBSP) diag-log reader for the FP3 (MSM8953).
#
# Reads the TZ diagnostic buffer that TZ publishes to HLOS and dumps the
# general log ring (+ boot/reset/interrupt tables). Used to ask "what does the
# TZ itself say about the PAS auth_and_reset" — two-sided UT(PIL) vs pmOS(PAS).
# Run as root on-device:  echo <pw> | sudo -S python3 /tmp/tzlog.py [label]
#
# MECHANISM (from downstream drivers/firmware/qcom/tz_log.c probe):
#   The DT node tz-log@08600720 (reg = <0x08600720 0x2000>) is NOT the buffer;
#   word0 at PA 0x08600720 is a POINTER to the real diag buffer PA. The driver
#   does: phy = readl(0x08600720); ioremap(phy, 0x2000); parse tzdbg_t there.
#   So we: read the u32 pointer, then mmap that PA and parse.
#
# ☠️ SAFETY (fp3-kernel-test rule 5): the diag-buffer PA is read from TZ's own
# pointer, exactly as the downstream driver does — TZ deliberately exposes this
# region to HLOS (tz-log debugfs). It is NOT a blind PA scan. Still: run on the
# UT ORACLE FIRST (its stock kernel binds this driver → proves the region is
# safely AP-readable) before pmOS. Do NOT point this at any other PA.
#
# tzdbg_t header layout (self-describing; offsets from buffer start):
#   0x00 magic_num  0x04 version   0x08 cpu_count
#   0x0c vmid_off   0x10 boot_off  0x14 reset_off  0x18 int_off
#   0x1c ring_off   0x20 ring_len  0x24 wakeup_off
# ring at ring_off: tzdbg_log_pos_t{u16 wrap; u16 offset} then log_buf[ring_len].
import mmap, struct, sys

PTR_PA   = 0x08600720   # DT tz-log window; word0 = diag buffer PA
BUF_LEN  = 0x2000       # DT reg size

def rd(fd, pa, n):
    base = pa & ~0xfff
    off  = pa - base
    span = ((off + n + 0xfff) & ~0xfff)
    m = mmap.mmap(fd.fileno(), span, mmap.MAP_SHARED, mmap.PROT_READ, offset=base)
    b = m[off:off+n]
    m.close()
    return b

def main():
    label = sys.argv[1] if len(sys.argv) > 1 else "tzlog"
    try:
        fd = open("/dev/mem", "rb")
    except PermissionError:
        sys.exit("need root: echo <pw> | sudo -S python3 %s" % sys.argv[0])
    with fd:
        phy = struct.unpack("<I", rd(fd, PTR_PA, 4))[0]
        print("[%s] tzdiag pointer @0x%08x -> diag PA 0x%08x" % (label, PTR_PA, phy))
        if phy == 0 or phy == 0xffffffff:
            sys.exit("  ! pointer looks invalid (0x%08x) — driver may not have run" % phy)
        buf = rd(fd, phy, BUF_LEN)
    (magic, ver, cpu, vmid_o, boot_o, reset_o, int_o,
     ring_o, ring_l, wake_o) = struct.unpack_from("<10I", buf, 0)
    print("  magic=0x%08x version=0x%08x cpu_count=%d" % (magic, ver, cpu))
    print("  offs: vmid=0x%x boot=0x%x reset=0x%x int=0x%x ring=0x%x(len=0x%x) wake=0x%x"
          % (vmid_o, boot_o, reset_o, int_o, ring_o, ring_l, wake_o))
    if magic != 0x747a6461 and magic == 0:      # 'tzda' or check nonzero
        print("  ! magic zero — buffer may be empty/uninitialised")
    # --- boot_info table (per-CPU warmboot/PC counters; PAS boot leaves traces) ---
    if 0 < boot_o < BUF_LEN and cpu and cpu <= 8:
        print("  boot_info[%d]:" % cpu)
        for c in range(cpu):
            base = boot_o + c*24
            if base+24 > len(buf): break
            wbe, wbx, pce, pcx, wj, sp = struct.unpack_from("<6I", buf, base)
            print("    cpu%d wb_ent=%d wb_exit=%d pc_ent=%d pc_exit=%d warmjmp=0x%08x"
                  % (c, wbe, wbx, pce, pcx, wj))
    # --- general log ring (the human-readable TZ log) ---
    if 0 < ring_o < BUF_LEN:
        wrap, off = struct.unpack_from("<HH", buf, ring_o)
        logbuf = buf[ring_o+4 : ring_o+4+ring_l]
        print("  ring: wrap=%d offset=%d len=0x%x" % (wrap, off, ring_l))
        if wrap == 0:
            text = logbuf[:off]
        else:
            text = logbuf[off:] + logbuf[:off]   # unwrap
        printable = bytes(ch if 9 <= ch <= 126 else 0x2e for ch in text)
        try:
            s = printable.decode("ascii", "replace")
        except Exception:
            s = repr(printable)
        print("  ---- TZ LOG (%d bytes) ----" % len(text))
        sys.stdout.write(s)
        print("\n  ---- end TZ LOG ----")

if __name__ == "__main__":
    main()
