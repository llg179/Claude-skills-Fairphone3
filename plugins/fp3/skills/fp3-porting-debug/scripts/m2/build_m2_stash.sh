#!/bin/bash
# build_m2_stash.sh — build the PURE-STASH single-hook image for Plan (C)
# (bss-stash + devcoredump-exfil). NO diag emit anywhere => proven run-1 safe
# (folyt.13 point 2: the load/store stash path ran clean, no reboot).
#   (1) assemble the stash cave (m2_stash_cave.s) -> splice at VA 0xf064e098
#       (verified 3952-byte zero region in the R+X segment); the cave does
#       pure loads+stores into bss 0xf0ca0000 (marker 0xC0DE7066 + 11 values),
#       then re-emits the displaced return packet -> ZERO diag call, ZERO frame.
#   (2) assemble the 8-byte site jump (m2_stash_site.s) -> splice at the hook
#       site VA 0xf04d1664 (toggle-detection RETURN packet).
# then re-sign with qtestsign (-v3, FP3 secure-boot OFF).
#
# Exfil is NOT by diag (that wedged in folyt.13) — instead by ADSP coredump:
# 0xf0ca0000 lives in PT_LOAD seg3 (VA 0xf07fc000, memsz 0x4b1000 -> covers
# 0xf0ca0000, flags R+W). qcom PAS coredump dumps p_memsz, so the kernel reads
# the carveout safely (no /dev/mem 900e) and the early-boot stash is inside it.
#
# Safety asserts (abort if violated): cave target ALL ZERO; site target == the
# expected original packet 48 52 fb 0f 00 c0 09 17. Stock never modified in place.
set -euo pipefail
cd "$(dirname "$0")"

STOCK=adsp.mbn
CAVE_S=m2_stash_cave.s ; CAVE_VA=0xf064e098
SITE_S=m2_stash_site.s ; SITE_VA=0xf04d1664
SITE_ORIG="48 52 fb 0f 00 c0 09 17"
OUT_UNS=adsp-m2stash.mbn
OUT_SIG=adsp-m2stash-signed.mbn

MC=""; OC=""
for v in -21 "" -18 -17 -16 -15 -14 -13; do
  command -v "llvm-mc$v"      >/dev/null 2>&1 && MC="llvm-mc$v"
  command -v "llvm-objcopy$v" >/dev/null 2>&1 && OC="llvm-objcopy$v"
  [ -n "$MC" ] && [ -n "$OC" ] && break
done
[ -n "$MC" ] && [ -n "$OC" ] || { echo "ERROR: need llvm-mc + llvm-objcopy (Hexagon)"; exit 1; }
echo "using: $MC / $OC"

asm() { # $1=src $2=out.bin
  "$MC" --arch=hexagon --mcpu=hexagonv60 --filetype=obj "$1" -o "${1%.s}.o"
  if "$OC" --dump-section .rela.text=/dev/stdout "${1%.s}.o" 2>/dev/null | grep -q .; then
    echo "ERROR: unresolved relocations in $1"; exit 1; fi
  "$OC" -O binary --only-section=.text "${1%.s}.o" "$2"
}
asm "$CAVE_S" scave.bin ; echo "cave: $(wc -c < scave.bin) bytes"
asm "$SITE_S" ssite.bin ; echo "site: $(wc -c < ssite.bin) bytes"

python3 - "$STOCK" "$OUT_UNS" "$CAVE_VA" "$SITE_VA" "$SITE_ORIG" <<'PY'
import struct, sys
stock, out, cave_va, site_va, site_orig = sys.argv[1], sys.argv[2], int(sys.argv[3],0), int(sys.argv[4],0), sys.argv[5]
d = open(stock, "rb").read()
assert d[:4] == b"\x7fELF", "stock not ELF32"
phoff = struct.unpack_from("<I", d, 0x1c)[0]
phes  = struct.unpack_from("<H", d, 0x2a)[0]
phn   = struct.unpack_from("<H", d, 0x2c)[0]
def v2o(va):
    for i in range(phn):
        t,o,v,pa,fs,ms,fl,al = struct.unpack_from("<8I", d, phoff+i*phes)
        if t==1 and fs>0 and v <= va < v+fs: return o + (va - v)
    raise SystemExit("vaddr 0x%x not in a file-backed PT_LOAD" % va)
cave = open("scave.bin","rb").read()
site = open("ssite.bin","rb").read()
buf = bytearray(d)
co = v2o(cave_va)
region = bytes(buf[co:co+len(cave)])
assert region == b"\x00"*len(cave), "cave target NOT zero (len %d): %s" % (len(cave), region[:16].hex())
buf[co:co+len(cave)] = cave
so = v2o(site_va)
exp = bytes(int(x,16) for x in site_orig.split())
got = bytes(buf[so:so+len(exp)])
assert got == exp, "site orig mismatch: got %s expected %s" % (got.hex(), exp.hex())
buf[so:so+len(site)] = site
open(out,"wb").write(buf)
print("cave  spliced %d B @ fileoff 0x%x (VA 0x%x)  [was all-zero OK]" % (len(cave), co, cave_va))
print("site  spliced %d B @ fileoff 0x%x (VA 0x%x)  [orig %s OK]" % (len(site), so, site_va, exp.hex()))
PY

python3 qtestsign/qtestsign.py adsp "$OUT_UNS" -v 3 -o "$OUT_SIG"
echo "signed: $OUT_SIG ($(wc -c < "$OUT_SIG") bytes)  [stock signed = 10999580]"
echo "md5 unsigned: $(md5sum "$OUT_UNS" | cut -d' ' -f1)  (stock unsigned md5 3ed6924d)"
echo "DONE (host-side). Flash is a SEPARATE, user-approved step."
