#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# build_m2rc.sh — DAL-op RC boot-trace (folyt.29). Applies to a FRESH stock:
#   (1) force-patch  @f04bfab4  word0 74816011 -> 7e806151  (gear r17=0xA, folyt.28-verified)
#   (2) rc-cave site @f04bfaf4  (12B call packet -> jump cave)
#   (3) cave         @f064e098  (m2rcs_cave.s)
# then re-sign (qtestsign -v3). Each patch verifies the stock bytes first.
set -euo pipefail
cd "$(dirname "$0")"
STOCK=adsp.mbn
CAVE_S=m2rcs_cave.s ; CAVE_VA=0xf064e098
SITE_S=m2rc_site.s ; SITE_VA=0xf04bfaf4
SITE_ORIG="20 7b 9b 5b c1 40 00 78 c0 f0 90 93"
FORCE_VA=0xf04bfab4 ; FORCE_ORIG="11 60 81 74" ; FORCE_NEW="7e 80 61 51"
OUT_UNS=adsp-m2rcs.mbn ; OUT_SIG=adsp-m2rcs-signed.mbn
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
asm "$CAVE_S" rcscave.bin ; echo "cave: $(wc -c < rcscave.bin) bytes"
asm "$SITE_S" rcsite.bin ; echo "site: $(wc -c < rcsite.bin) bytes"
python3 - "$STOCK" "$OUT_UNS" "$CAVE_VA" "$SITE_VA" "$SITE_ORIG" "$FORCE_VA" "$FORCE_ORIG" "$FORCE_NEW" <<'PY'
import struct, sys
stock,out,cave_va,site_va,site_orig,force_va,force_orig,force_new=(
    sys.argv[1],sys.argv[2],int(sys.argv[3],0),int(sys.argv[4],0),sys.argv[5],
    int(sys.argv[6],0),sys.argv[7],sys.argv[8])
d=open(stock,"rb").read(); assert d[:4]==b"\x7fELF"
phoff=struct.unpack_from("<I",d,0x1c)[0]; phes=struct.unpack_from("<H",d,0x2a)[0]; phn=struct.unpack_from("<H",d,0x2c)[0]
def v2o(va):
    for i in range(phn):
        t,o,v,pa,fs,ms,fl,al=struct.unpack_from("<8I",d,phoff+i*phes)
        if t==1 and fs>0 and v<=va<v+fs: return o+(va-v)
    raise SystemExit("vaddr not in file-backed PT_LOAD")
buf=bytearray(d)
# (1) force
fo=v2o(force_va); exp=bytes(int(x,16) for x in force_orig.split()); new=bytes(int(x,16) for x in force_new.split())
got=bytes(buf[fo:fo+len(exp)]); assert got==exp,"force orig mismatch: got %s exp %s"%(got.hex(),exp.hex())
buf[fo:fo+len(new)]=new
print("force %d B @off 0x%x [orig %s -> %s OK]"%(len(new),fo,exp.hex(),new.hex()))
# (2) cave
cave=open("rcscave.bin","rb").read(); co=v2o(cave_va); region=bytes(buf[co:co+len(cave)])
assert region==b"\x00"*len(cave),"cave target NOT zero: %s"%region[:16].hex()
buf[co:co+len(cave)]=cave
print("cave %d B @off 0x%x (VA 0x%x) [zero OK]"%(len(cave),co,cave_va))
# (3) site
site=open("rcsite.bin","rb").read(); so=v2o(site_va); exp2=bytes(int(x,16) for x in site_orig.split()); got2=bytes(buf[so:so+len(exp2)])
assert got2==exp2,"site orig mismatch: got %s exp %s"%(got2.hex(),exp2.hex())
assert len(site)==len(exp2),"site len %d != orig %d"%(len(site),len(exp2))
buf[so:so+len(site)]=site
print("site %d B @off 0x%x [orig %s OK]"%(len(site),so,exp2.hex()))
open(out,"wb").write(buf)
PY
python3 qtestsign/qtestsign.py adsp "$OUT_UNS" -v 3 -o "$OUT_SIG"
echo "signed: $OUT_SIG ($(wc -c < "$OUT_SIG") bytes) [stock signed=10999580]"
echo "md5 signed: $(md5sum "$OUT_SIG"|cut -d' ' -f1)"
