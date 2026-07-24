#!/bin/bash
# build_m2.sh — assemble the M2 framer-trace trampoline, splice it into the stock
# (unsigned) adsp.mbn at f04c36e0, and re-sign with qtestsign (-v3, secure-boot off).
# Run from the scratchpad dir. Produces adsp-m2-signed.mbn ready to deploy.
# One change / run; fully reversible (stock adsp.mbn is never modified in place).
set -euo pipefail
cd "$(dirname "$0")"

STOCK=adsp.mbn                 # stock UNSIGNED ELF32 (9962764 B, md5 3ed6924d)
STUB=m2trace.s
SPLICE_VADDR=0xf04c36e0        # SLIMbus framer-mode-decision fn; ctx in r0 at entry
OUT_UNS=adsp-m2.mbn
OUT_SIG=adsp-m2-signed.mbn

# 1) locate an llvm-mc / llvm-objcopy (try plain then versioned)
MC=""; OC=""
for v in "" -18 -17 -16 -15 -14 -13; do
  command -v "llvm-mc$v"      >/dev/null 2>&1 && MC="llvm-mc$v"
  command -v "llvm-objcopy$v" >/dev/null 2>&1 && OC="llvm-objcopy$v"
  [ -n "$MC" ] && [ -n "$OC" ] && break
done
[ -n "$MC" ] || { echo "ERROR: no llvm-mc found (need LLVM with the Hexagon target)"; exit 1; }
[ -n "$OC" ] || { echo "ERROR: no llvm-objcopy found"; exit 1; }
echo "using: $MC / $OC"

# 2) assemble the stub -> raw .text bytes
"$MC" --arch=hexagon --mcpu=hexagonv60 --filetype=obj "$STUB" -o m2trace.o
"$OC" -O binary --only-section=.text m2trace.o m2trace.bin
echo "stub assembled: $(wc -c < m2trace.bin) bytes"

# 3) splice into a fresh copy of the stock image at v2o(SPLICE_VADDR)
python3 - "$STOCK" m2trace.bin "$OUT_UNS" "$SPLICE_VADDR" <<'PY'
import struct, sys, shutil
stock, stub, out, vaddr = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4], 0)
d = open(stock, "rb").read()
assert d[:4] == b"\x7fELF", "stock is not ELF32"
phoff = struct.unpack_from("<I", d, 0x1c)[0]
phes  = struct.unpack_from("<H", d, 0x2a)[0]
phn   = struct.unpack_from("<H", d, 0x2c)[0]
def v2o(va):
    for i in range(phn):
        t,o,v,pa,fs,ms,fl,al = struct.unpack_from("<8I", d, phoff+i*phes)
        if t==1 and fs>0 and v <= va < v+fs:
            return o + (va - v)
    raise SystemExit("vaddr 0x%x not in a file-backed PT_LOAD" % va)
off = v2o(vaddr)
code = open(stub, "rb").read()
shutil.copyfile(stock, out)
buf = bytearray(open(out, "rb").read())
orig = bytes(buf[off:off+len(code)])
buf[off:off+len(code)] = code
open(out, "wb").write(buf)
print("spliced %d bytes at fileoff 0x%x (vaddr 0x%x)" % (len(code), off, vaddr))
print("  orig[:16] =", orig[:16].hex())
print("  new [:16] =", bytes(code[:16]).hex())
PY

# 4) re-sign (v3, adsp SW_ID=0x04) — secure boot is OFF so a dummy chain loads
python3 qtestsign/qtestsign.py adsp "$OUT_UNS" -v 3 -o "$OUT_SIG"
echo "signed image: $OUT_SIG ($(wc -c < "$OUT_SIG") bytes)  [stock signed = 10999580]"
echo "DONE. Next: deploy_m2.sh"
