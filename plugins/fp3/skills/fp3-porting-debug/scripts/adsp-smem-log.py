#!/usr/bin/env python3
# adsp-smem-log.py — read Qualcomm SMEM_LOG ring from the AP on mainline pmOS.
#
# SMEM_LOG is a shared-memory event ring (QMI/SMD/messaging trace between APPS and
# the subsystems incl. ADSP). It lives in the *safe* legacy-SMEM region at PA
# 0x86300000 — AP-readable via python mmap(PROT_READ), NO carveout, NO wedge risk.
# This is the zero-injection diag channel on mainline (there is no /dev/diag).
#
# Run ON THE DEVICE as root:  sudo python3 /tmp/adsp-smem-log.py [dump N | watch | grep TOKEN]
#   dump [N]   decode the last N event-records (default 60)
#   watch      poll the write index and print new records live (Ctrl-C to stop)
#   grep TOK   dump, keep only records whose ASCII contains TOK (e.g. slim, qmi, APPS)
#
# Event format (legacy MSM smem_log): item79 = 2000 x 20-byte entries
#   struct { u32 identifier; u32 timetick; u32 data1,data2,data3; }
# identifier bit28 (0x10000000) = CONTINUE: a full log record is a base entry
# (bit28=0) immediately followed by a continue entry (bit28=1) sharing the tick,
# giving 6 data words. item78 = write index (entry number, wraps mod 2000).
import mmap, struct, sys, time

BASE = 0x86300000
MAPSZ = 0x200000
CONT = 0x10000000

def openmem():
    f = open("/dev/mem", "rb")
    return mmap.mmap(f.fileno(), MAPSZ, mmap.MAP_SHARED, mmap.PROT_READ, offset=BASE)

def toc(m, i):
    return struct.unpack_from("<IIII", m, 0xD0 + i*16)  # alloc, off, size, aux

def find_ring(m):
    # events ring = the allocated 40000-byte item (2000*20); write-index = the
    # 8-byte item immediately before it (id 78/79 on this build, but detect by size
    # so it survives an SMEM layout change).
    ev = idx = None
    for i in range(256):
        a, o, s, _ = toc(m, i)
        if a and s == 40000:
            ev = (i, o, s)
    if ev:
        a, o, s, _ = toc(m, ev[0]-1)
        if a and s == 8:
            idx = (ev[0]-1, o, s)
    return ev, idx

def ascii_words(words):
    out = []
    for w in words:
        b = struct.pack("<I", w)
        s = "".join(chr(c) if 32 <= c < 127 else "." for c in b)
        out.append(s)
    return "".join(out)

def read_records(m, ev_off, N, idxoff, count):
    wr = struct.unpack_from("<I", m, idxoff)[0]
    we = wr % N
    recs = []
    e = (we - 1) % N
    seen = 0
    while seen < count*2 and len(recs) < count:
        ident, tick, d1, d2, d3 = struct.unpack_from("<IIIII", m, ev_off + e*20)
        seen += 1
        if ident == 0 and tick == 0:
            e = (e - 1) % N; continue
        # a base entry (bit28=0); try to attach the continue at e+1
        if not (ident & CONT):
            ci, ct, c1, c2, c3 = struct.unpack_from("<IIIII", m, ev_off + ((e+1) % N)*20)
            words = [d1, d2, d3] + ([c1, c2, c3] if (ci & CONT) and ct == tick else [])
            recs.append((e, ident, tick, words))
        e = (e - 1) % N
    return wr, we, recs

def fmt(rec):
    e, ident, tick, words = rec
    asc = ascii_words(words)
    hexw = " ".join("%08x" % w for w in words)
    return "e%-4d id=%08x t=%08x | %s | %r" % (e, ident, tick, hexw, asc)

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "dump"
    m = openmem()
    ev, idx = find_ring(m)
    if not ev or not idx:
        print("SMEM_LOG ring not found (ev=%r idx=%r)" % (ev, idx)); return
    _, ev_off, ev_sz = ev
    _, idxoff, _ = idx
    N = ev_sz // 20
    if mode == "watch":
        last = struct.unpack_from("<I", m, idxoff)[0] % N
        print("watching SMEM_LOG (ring id=%d, %d entries) — Ctrl-C to stop" % (ev[0], N))
        try:
            while True:
                wr = struct.unpack_from("<I", m, idxoff)[0] % N
                e = last
                while e != wr:
                    ident, tick, d1, d2, d3 = struct.unpack_from("<IIIII", m, ev_off + e*20)
                    if not (ident & CONT) and not (ident == 0 and tick == 0):
                        ci, ct, c1, c2, c3 = struct.unpack_from("<IIIII", m, ev_off + ((e+1) % N)*20)
                        words = [d1, d2, d3] + ([c1, c2, c3] if (ci & CONT) and ct == tick else [])
                        print(fmt((e, ident, tick, words)))
                    e = (e + 1) % N
                last = wr
                time.sleep(0.25)
        except KeyboardInterrupt:
            print()
        return
    count = 60
    token = None
    if mode == "grep" and len(sys.argv) > 2:
        token = sys.argv[2]; count = 400
    elif mode == "dump" and len(sys.argv) > 2:
        count = int(sys.argv[2])
    wr, we, recs = read_records(m, ev_off, N, idxoff, count)
    print("SMEM_LOG ring id=%d off=0x%x entries=%d  write-ptr=%d (entry %d)" % (ev[0], ev_off, N, wr, we))
    for rec in recs:
        line = fmt(rec)
        if token is None or token.lower() in line.lower():
            print(line)

if __name__ == "__main__":
    main()
