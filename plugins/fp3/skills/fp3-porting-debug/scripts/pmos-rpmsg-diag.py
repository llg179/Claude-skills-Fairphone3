#!/usr/bin/env python3
# pmos-rpmsg-diag.py — read the ADSP's DIAG stream on pmOS via rpmsg_char, and
# (optionally) push the F3 message mask on the DIAG_CNTL channel so the ADSP
# actually emits its debug log during framer bring-up.
#
# Node specs: "data:/dev/rpmsgX"  (read F3, HDLC-decode)
#             "cntl:/dev/rpmsgY"  (write F3-enable ctrl mask on start, also read)
# Plain "/dev/rpmsgX" == data.
#
# F3 ctrl mask (diag_ctrl_msg_mask, diagfwd_cntl.h / diag_masks.c, raw on CNTL):
#   u32 cmd_type=11 (DIAG_CTRL_MSG_F3_MASK)
#   u32 data_len = MSG_MASK_CTRL_HEADER_LEN(11) + 4
#   u8  stream_id=1, u8 status=2 (ALL_ENABLED), u8 msg_mode=0
#   u16 ssid_first=0, u16 ssid_last=0, u32 msg_mask_size=1, u32 mask=0xFFFFFFFF
import os, sys, time, re, select, struct

def f3_ctrl_mask():
    return struct.pack("<IIBBBHHII",
                       11,          # cmd_type = DIAG_CTRL_MSG_F3_MASK
                       11 + 4,      # data_len
                       1,           # stream_id
                       2,           # status = DIAG_CTRL_MASK_ALL_ENABLED
                       0,           # msg_mode
                       0,           # ssid_first
                       0,           # ssid_last
                       1,           # msg_mask_size (uint32 count)
                       0xFFFFFFFF)  # mask

CTRL = 0x7E; ESC = 0x7D
def hdlc_split(buf, carry):
    data = carry + buf; frames = []
    while True:
        i = data.find(bytes([CTRL]))
        if i < 0: break
        raw, data = data[:i], data[i+1:]
        if not raw: continue
        out = bytearray(); esc = False
        for b in raw:
            if esc: out.append(b ^ 0x20); esc = False
            elif b == ESC: esc = True
            else: out.append(b)
        frames.append(bytes(out))
    return frames, data

ASCII = re.compile(rb"[ -~]{4,}")
def dump(fh, tag, frame):
    fh.write("[%s] len=%d hex=%s\n" % (tag, len(frame), frame[:20].hex()))
    for m in ASCII.finditer(frame):
        fh.write("    STR: %s\n" % m.group().decode("ascii","replace"))
    fh.flush()

def main():
    dur = float(sys.argv[1]); outp = sys.argv[2]
    specs = sys.argv[3:]
    fds = {}; carry = {}; kind = {}
    for s in specs:
        k, _, path = s.partition(":")
        if not path: k, path = "data", k
        try:
            fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
        except OSError as e:
            sys.stderr.write("open %s failed: %s\n" % (path, e)); continue
        fds[fd] = os.path.basename(path); carry[fd] = b""; kind[fd] = k
        if k == "cntl":
            try:
                os.write(fd, f3_ctrl_mask())
                sys.stderr.write("wrote F3 ctrl-mask to %s\n" % path)
            except OSError as e:
                sys.stderr.write("cntl write %s failed: %s\n" % (path, e))
    if not fds:
        sys.stderr.write("no devices\n"); return
    sys.stderr.write("reading %s for %.1fs\n" % (list(fds.values()), dur)); sys.stderr.flush()
    t0 = time.time(); n = 0; last_arm = t0
    with open(outp, "w") as fh:
        fh.write("# pmOS rpmsg DIAG capture t0=%f dur=%.1f specs=%s\n" % (t0, dur, specs))
        while time.time() - t0 < dur:
            # re-arm F3 mask on cntl every 1s (survives peripheral state changes)
            if time.time() - last_arm > 1.0:
                for fd in fds:
                    if kind[fd] == "cntl":
                        try: os.write(fd, f3_ctrl_mask())
                        except OSError: pass
                last_arm = time.time()
            r, _, _ = select.select(list(fds), [], [], 0.3)
            for fd in r:
                try: data = os.read(fd, 1 << 16)
                except (BlockingIOError, OSError): continue
                if not data: continue
                frames, carry[fd] = hdlc_split(data, carry[fd])
                tag = ("%s/%s" % (kind[fd], fds[fd]))
                if not frames and 0x7E not in data:
                    dump(fh, tag+":raw", data); n += 1
                for f in frames:
                    dump(fh, tag, f); n += 1
        fh.write("# done frames=%d\n" % n)
    for fd in fds: os.close(fd)
    sys.stderr.write("captured %d frames\n" % n)

if __name__ == "__main__":
    main()
