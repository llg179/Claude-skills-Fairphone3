#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# UT (downstream 4.9 diagchar) ADSP F3 capture via /dev/diag.
# Unlike mainline rpmsg, UT uses the classic Qualcomm diagchar node:
#   1. ioctl DIAG_IOCTL_SWITCH_LOGGING(7) -> MEMORY_DEVICE_MODE(2), all peripherals
#   2. write [USER_SPACE_DATA_TYPE=0x20][HDLC(7D 05 00 00 FF FF FF FF)] = set-all-F3
#   3. read(): [data_type:4][md payload w/ 0x7e-HDLC F3 frames] -> dump raw
# Raw is 0x7e-framed like mainline, so f3_dump.py parses it unchanged.
#   ut_diag_f3.py <secs> <outfile>
import os, sys, struct, select, time, fcntl

DIAG = "/dev/diag"
DIAG_IOCTL_SWITCH_LOGGING = 7
MEMORY_DEVICE_MODE = 2
USER_SPACE_DATA_TYPE = 0x20

def crc_ccitt(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8408 if (crc & 1) else (crc >> 1)
    return (~crc) & 0xFFFF

def hdlc(payload):
    fcs = crc_ccitt(payload)
    body = payload + bytes([fcs & 0xFF, (fcs >> 8) & 0xFF])
    out = bytearray()
    for b in body:
        if b == 0x7E: out += b'\x7d\x5e'
        elif b == 0x7D: out += b'\x7d\x5d'
        else: out.append(b)
    out.append(0x7E)
    return bytes(out)

def main():
    secs = float(sys.argv[1]); outp = sys.argv[2]
    fd = os.open(DIAG, os.O_RDWR)
    # diag_logging_mode_param_t: req_mode,peripheral_mask,pd_mask (u32x3),
    #   mode_param,diag_id,pd_val,reserved (u8x4), peripheral (i32) = 20 bytes
    mode = struct.pack('<IIIBBBBi', MEMORY_DEVICE_MODE, 0x7F, 0, 0, 0, 0, 0, 0)
    try:
        r = fcntl.ioctl(fd, DIAG_IOCTL_SWITCH_LOGGING, mode)
        print("[switch_logging] ret ok")
    except OSError as e:
        print("[switch_logging] FAILED:", e)
    # enable all F3 (msg) masks: cmd 0x7D, sub 0x05 SET_ALL, rt_mask=0xFFFFFFFF
    cmd = bytes([0x7D, 0x05, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0xFF])
    pkt = struct.pack('<I', USER_SPACE_DATA_TYPE) + hdlc(cmd)
    try:
        n = os.write(fd, pkt); print("[set-all-F3] wrote", n, "bytes")
    except OSError as e:
        print("[set-all-F3] write FAILED:", e)
    # also enable all LOG masks isn't needed; capture F3
    raw = open(outp, 'wb'); total = 0; frames = 0
    end = time.time() + secs
    while time.time() < end:
        r, _, _ = select.select([fd], [], [], 0.3)
        if fd in r:
            try:
                d = os.read(fd, 65536)
            except OSError as e:
                print("read err", e); continue
            if d:
                raw.write(d); total += len(d)
                frames += d.count(b'\x7e')
    raw.close()
    print("[done] %d bytes, ~%d hdlc frames -> %s" % (total, frames, outp))
    # restore sane logging mode (USB_MODE=1) so we don't leave diag hijacked
    try:
        fcntl.ioctl(fd, DIAG_IOCTL_SWITCH_LOGGING,
                    struct.pack('<IIIBBBBi', 1, 0x7F, 0, 0, 0, 0, 0, 0))
    except OSError:
        pass
    os.close(fd)

if __name__ == "__main__":
    main()
