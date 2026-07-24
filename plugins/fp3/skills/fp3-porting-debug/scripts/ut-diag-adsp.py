#!/usr/bin/env python3
# ut-diag-adsp.py  — on-device (UT) ADSP/LPASS diag F3 capture via /dev/diag
# Pure python, no compilation. Constants verified against downstream source:
#   hadk22/kernel/fairphone/sdm632/drivers/char/diag/
#     include/linux/diagchar.h : DIAG_IOCTL_SWITCH_LOGGING=7, MEMORY_DEVICE_MODE=2,
#                                USER_SPACE_DATA_TYPE=0x20
#     diagchar.h               : DIAG_CON_APSS=1 LPASS=4 ; DIAG_CMD_MSG_CONFIG=0x7D
#     diag_masks.h             : diag_msg_config_rsp_t {u8 cmd,u8 sub,u8 status,u8 pad,u32 rt_mask}
#     diag_masks.c             : SET_ALL_MSG_MASK sub_cmd=5, rt_mask!=0 -> ALL_ENABLED
#     diagchar_hdlc.c          : crc_ccitt reflected(0x8408) seed 0xFFFF, ~crc, low byte first,
#                                escape 0x7E/0x7D ^0x20, terminate 0x7E
#     diag_memorydevice.c      : read = [i32 data_type][i32 num_data]{[i32 len][len bytes]}*
import os, sys, struct, fcntl, time, re, select

DEV = "/dev/diag"
DIAG_IOCTL_SWITCH_LOGGING = 7
MEMORY_DEVICE_MODE = 2
USER_SPACE_DATA_TYPE = 0x20
DIAG_CON_APSS = 0x01
DIAG_CON_LPASS = 0x04
DIAG_CON_UPD_AUDIO = 0x2000   # audio user-PD on LPASS
DIAG_CMD_MSG_CONFIG = 0x7D
OP_SET_ALL_MSG_MASK = 5

# ---- CRC-CCITT reflected (Linux lib/crc-ccitt.c, poly 0x8408) ----
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
        if b == 0x7E or b == 0x7D:
            out.append(0x7D); out.append(b ^ 0x20)
        else:
            out.append(b)
    out.append(0x7E)
    return bytes(out)

def switch_logging(fd, mode, periph_mask):
    # struct diag_logging_mode_param_t __packed (20 bytes):
    #  u32 req_mode, u32 peripheral_mask, u32 pd_mask,
    #  u8 mode_param, u8 diag_id, u8 pd_val, u8 reserved, i32 peripheral
    buf = bytearray(struct.pack("<IIIBBBBi", mode, periph_mask, 0, 0, 0, 0, 0, 0))
    fcntl.ioctl(fd, DIAG_IOCTL_SWITCH_LOGGING, buf, True)

def set_all_f3(fd):
    cmd = bytes([DIAG_CMD_MSG_CONFIG, OP_SET_ALL_MSG_MASK, 0x00, 0x00,
                 0xFF, 0xFF, 0xFF, 0xFF])   # rt_mask=0xFFFFFFFF -> all levels/all SSIDs
    frame = hdlc_encode(cmd)
    os.write(fd, struct.pack("<i", USER_SPACE_DATA_TYPE) + frame)

def hdlc_decode(p):
    # de-stuff a single 0x7E-terminated frame (payload keeps trailing CRC bytes)
    out = bytearray(); esc = False
    for b in p:
        if b == 0x7E: break
        if esc: out.append(b ^ 0x20); esc = False
        elif b == 0x7D: esc = True
        else: out.append(b)
    return bytes(out)

ASCII = re.compile(rb"[ -~]{4,}")
def dump_frame(fh, raw):
    dec = hdlc_decode(raw) if (0x7E in raw) else raw
    strs = [m.group().decode("ascii", "replace") for m in ASCII.finditer(dec)]
    fh.write("FRAME len=%d hex=%s\n" % (len(dec), dec[:24].hex()))
    for s in strs:
        fh.write("  STR: %s\n" % s)
    fh.flush()

def main():
    dur = float(sys.argv[1]) if len(sys.argv) > 1 else 8.0
    outp = sys.argv[2] if len(sys.argv) > 2 else "/tmp/adsp_f3.txt"
    mask = int(sys.argv[3], 0) if len(sys.argv) > 3 \
        else (DIAG_CON_LPASS | DIAG_CON_APSS | DIAG_CON_UPD_AUDIO)
    fd = os.open(DEV, os.O_RDWR)
    switch_logging(fd, MEMORY_DEVICE_MODE, mask)
    time.sleep(0.2)
    set_all_f3(fd)
    sys.stderr.write("diag: F3 mask set (periph=0x%x), capturing %.1fs -> %s\n"
                     % (mask, dur, outp))
    sys.stderr.flush()
    nframes = 0
    t0 = time.time()
    last_arm = t0
    with open(outp, "w") as fh:
        fh.write("# ADSP F3 capture t0=%f dur=%.1f periph=0x%x\n" % (t0, dur, mask))
        while time.time() - t0 < dur:
            if time.time() - last_arm > 1.0:   # re-arm across SLIMbus resume/PD reload
                set_all_f3(fd); last_arm = time.time()
            r, _, _ = select.select([fd], [], [], 0.5)
            if not r:
                continue
            data = os.read(fd, 1 << 16)
            if len(data) < 8:
                continue
            dtype, ndata = struct.unpack_from("<ii", data, 0)
            off = 8
            for _ in range(ndata):
                if off + 4 > len(data): break
                (ln,) = struct.unpack_from("<i", data, off); off += 4
                if ln <= 0 or off + ln > len(data): break
                dump_frame(fh, data[off:off+ln]); off += ln; nframes += 1
        fh.write("# done frames=%d\n" % nframes)
    os.close(fd)
    sys.stderr.write("diag: captured %d frames\n" % nframes)

if __name__ == "__main__":
    main()
