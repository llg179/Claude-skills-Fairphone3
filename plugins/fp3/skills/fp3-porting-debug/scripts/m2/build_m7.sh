#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# build_m7.sh — M7 post-DAL-enable rc capture. Splices TWO pieces into stock adsp.mbn:
#   (a) a 4-byte relative `jump 0xf064e098` OVER the single-word packet
#       `{ jump 0xf04bfb5c }` at 0xf04bfb00 (right after the DAL enable call),
#   (b) the m7trace.s cave stub at 0xf064e098 (rc capture + counters).
# Re-sign (qtestsign -v3). Produces adsp-m7-signed.mbn. NON-crashing; the cave
# reads only post-gate offsets the stock code already dereferenced -> COLD-BOOT SAFE.
set -euo pipefail
cd "$(dirname "$0")"

STOCK=adsp.mbn
STUB=m7trace.s
CAVE_VADDR=0xf064e098
INJECT_VADDR=0xf04bfb00        # single-word packet { jump 0xf04bfb5c } = 2ec00058
OUT_UNS=adsp-m7.mbn
OUT_SIG=adsp-m7-signed.mbn

MC=""; OC=""
for v in "" -22 -21 -18 -17 -16 -15 -14 -13; do
  command -v "llvm-mc$v" >/dev/null 2>&1 && MC="llvm-mc$v"
  command -v "llvm-objcopy$v" >/dev/null 2>&1 && OC="llvm-objcopy$v"
  [ -n "$MC" ] && [ -n "$OC" ] && break
done
[ -n "$MC" ] && [ -n "$OC" ] || { echo "ERROR: need llvm-mc + llvm-objcopy (Hexagon)"; exit 1; }
echo "using: $MC / $OC"

# 2a) assemble the cave stub
"$MC" --arch=hexagon --mcpu=hexagonv60 --filetype=obj "$STUB" -o m7trace.o
"$OC" -O binary --only-section=.text m7trace.o m7trace.bin
echo "cave stub: $(wc -c < m7trace.bin) bytes"

# sanity: the final trailer jump target 0xf04bfb5c must be assembled somewhere
python3 - <<'PY'
b=open("m7trace.bin","rb").read()
# 0xf04bfb5c appears as a ## immediate (little-endian embedded); just assert nonzero size
assert len(b) >= 64 and len(b) % 4 == 0, "stub size looks wrong: %d"%len(b)
print("stub sanity OK: %d bytes"%len(b))
PY

# 3) splice cave + compute+verify a 4-byte relative jump at the inject site
python3 - "$STOCK" m7trace.bin "$OUT_UNS" "$INJECT_VADDR" "$CAVE_VADDR" <<'PY'
import struct, sys, shutil
stock, stub, out, inj, cave = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4],0), int(sys.argv[5],0)
d=open(stock,"rb").read(); assert d[:4]==b"\x7fELF"
phoff=struct.unpack_from("<I",d,0x1c)[0]; phes=struct.unpack_from("<H",d,0x2a)[0]; phn=struct.unpack_from("<H",d,0x2c)[0]
def v2o(va):
    for i in range(phn):
        t,o,v,pa,fs,ms,fl,al=struct.unpack_from("<8I",d,phoff+i*phes)
        if t==1 and fs>0 and v<=va<v+fs: return o+(va-v)
    raise SystemExit("vaddr 0x%x not file-backed"%va)
# J2_jump 4-byte PC-relative; base opcode 0x5800C000 (parse=11), imm=offset>>2
BASE=0x5800C000; off=cave-inj; assert off%4==0
imm=off>>2; assert -(1<<21)<=imm<(1<<21), "jump out of +-2MB"
imm&=0x3FFFFF
word=BASE | ((imm>>13 & 0x1FF)<<16) | ((imm & 0x1FFF)<<1)
hi=(word>>16)&0x1FF; lo=(word>>1)&0x1FFF; dimm=(hi<<13)|lo
if dimm&(1<<21): dimm-=(1<<22)
assert inj+(dimm<<2)==cave, "encode mismatch"
jb=struct.pack("<I",word)
print("jump word=0x%08x bytes=%s -> 0x%x (verified)"%(word,jb.hex(),cave))
shutil.copyfile(stock,out)
buf=bytearray(open(out,"rb").read())
code=open(stub,"rb").read()
co=v2o(cave)
assert all(b==0 for b in buf[co:co+len(code)]), "cave not empty!"
buf[co:co+len(code)]=code
io=v2o(inj); orig=bytes(buf[io:io+4])
assert orig==bytes.fromhex("2ec00058"), "inject site is not the { jump 0xf04bfb5c } word! got %s"%orig.hex()
buf[io:io+4]=jb
open(out,"wb").write(buf)
print("cave  @ file 0x%x : %d bytes"%(co,len(code)))
print("inject@ file 0x%x : %s -> %s (replaces { jump 0xf04bfb5c })"%(io, orig.hex(), jb.hex()))
PY

# 4) re-sign
python3 qtestsign/qtestsign.py adsp "$OUT_UNS" -v 3 -o "$OUT_SIG" >/dev/null
echo "signed: $OUT_SIG ($(wc -c < "$OUT_SIG") bytes)  [stock signed = 10999580]"
echo "DONE."
