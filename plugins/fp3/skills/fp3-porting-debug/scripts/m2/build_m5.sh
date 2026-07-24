#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# build_m5.sh — M5 clock-work ENTRY exfil. Splices TWO pieces into stock adsp.mbn:
#   (a) a 4-byte relative `jump 0xf064e098` over the FIRST word of the entry-prologue
#       packet at 0xf04bfaa0 (the generic clock enable/disable worker fn),
#   (b) the m5trace.s cave stub at 0xf064e098 (aggregate counters + re-emit prologue).
# Re-sign (qtestsign -v3). Produces adsp-m5-signed.mbn. Deploy NON-crashing:
# one SSR-reload, ADSP boots normally, AP reads SMEM PA 0x86302a70.
set -euo pipefail
cd "$(dirname "$0")"

STOCK=adsp.mbn
STUB=m5trace.s
CAVE_VADDR=0xf064e098
INJECT_VADDR=0xf04bfaa0        # first word of prologue: { r16=r0 ; <duplex alloc> }
OUT_UNS=adsp-m5.mbn
OUT_SIG=adsp-m5-signed.mbn

MC=""; OC=""
for v in "" -22 -21 -18 -17 -16 -15 -14 -13; do
  command -v "llvm-mc$v" >/dev/null 2>&1 && MC="llvm-mc$v"
  command -v "llvm-objcopy$v" >/dev/null 2>&1 && OC="llvm-objcopy$v"
  [ -n "$MC" ] && [ -n "$OC" ] && break
done
[ -n "$MC" ] && [ -n "$OC" ] || { echo "ERROR: need llvm-mc + llvm-objcopy (Hexagon)"; exit 1; }
echo "using: $MC / $OC"

# 2a) assemble the cave stub
"$MC" --arch=hexagon --mcpu=hexagonv60 --filetype=obj "$STUB" -o m5trace.o
"$OC" -O binary --only-section=.text m5trace.o m5trace.bin
echo "cave stub: $(wc -c < m5trace.bin) bytes"

# sanity: the re-emitted prologue (raw .long 0x70604010,0xebf41c10) must be present
python3 - <<'PY'
b=open("m5trace.bin","rb").read()
need=bytes.fromhex("10406070101cf4eb")
assert need in b, "re-emitted prologue bytes NOT found in stub (asm mangled .long?)"
print("prologue re-emit bytes present: OK (offset 0x%x)"%b.find(need))
PY

# 3) splice cave + compute+verify a 4-byte relative jump at the inject site
python3 - "$STOCK" m5trace.bin "$OUT_UNS" "$INJECT_VADDR" "$CAVE_VADDR" <<'PY'
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
assert orig==bytes.fromhex("10406070"), "inject site is not the r16=r0 word! got %s"%orig.hex()
buf[io:io+4]=jb
open(out,"wb").write(buf)
print("cave  @ file 0x%x : %d bytes"%(co,len(code)))
print("inject@ file 0x%x : %s -> %s (only the r16=r0 word; orphan allocframe unreached)"%(io, orig.hex(), jb.hex()))
PY

# 4) re-sign
python3 qtestsign/qtestsign.py adsp "$OUT_UNS" -v 3 -o "$OUT_SIG" >/dev/null
echo "signed: $OUT_SIG ($(wc -c < "$OUT_SIG") bytes)  [stock signed = 10999580]"
echo "DONE."
