#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Capture ADSP F3 debug messages across an SSR (fresh SLIMbus framer bring-up).
# Re-arms DIAG F3 masks continuously so the fresh ADSP starts streaming ASAP.
# Devices are rediscovered by name+parent because /dev/rpmsgN minors change on SSR.
#   diagcap.py <secs> [ssr] [grepfile]
# ssr = trigger remoteproc2 stop/start at t0. grepfile = write raw+parsed to /tmp.
import os, sys, glob, select, time, struct

ADSP_RPROC = "remoteproc2"
RP_STATE = "/sys/class/remoteproc/remoteproc2/state"

def find_devs():
    data = cntl = None
    for n in glob.glob('/sys/class/rpmsg/rpmsg*'):
        try:
            name = open(n + '/name').read().strip()
            real = os.path.realpath(n)
        except OSError:
            continue
        if ADSP_RPROC not in real:
            continue
        dev = '/dev/' + os.path.basename(n)
        if name == "DIAG":
            data = dev
        elif name == "DIAG_CNTL":
            cntl = dev
    return data, cntl

def pkt_feature():
    return struct.pack('<III', 8, 6, 2) + bytes([1, 0])

def pkt_f3():
    return (struct.pack('<II', 11, 15) + bytes([1, 2, 0]) +
            struct.pack('<HHI', 0, 0, 1) + struct.pack('<I', 0xFFFFFFFF))

def arm(cntl):
    try:
        fd = os.open(cntl, os.O_RDWR | os.O_NONBLOCK)
    except OSError:
        return False
    ok = True
    for p in (pkt_feature(), pkt_f3()):
        try:
            os.write(fd, p)
        except OSError:
            ok = False
    os.close(fd)
    return ok

def unescape(raw):
    u = bytearray(); esc = False
    for b in raw:
        if esc:
            u.append(b ^ 0x20); esc = False
        elif b == 0x7d:
            esc = True
        else:
            u.append(b)
    return bytes(u)

def parse_f3(p):
    if len(p) < 20:
        return None
    cmd = p[0]
    if cmd not in (0x79, 0x92):
        return None
    num_args = p[2]
    line = struct.unpack_from('<H', p, 12)[0]
    ssid = struct.unpack_from('<H', p, 14)[0]
    off = 20 + 4 * num_args
    rest = p[off:]
    parts = rest.split(b'\x00')
    fmt = parts[0].decode('ascii', 'replace') if parts and cmd == 0x79 else ('QSR#%08x' % (struct.unpack_from('<I', p, 20)[0] if len(p) >= 24 else 0))
    fname = parts[1].decode('ascii', 'replace') if len(parts) > 1 and cmd == 0x79 else ''
    return (cmd, ssid, line, fmt, fname)

GREP = ['slim', 'sb_', 'lpass', 'framer', 'wcd', 'afe', 'q6', 'clk', 'codec', 'tdm', 'enum', 'laddr', 'satellite', 'reconf', 'capab']

def main():
    secs = float(sys.argv[1])
    do_ssr = 'ssr' in sys.argv[2:]
    rawpath = '/tmp/adsp_f3_raw.bin'
    rawf = open(rawpath, 'wb')

    if do_ssr:
        try:
            with open(RP_STATE, 'w') as f: f.write('stop')
            time.sleep(1.0)
            with open(RP_STATE, 'w') as f: f.write('start')
            print("[ssr] adsp stop+start issued")
        except OSError as e:
            print("[ssr] FAILED:", e)

    end = time.time() + secs
    dfd = None; last_arm = 0.0; buf = bytearray()
    seen = {}; hits = []; total_msgs = 0

    while time.time() < end:
        data, cntl = find_devs()
        if not data or not cntl:
            if dfd is not None:
                os.close(dfd); dfd = None
            time.sleep(0.1); continue
        now = time.time()
        if now - last_arm > 0.25:
            arm(cntl); last_arm = now
        if dfd is None:
            try:
                dfd = os.open(data, os.O_RDWR | os.O_NONBLOCK)
            except OSError:
                time.sleep(0.05); continue
        r, _, _ = select.select([dfd], [], [], 0.2)
        if dfd in r:
            try:
                d = os.read(dfd, 32768)
            except OSError:
                os.close(dfd); dfd = None; continue
            if not d:
                continue
            rawf.write(d); buf += d
            while b'\x7e' in buf:
                idx = buf.index(b'\x7e')
                frame = bytes(buf[:idx]); del buf[:idx + 1]
                if not frame:
                    continue
                payload = unescape(frame)
                if len(payload) <= 2:
                    continue
                m = parse_f3(payload[:-2])
                if not m:
                    continue
                total_msgs += 1
                seen[m[1]] = seen.get(m[1], 0) + 1
                text = (m[3] + ' ' + m[4]).lower()
                if any(t in text for t in GREP):
                    hits.append(m)
    if dfd is not None:
        os.close(dfd)
    rawf.close()

    print("\n==== SUMMARY: %d F3 msgs, %d bytes raw -> %s ====" % (total_msgs, os.path.getsize(rawpath), rawpath))
    print("ss_id histogram (count):")
    for ss in sorted(seen, key=lambda k: -seen[k]):
        print("   ss_id=%-6d %d" % (ss, seen[ss]))
    print("\n==== AUDIO/SLIMBUS-RELATED F3 (%d hits) ====" % len(hits))
    seen_line = set()
    for cmd, ssid, line, fmt, fname in hits:
        key = (ssid, line, fmt[:40])
        if key in seen_line:
            continue
        seen_line.add(key)
        tag = 'EXT' if cmd == 0x79 else 'QSR'
        print("  [%s ss=%d L%d %s] %s" % (tag, ssid, line, fname, fmt))

if __name__ == "__main__":
    main()
