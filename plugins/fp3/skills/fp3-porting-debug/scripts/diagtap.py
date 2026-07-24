#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Minimal DIAG-over-rpmsg tap for mainline pmOS (msm8953).
# The ADSP/modem DIAG SMD channels are exposed as /dev/rpmsgN char devices.
# This speaks classic DIAG HDLC framing to prove the channel and (later) enable F3.
#
#   diagtap.py listen <dev> <secs>          passive hexdump of incoming SMD packets
#   diagtap.py send   <dev> <hexbytes> <s>  HDLC-frame payload, write, read replies for <s>s
#   diagtap.py ver    <dev> <secs>          send DIAG version req (0x00) + read
#   diagtap.py raw    <dev> <hexbytes> <s>  write raw (already-framed) bytes, read replies
import os, sys, select, time, binascii

def crc_ccitt(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8408 if (crc & 1) else (crc >> 1)
    return (~crc) & 0xFFFF

def hdlc_encode(payload: bytes) -> bytes:
    fcs = crc_ccitt(payload)
    body = payload + bytes([fcs & 0xFF, (fcs >> 8) & 0xFF])
    out = bytearray()
    for b in body:
        if b == 0x7E: out += b'\x7d\x5e'
        elif b == 0x7D: out += b'\x7d\x5d'
        else: out.append(b)
    out.append(0x7E)
    return bytes(out)

def hexdump(tag, data):
    print(f"[{tag}] {len(data)} bytes:")
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        hexs = ' '.join(f'{c:02x}' for c in chunk)
        asci = ''.join(chr(c) if 32 <= c < 127 else '.' for c in chunk)
        print(f"  {i:04x}  {hexs:<47}  {asci}")

def open_dev(dev):
    return os.open(dev, os.O_RDWR | os.O_NONBLOCK)

def drain(fd, secs, tag="rx"):
    end = time.time() + secs
    got = 0
    while time.time() < end:
        r, _, _ = select.select([fd], [], [], max(0, end - time.time()))
        if fd in r:
            try:
                data = os.read(fd, 4096)
            except BlockingIOError:
                continue
            except OSError as e:
                print(f"  read err: {e}"); break
            if data:
                got += len(data)
                hexdump(tag, data)
            else:
                time.sleep(0.02)
    if got == 0:
        print(f"  ({tag}: nothing in {secs}s)")
    return got

# ---- DIAG control-channel packets (RAW, not HDLC) ----
def pkt_feature_mask():
    # struct diag_ctrl_feature_mask: id=8, data_len=6, feature_mask_len=2, bytes[2]
    # feature byte0 bit0 = F_DIAG_FEATURE_MASK_SUPPORT (minimal)
    import struct
    return struct.pack('<III', 8, 6, 2) + bytes([0x01, 0x00])

def pkt_f3_mask_all_enabled():
    # struct diag_ctrl_msg_mask: cmd_type=11(F3_MASK), data_len=11+4,
    # stream_id=1, status=2(ALL_ENABLED), msg_mode=0, ssid_first=0, ssid_last=0,
    # msg_mask_size=1, mask=0xffffffff
    import struct
    return (struct.pack('<II', 11, 15) +
            bytes([1, 2, 0]) +
            struct.pack('<HHI', 0, 0, 1) +
            struct.pack('<I', 0xFFFFFFFF))

def ascii_runs(data, minlen=4):
    out, cur = [], bytearray()
    for c in data:
        if 32 <= c < 127:
            cur.append(c)
        else:
            if len(cur) >= minlen: out.append(cur.decode('ascii', 'replace'))
            cur = bytearray()
    if len(cur) >= minlen: out.append(cur.decode('ascii', 'replace'))
    return out

def main():
    cmd = sys.argv[1]
    if cmd == "f3":
        # f3 <cntl_dev> <data_dev> <secs>  — enable all F3, capture ADSP debug msgs
        cntl, data, secs = sys.argv[2], sys.argv[3], float(sys.argv[4])
        cfd = open_dev(cntl)
        for name, p in (("feature", pkt_feature_mask()), ("f3_all", pkt_f3_mask_all_enabled())):
            hexdump("tx-cntl-"+name, p)
            try: os.write(cfd, p); print(f"  wrote {name} ({len(p)}B) to {cntl}")
            except OSError as e: print(f"  {name} WRITE FAILED: {e}")
        # brief cntl ack read
        drain(cfd, 0.5, "cntl-ack")
        dfd = open_dev(data)
        print(f"--- capturing F3 on {data} for {secs}s ---")
        end = time.time() + secs; total = bytearray()
        while time.time() < end:
            r, _, _ = select.select([dfd], [], [], max(0, end - time.time()))
            if dfd in r:
                try: d = os.read(dfd, 8192)
                except (BlockingIOError, OSError): continue
                if d: total += d
        os.close(dfd); os.close(cfd)
        if total:
            hexdump("F3-raw", total[:512])
            print(f"--- ASCII strings in {len(total)}B of F3 ---")
            for s in ascii_runs(total): print("   ", s)
        else:
            print(f"  (no F3 in {secs}s)")
        return
    dev = sys.argv[2]
    if cmd == "listen":
        secs = float(sys.argv[3])
        fd = open_dev(dev)
        print(f"listening {dev} for {secs}s ...")
        drain(fd, secs, "cntl/data")
        os.close(fd)
    elif cmd in ("send", "ver", "raw"):
        if cmd == "ver":
            payload = b'\x00'; secs = float(sys.argv[3]); frame = hdlc_encode(payload)
        elif cmd == "send":
            payload = binascii.unhexlify(sys.argv[3]); secs = float(sys.argv[4]); frame = hdlc_encode(payload)
        else:  # raw
            frame = binascii.unhexlify(sys.argv[3]); secs = float(sys.argv[4])
        fd = open_dev(dev)
        hexdump("tx", frame)
        try:
            n = os.write(fd, frame)
            print(f"  wrote {n} bytes to {dev}")
        except OSError as e:
            print(f"  WRITE FAILED: {e}"); os.close(fd); return
        drain(fd, secs, "reply")
        os.close(fd)
    else:
        print(__doc__)

if __name__ == "__main__":
    main()
