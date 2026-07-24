#!/bin/bash
# build_m3.sh — M3 clock-work rc/handle trace. Splices TWO pieces into stock adsp.mbn:
#   (a) a 4-byte relative `jump 0xf064e098` over the packet at 0xf04bfb00
#       (the post-DAL-call `jump 0xf04bfb5c` in the SLIMbus clock-work fn),
#   (b) the m3trace.s cave stub at the free code cave 0xf064e098.
# Then re-sign (qtestsign -v3, secure-boot off). Produces adsp-m3-signed.mbn.
# Deploy with deploy_m2b.sh after: SIG=adsp-m3-signed.mbn ./deploy_m2b.sh (edit SIG).
# One change / run; stock adsp.mbn never modified in place.
set -euo pipefail
cd "$(dirname "$0")"

STOCK=adsp.mbn
STUB=m3trace.s
CAVE_VADDR=0xf064e098          # free R-X cave (128+ zero bytes verified)
INJECT_VADDR=0xf04bfb00        # single 4-byte packet: jump 0xf04bfb5c
OUT_UNS=adsp-m3.mbn
OUT_SIG=adsp-m3-signed.mbn

# 1) tools
MC=""; OC=""
for v in "" -22 -21 -18 -17 -16 -15 -14 -13; do
  command -v "llvm-mc$v"      >/dev/null 2>&1 && MC="llvm-mc$v"
  command -v "llvm-objcopy$v" >/dev/null 2>&1 && OC="llvm-objcopy$v"
  [ -n "$MC" ] && [ -n "$OC" ] && break
done
[ -n "$MC" ] || { echo "ERROR: no llvm-mc with Hexagon"; exit 1; }
[ -n "$OC" ] || { echo "ERROR: no llvm-objcopy"; exit 1; }
echo "using: $MC / $OC"

# 2) assemble the cave stub
"$MC" --arch=hexagon --mcpu=hexagonv60 --filetype=obj "$STUB" -o m3trace.o
"$OC" -O binary --only-section=.text m3trace.o m3trace.bin
echo "cave stub: $(wc -c < m3trace.bin) bytes"

# 3) splice both pieces + compute+verify the 4-byte relative jump encoding
python3 - "$STOCK" m3trace.bin "$OUT_UNS" "$INJECT_VADDR" "$CAVE_VADDR" <<'PY'
import struct, sys, shutil
stock, stub, out, inj, cave = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4],0), int(sys.argv[5],0)
d = open(stock,"rb").read()
assert d[:4]==b"\x7fELF"
phoff=struct.unpack_from("<I",d,0x1c)[0]; phes=struct.unpack_from("<H",d,0x2a)[0]; phn=struct.unpack_from("<H",d,0x2c)[0]
def v2o(va):
    for i in range(phn):
        t,o,v,pa,fs,ms,fl,al=struct.unpack_from("<8I",d,phoff+i*phes)
        if t==1 and fs>0 and v<=va<v+fs: return o+(va-v)
    raise SystemExit("vaddr 0x%x not file-backed"%va)

# --- encode J2_jump (4-byte, PC-relative, +-2MB). Base opcode from the known
#     reference `jump 0xf04bfb5c`@f04bfb00 = 0x5800c02e (offset 0x5c). ---
BASE = 0x5800C000            # opcode with imm bits cleared, parse=11
off = cave - inj
assert off % 4 == 0
imm = off >> 2
assert -(1<<21) <= imm < (1<<21), "jump target out of +-2MB range"
imm &= 0x3FFFFF
word = BASE | ((imm>>13 & 0x1FF)<<16) | ((imm & 0x1FFF)<<1)
# round-trip decode to be safe
di_hi=(word>>16)&0x1FF; di_lo=(word>>1)&0x1FFF; dimm=(di_hi<<13)|di_lo
if dimm & (1<<21): dimm -= (1<<22)
tgt = inj + (dimm<<2)
assert tgt == cave, "encode/decode mismatch: 0x%x != 0x%x"%(tgt,cave)
jbytes = struct.pack("<I", word)
print("jump word = 0x%08x  bytes=%s  -> target 0x%x (verified)"%(word, jbytes.hex(), tgt))

shutil.copyfile(stock, out)
buf = bytearray(open(out,"rb").read())
# (b) cave stub
co = v2o(cave); code = open(stub,"rb").read()
assert all(b==0 for b in buf[co:co+len(code)]), "cave not empty!"
buf[co:co+len(code)] = code
# (a) 4-byte jump
io = v2o(inj); orig = bytes(buf[io:io+4])
buf[io:io+4] = jbytes
open(out,"wb").write(buf)
print("cave  @ file 0x%x : %d bytes"%(co,len(code)))
print("inject@ file 0x%x : %s -> %s"%(io, orig.hex(), jbytes.hex()))
PY

# 4) re-sign
python3 qtestsign/qtestsign.py adsp "$OUT_UNS" -v 3 -o "$OUT_SIG"
echo "signed: $OUT_SIG ($(wc -c < "$OUT_SIG") bytes)  [stock signed = 10999580]"
echo "DONE. Deploy: edit deploy_m2b.sh SIG=$OUT_SIG then ./deploy_m2b.sh"
