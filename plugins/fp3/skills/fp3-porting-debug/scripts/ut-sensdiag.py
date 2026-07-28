#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# ut-sensdiag.py — Ubuntu Touch (downstream /dev/diag) oracle capture of ADSP F3,
# written as a RAW 0x7E-framed binary so the pmOS-side parser (sensdiag.py) can be
# run byte-for-byte identically on both sides.  Constants: see ut-diag-adsp.py.
#   ut-sensdiag.py <secs> [outfile] [ssr]
import os, sys, struct, fcntl, time, select, glob

DEV = "/dev/diag"
DIAG_IOCTL_SWITCH_LOGGING = 7
MEMORY_DEVICE_MODE = 2
USER_SPACE_DATA_TYPE = 0x20
DIAG_CON_APSS = 0x01
DIAG_CON_LPASS = 0x04
DIAG_CON_UPD_AUDIO = 0x2000
DIAG_CON_UPD_SENSORS = 0x1000   # sensors user-PD on LPASS (if this build has one)
DIAG_CMD_MSG_CONFIG = 0x7D
OP_SET_ALL_MSG_MASK = 5

_tab = []
for i in range(256):
    c = i
    for _ in range(8):
        c = (c >> 1) ^ 0x8408 if (c & 1) else (c >> 1)
    _tab.append(c & 0xFFFF)


def crc_ccitt(buf, crc=0xFFFF):
    for b in buf:
        crc = (crc >> 8) ^ _tab[(crc ^ b) & 0xFF]
    return crc & 0xFFFF


def hdlc_encode(payload):
    fcs = (~crc_ccitt(payload)) & 0xFFFF
    body = bytes(payload) + bytes([fcs & 0xFF, (fcs >> 8) & 0xFF])
    out = bytearray()
    for b in body:
        if b in (0x7E, 0x7D):
            out.append(0x7D); out.append(b ^ 0x20)
        else:
            out.append(b)
    out.append(0x7E)
    return bytes(out)


def switch_logging(fd, mode, periph_mask):
    buf = bytearray(struct.pack("<IIIBBBBi", mode, periph_mask, 0, 0, 0, 0, 0, 0))
    fcntl.ioctl(fd, DIAG_IOCTL_SWITCH_LOGGING, buf, True)


def set_all_f3(fd):
    cmd = bytes([DIAG_CMD_MSG_CONFIG, OP_SET_ALL_MSG_MASK, 0x00, 0x00,
                 0xFF, 0xFF, 0xFF, 0xFF])
    os.write(fd, struct.pack("<i", USER_SPACE_DATA_TYPE) + hdlc_encode(cmd))


def find_adsp_subsys():
    for d in glob.glob('/sys/bus/msm_subsys/devices/subsys*'):
        try:
            n = open(d + '/name').read().strip()
        except OSError:
            continue
        if n in ('adsp', 'lpass', 'slpi'):
            return d, n
    return None, None


def main():
    dur = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0
    outp = sys.argv[2] if len(sys.argv) > 2 else "/tmp/ut_adsp_f3.bin"
    do_ssr = 'ssr' in sys.argv[3:]

    # Boot-armed use: /dev/diag may not exist yet.  Wait for it, bounded, so the
    # unit can be started very early (the ADSP comes out of reset at ~t=22.5s).
    for _ in range(600):
        if os.path.exists(DEV):
            break
        time.sleep(0.1)
    else:
        sys.stderr.write("no %s after 60s\n" % DEV)
        return

    fd = os.open(DEV, os.O_RDWR)
    mask = (DIAG_CON_LPASS | DIAG_CON_APSS |
            DIAG_CON_UPD_AUDIO | DIAG_CON_UPD_SENSORS)
    switch_logging(fd, MEMORY_DEVICE_MODE, mask)
    time.sleep(0.2)
    set_all_f3(fd)
    sys.stderr.write("diag: mask=0x%x, %.1fs -> %s\n" % (mask, dur, outp))

    if do_ssr:
        # Graceful adsp-loader put/get (subsystem_put -> subsystem_get).  This is
        # deliberately NOT a crash-restart: the adsp subsys here has
        # restart_level=SYSTEM, so a crash would reboot the whole phone.
        d, n = find_adsp_subsys()
        boot = '/sys/kernel/boot_adsp/boot'
        st = (d + '/state') if d else None

        def state():
            try:
                return open(st).read().strip() if st else '?'
            except OSError:
                return '?'
        if os.path.exists(boot):
            try:
                sys.stderr.write("[ssr] before: state=%s\n" % state())
                with open(boot, 'w') as f:
                    f.write('0')
                time.sleep(1.5)
                sys.stderr.write("[ssr] after put: state=%s\n" % state())
                with open(boot, 'w') as f:
                    f.write('1')
                sys.stderr.write("[ssr] get issued, state=%s\n" % state())
            except OSError as e:
                sys.stderr.write("[ssr] FAILED: %s\n" % e)
        else:
            sys.stderr.write("[ssr] no /sys/kernel/boot_adsp/boot\n")

    nframes = 0
    # monotonic: the wall clock jumps mid-boot (RTC/NTP), which made an
    # earlier time.time() loop terminate instantly and capture nothing.
    t0 = time.monotonic(); last_arm = t0
    with open(outp, 'wb') as fh:
        while time.monotonic() - t0 < dur:
            if time.monotonic() - last_arm > 0.5:
                try:
                    set_all_f3(fd)
                except OSError:
                    pass
                last_arm = time.monotonic()
            r, _, _ = select.select([fd], [], [], 0.5)
            if not r:
                continue
            data = os.read(fd, 1 << 16)
            if len(data) < 8:
                continue
            dtype, ndata = struct.unpack_from("<ii", data, 0)
            off = 8
            for _ in range(ndata):
                if off + 4 > len(data):
                    break
                (ln,) = struct.unpack_from("<i", data, off); off += 4
                if ln <= 0 or off + ln > len(data):
                    break
                frame = data[off:off + ln]; off += ln
                fh.write(frame)
                if not frame.endswith(b'\x7e'):
                    fh.write(b'\x7e')
                nframes += 1
            fh.flush()
    os.close(fd)
    sys.stderr.write("diag: captured %d frames, %d bytes\n"
                     % (nframes, os.path.getsize(outp)))


if __name__ == "__main__":
    main()
