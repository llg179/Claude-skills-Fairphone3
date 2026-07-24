#!/bin/bash
# build_m15.sh — M15 framer-GATE 5-condition trace. Splices TWO pieces into stock:
#   (a) the m15trace.s cave stub at 0xf064e098 (replicates the f04c97d0 gate +
#       logs all 5 conditions + which branch to SMEM),
#   (b) a 4-byte relative `jump 0xf064e098` OVER the first word of the entry packet
#       at 0xf04c97d0 (orig `02 4b 10 91` = { r2 = memb(r16+#0x58) ... }). The stock
#       word is parse=01 (2-word packet); the rel jump is parse=11 (self-contained),
#       so the old second word 0xf04c97d4 becomes a dead never-reached packet (same
#       technique as m9). The cave fully reproduces the gate decision -> non-crashing.
# Re-sign (qtestsign -v3). Produces adsp-m15-signed.mbn.
set -euo pipefail
cd "$(dirname "$0")"

STOCK=adsp.mbn
STUB=m15trace.s
CAVE_VADDR=0xf064e098
INJECT_VADDR=0xf01733e0        # first word of the gate entry packet; orig = 04 c0 9d a0 = { allocframe(#0x20) }
ORIG_HEX=04c09da0
OUT_UNS=adsp-m15.mbn
OUT_SIG=adsp-m15-signed.mbn

MC=""; OC=""
for v in "" -22 -21 -18 -17 -16 -15 -14 -13; do
  command -v "llvm-mc$v" >/dev/null 2>&1 && MC="llvm-mc$v"
  command -v "llvm-objcopy$v" >/dev/null 2>&1 && OC="llvm-objcopy$v"
  [ -n "$MC" ] && [ -n "$OC" ] && break
done
[ -n "$MC" ] && [ -n "$OC" ] || { echo "ERROR: need llvm-mc + llvm-objcopy (Hexagon)"; exit 1; }
echo "using: $MC / $OC"

"$MC" --arch=hexagon --mcpu=hexagonv60 --filetype=obj "$STUB" -o m15trace.o
"$OC" -O binary --only-section=.text m15trace.o m15trace.bin
echo "cave stub: $(wc -c < m15trace.bin) bytes"

python3 - "$STOCK" m15trace.bin "$OUT_UNS" "$INJECT_VADDR" "$CAVE_VADDR" "$ORIG_HEX" <<'PY'
import struct, sys, shutil
stock, stub, out, inj, cave, orighex = (sys.argv[1], sys.argv[2], sys.argv[3],
                                        int(sys.argv[4],0), int(sys.argv[5],0), sys.argv[6])
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
# verify decode round-trips
hi=(word>>16)&0x1FF; lo=(word>>1)&0x1FFF; dimm=(hi<<13)|lo
if dimm&(1<<21): dimm-=(1<<22)
assert inj+(dimm<<2)==cave, "encode mismatch"
jb=struct.pack("<I",word)
print("jump word=0x%08x bytes=%s -> 0x%x (verified)"%(word,jb.hex(),cave))
shutil.copyfile(stock,out)
buf=bytearray(open(out,"rb").read())
# (a) cave
code=open(stub,"rb").read()
co=v2o(cave)
assert all(b==0 for b in buf[co:co+len(code)]), "cave not empty!"
buf[co:co+len(code)]=code
print("cave  @ file 0x%x : %d bytes"%(co,len(code)))
# (b) inject rel jump
io=v2o(inj); orig=bytes(buf[io:io+4])
assert orig==bytes.fromhex(orighex), "inject site mismatch! got %s want %s"%(orig.hex(),orighex)
buf[io:io+4]=jb
print("inject@ file 0x%x : %s -> %s"%(io, orig.hex(), jb.hex()))
open(out,"wb").write(buf)
PY

python3 qtestsign/qtestsign.py adsp "$OUT_UNS" -v 3 -o "$OUT_SIG" >/dev/null
echo "signed: $OUT_SIG ($(wc -c < "$OUT_SIG") bytes)  [stock signed = 10999580]"
echo "DONE."
