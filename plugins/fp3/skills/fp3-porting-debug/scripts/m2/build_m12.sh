#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# build_m12.sh — M12 slim CBCR enable trace. TWO edits to stock adsp.mbn:
#   (a) cave stub m12trace.s at 0xf064e098 (replicates f04df0ac enable + ring-logs),
#   (b) DATA patch: vtable word @0xf0889538 (the slim clock vtable[0]) f04df0ac -> cave.
# Only clocks using vtable 0xf0889538 hit the cave (other f04df0ac user @0xf08228d0 untouched).
# Re-sign (qtestsign -v3). NON-crashing: cave fully replicates f04df0ac + guarded SMEM writes.
set -euo pipefail
cd "$(dirname "$0")"

STOCK=adsp.mbn
STUB=m12trace.s
CAVE_VADDR=0xf064e098
VTABLE_VADDR=0xf0889538         # slim clock vtable[0], currently = f04df0ac
OLD_FN=0xf04df0ac
OUT_UNS=adsp-m12.mbn
OUT_SIG=adsp-m12-signed.mbn

MC=""; OC=""
for v in "" -22 -21 -18 -17 -16 -15 -14 -13; do
  command -v "llvm-mc$v" >/dev/null 2>&1 && MC="llvm-mc$v"
  command -v "llvm-objcopy$v" >/dev/null 2>&1 && OC="llvm-objcopy$v"
  [ -n "$MC" ] && [ -n "$OC" ] && break
done
[ -n "$MC" ] && [ -n "$OC" ] || { echo "ERROR: need llvm-mc + llvm-objcopy (Hexagon)"; exit 1; }
echo "using: $MC / $OC"

"$MC" --arch=hexagon --mcpu=hexagonv60 --filetype=obj "$STUB" -o m12trace.o
"$OC" -O binary --only-section=.text m12trace.o m12trace.bin
echo "cave stub: $(wc -c < m12trace.bin) bytes"

python3 - "$STOCK" m12trace.bin "$OUT_UNS" "$CAVE_VADDR" "$VTABLE_VADDR" "$OLD_FN" <<'PY'
import struct, sys, shutil
stock, stub, out, cave, vt, oldfn = (sys.argv[1], sys.argv[2], sys.argv[3],
                                     int(sys.argv[4],0), int(sys.argv[5],0), int(sys.argv[6],0))
d=open(stock,"rb").read(); assert d[:4]==b"\x7fELF"
phoff=struct.unpack_from("<I",d,0x1c)[0]; phes=struct.unpack_from("<H",d,0x2a)[0]; phn=struct.unpack_from("<H",d,0x2c)[0]
def v2o(va):
    for i in range(phn):
        t,o,v,pa,fs,ms,fl,al=struct.unpack_from("<8I",d,phoff+i*phes)
        if t==1 and fs>0 and v<=va<v+fs: return o+(va-v)
    raise SystemExit("vaddr 0x%x not file-backed"%va)
shutil.copyfile(stock,out)
buf=bytearray(open(out,"rb").read())
# (a) cave
code=open(stub,"rb").read()
co=v2o(cave)
assert all(b==0 for b in buf[co:co+len(code)]), "cave not empty!"
buf[co:co+len(code)]=code
print("cave  @ file 0x%x : %d bytes"%(co,len(code)))
# (b) vtable data patch: f04df0ac -> cave
vo=v2o(vt); orig=struct.unpack_from("<I",buf,vo)[0]
assert orig==oldfn, "vtable[0] is not 0x%x! got 0x%x"%(oldfn,orig)
struct.pack_into("<I",buf,vo,cave)
print("vtable@ file 0x%x : 0x%08x -> 0x%08x"%(vo,orig,cave))
open(out,"wb").write(buf)
PY

python3 qtestsign/qtestsign.py adsp "$OUT_UNS" -v 3 -o "$OUT_SIG" >/dev/null
echo "signed: $OUT_SIG ($(wc -c < "$OUT_SIG") bytes)  [stock signed = 10999580]"
echo "DONE."
