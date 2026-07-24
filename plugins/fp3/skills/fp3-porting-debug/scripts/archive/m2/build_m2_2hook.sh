#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# build_m2_2hook.sh — build the NON-CRASHING two-hook trace image:
#   EARLY  (pure stash, no emit): cave m2_stash_cave.s  @ 0xf064e098
#          site  m2_stash_site.s  @ 0xf04d1664 (toggle-detection RETURN)
#   LATE   (safe-context emit):   cave m2_emit_late_cave.s @ 0xf064e200
#          site  m2_late_site.s   @ 0xf01d7f08 (diag-control-dispatcher ENTRY)
# then re-sign with qtestsign (-v3). Four in-place splices; stock never modified in
# place. Safety asserts: both caves' target bytes are ZERO; both sites' target bytes
# equal the expected original packets.
set -euo pipefail
cd "$(dirname "$0")"
STOCK=adsp.mbn
ECAVE_S=m2_stash_cave.s      ; ECAVE_VA=0xf064e098
LCAVE_S=m2_emit_late_cave.s  ; LCAVE_VA=0xf064e200
ESITE_S=m2_stash_site.s      ; ESITE_VA=0xf04d1664 ; ESITE_ORIG="48 52 fb 0f 00 c0 09 17"
LSITE_S=m2_late_site.s       ; LSITE_VA=0xf01d7f08 ; LSITE_ORIG="36 54 c8 5b 06 c0 9d a0"
OUT_UNS=adsp-m2-2hook.mbn
OUT_SIG=adsp-m2-2hook-signed.mbn

MC=""; OC=""
for v in -21 "" -18 -17 -16 -15 -14 -13; do
  command -v "llvm-mc$v" >/dev/null 2>&1 && MC="llvm-mc$v"
  command -v "llvm-objcopy$v" >/dev/null 2>&1 && OC="llvm-objcopy$v"
  [ -n "$MC" ] && [ -n "$OC" ] && break
done
[ -n "$MC" ] && [ -n "$OC" ] || { echo "ERROR: need llvm-mc + llvm-objcopy"; exit 1; }

asm() { "$MC" --arch=hexagon --mcpu=hexagonv60 --filetype=obj "$1" -o "${1%.s}.o"
        "$OC" -O binary --only-section=.text "${1%.s}.o" "$2"; echo "$1 -> $(wc -c <"$2")B"; }
asm "$ECAVE_S" ecave.bin
asm "$LCAVE_S" lcave.bin
asm "$ESITE_S" esite.bin
asm "$LSITE_S" lsite.bin

python3 - "$STOCK" "$OUT_UNS" \
  "$ECAVE_VA" "$LCAVE_VA" "$ESITE_VA" "$ESITE_ORIG" "$LSITE_VA" "$LSITE_ORIG" <<'PY'
import struct, sys
stock, out = sys.argv[1], sys.argv[2]
ecave_va, lcave_va = int(sys.argv[3],0), int(sys.argv[4],0)
esite_va, esite_orig = int(sys.argv[5],0), sys.argv[6]
lsite_va, lsite_orig = int(sys.argv[7],0), sys.argv[8]
d = open(stock,"rb").read(); assert d[:4]==b"\x7fELF"
phoff=struct.unpack_from("<I",d,0x1c)[0]; phes=struct.unpack_from("<H",d,0x2a)[0]; phn=struct.unpack_from("<H",d,0x2c)[0]
def v2o(va):
    for i in range(phn):
        t,o,v,pa,fs,ms,fl,al=struct.unpack_from("<8I",d,phoff+i*phes)
        if t==1 and fs>0 and v<=va<v+fs: return o+(va-v)
    raise SystemExit("vaddr 0x%x not in a file-backed PT_LOAD"%va)
buf=bytearray(d)
def splice_zero(va, blob, tag):
    o=v2o(va); reg=bytes(buf[o:o+len(blob)])
    assert reg==b"\x00"*len(blob), "%s cave NOT zero @0x%x: %s"%(tag,va,reg[:16].hex())
    buf[o:o+len(blob)]=blob; print("%s cave %dB @0x%x [zero OK]"%(tag,len(blob),va))
def splice_orig(va, blob, orig, tag):
    o=v2o(va); exp=bytes(int(x,16) for x in orig.split()); got=bytes(buf[o:o+len(exp)])
    assert got==exp, "%s site orig mismatch @0x%x: got %s exp %s"%(tag,va,got.hex(),exp.hex())
    buf[o:o+len(blob)]=blob; print("%s site %dB @0x%x [orig %s OK]"%(tag,len(blob),va,exp.hex()))
splice_zero(ecave_va, open("ecave.bin","rb").read(), "EARLY")
splice_zero(lcave_va, open("lcave.bin","rb").read(), "LATE ")
splice_orig(esite_va, open("esite.bin","rb").read(), esite_orig, "EARLY")
splice_orig(lsite_va, open("lsite.bin","rb").read(), lsite_orig, "LATE ")
# ensure caves don't overlap
assert lcave_va >= ecave_va + len(open("ecave.bin","rb").read()), "caves overlap!"
open(out,"wb").write(buf); print("wrote", out)
PY

python3 qtestsign/qtestsign.py adsp "$OUT_UNS" -v 3 -o "$OUT_SIG" >/dev/null
echo "signed: $OUT_SIG ($(wc -c <"$OUT_SIG")B)  [stock signed 10999580]"
echo "md5: $(md5sum "$OUT_SIG"|cut -d' ' -f1)"
echo "DONE (host-side). Flash = SEPARATE, recovery=disabled MANDATORY."
