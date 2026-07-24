#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# build_m2_gear.sh — PURE-STASH boot-trace image, cave@f064e098 + site@f04bfaa0.
set -euo pipefail
cd "$(dirname "$0")"
STOCK=adsp.mbn
CAVE_S=m2_sat_cave.s ; CAVE_VA=0xf064e098 ; CAVE_VA=0xf064e098
SITE_S=m2_sat_site.s ; SITE_VA=0xf04bfb68
SITE_ORIG="23 40 00 78 10 40 60 70 20 1c f4 eb"
OUT_UNS=adsp-m2sat.mbn
OUT_SIG=adsp-m2sat-signed.mbn
MC=""; OC=""
for v in -21 "" -18 -17 -16 -15 -14 -13; do
  command -v "llvm-mc$v"      >/dev/null 2>&1 && MC="llvm-mc$v"
  command -v "llvm-objcopy$v" >/dev/null 2>&1 && OC="llvm-objcopy$v"
  [ -n "$MC" ] && [ -n "$OC" ] && break
done
[ -n "$MC" ] && [ -n "$OC" ] || { echo "ERROR: need llvm-mc + llvm-objcopy"; exit 1; }
echo "using: $MC / $OC"
asm() {
  "$MC" --arch=hexagon --mcpu=hexagonv60 --filetype=obj "$1" -o "${1%.s}.o"
  if "$OC" --dump-section .rela.text=/dev/stdout "${1%.s}.o" 2>/dev/null | grep -q .; then
    echo "ERROR: unresolved relocations in $1"; exit 1; fi
  "$OC" -O binary --only-section=.text "${1%.s}.o" "$2"
}
asm "$CAVE_S" gcave.bin ; echo "cave: $(wc -c < gcave.bin) bytes"
asm "$SITE_S" gsite.bin ; echo "site: $(wc -c < gsite.bin) bytes"
python3 - "$STOCK" "$OUT_UNS" "$CAVE_VA" "$SITE_VA" "$SITE_ORIG" <<'PY'
import struct, sys
stock,out,cave_va,site_va,site_orig=sys.argv[1],sys.argv[2],int(sys.argv[3],0),int(sys.argv[4],0),sys.argv[5]
d=open(stock,"rb").read(); assert d[:4]==b"\x7fELF"
phoff=struct.unpack_from("<I",d,0x1c)[0]; phes=struct.unpack_from("<H",d,0x2a)[0]; phn=struct.unpack_from("<H",d,0x2c)[0]
def v2o(va):
    for i in range(phn):
        t,o,v,pa,fs,ms,fl,al=struct.unpack_from("<8I",d,phoff+i*phes)
        if t==1 and fs>0 and v<=va<v+fs: return o+(va-v)
    raise SystemExit("vaddr not in file-backed PT_LOAD")
cave=open("gcave.bin","rb").read(); site=open("gsite.bin","rb").read()
buf=bytearray(d)
co=v2o(cave_va); region=bytes(buf[co:co+len(cave)])
assert region==b"\x00"*len(cave), "cave target NOT zero: %s"%region[:16].hex()
buf[co:co+len(cave)]=cave
so=v2o(site_va); exp=bytes(int(x,16) for x in site_orig.split()); got=bytes(buf[so:so+len(exp)])
assert got==exp, "site orig mismatch: got %s exp %s"%(got.hex(),exp.hex())
buf[so:so+len(site)]=site
open(out,"wb").write(buf)
print("cave %d B @off 0x%x (VA 0x%x) [zero OK]; site %d B @off 0x%x [orig %s OK]"%(len(cave),co,cave_va,len(site),so,exp.hex()))
PY
python3 qtestsign/qtestsign.py adsp "$OUT_UNS" -v 3 -o "$OUT_SIG"
echo "signed: $OUT_SIG ($(wc -c < "$OUT_SIG") bytes) [stock signed=10999580]"
echo "md5 signed: $(md5sum "$OUT_SIG"|cut -d' ' -f1)"
