#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Build a UT p1 (vfat firmware) image from a PAS-signed adsp mbn, using the PROVEN
# compact-mdt + full-split recipe (folyt.80, confirmed vs ut-p1-hwl4.img):
#   adsp.b{i:02d} = mbn[ph[i].off : +ph[i].filesz]  for each phdr i with filesz>0
#   adsp.mdt (compact) = mbn[ph0.off:+ph0.filesz] + mbn[ph1.off:+ph1.filesz]  (header+hash, contiguous)
# Replaces /image/adsp.* in a COPY of the stock p1 (loopback-mount RW).
# usage: build_ut_p1.py <signed.mbn> <stock_p1.img> <out_p1.img>
import struct, sys, os, subprocess, shutil
mbnf, stock, out = sys.argv[1], sys.argv[2], sys.argv[3]
mbn=open(mbnf,"rb").read()
e_phoff=struct.unpack_from("<I",mbn,0x1c)[0]; e_phnum=struct.unpack_from("<H",mbn,0x2c)[0]
phs=[struct.unpack_from("<8I",mbn,e_phoff+i*32) for i in range(e_phnum)]  # type,off,vaddr,paddr,filesz,memsz,flags,align
# compact mdt = ph0 + ph1 (header + hash), contiguous
ph0, ph1 = phs[0], phs[1]
mdt = mbn[ph0[1]:ph0[1]+ph0[4]] + mbn[ph1[1]:ph1[1]+ph1[4]]
# full split: b{i} = ph[i] data (skip filesz==0)
segs={}
for i,ph in enumerate(phs):
    if ph[4] > 0:
        segs[i]=mbn[ph[1]:ph[1]+ph[4]]
print(f"mdt {len(mdt)}B (ph0 {ph0[4]} + ph1 {ph1[4]}); {len(segs)} bNN segments: "+
      ",".join(f"b{i:02d}={len(d)}" for i,d in sorted(segs.items())))
# copy stock -> out
shutil.copy(stock, out)
mnt="/tmp/p1build_mnt"; os.makedirs(mnt, exist_ok=True)
def run(c): return subprocess.run(["bash","-lc",c],check=True)
run(f"sudo mount -o loop,rw {out} {mnt}")
try:
    run(f"sudo rm -f {mnt}/image/adsp.b* {mnt}/image/adsp.mdt")
    # write mdt + bNN
    with open("/tmp/_mdt","wb") as f: f.write(mdt)
    run(f"sudo cp /tmp/_mdt {mnt}/image/adsp.mdt")
    for i,d in sorted(segs.items()):
        with open("/tmp/_seg","wb") as f: f.write(d)
        run(f"sudo cp /tmp/_seg {mnt}/image/adsp.b{i:02d}")
    run(f"sudo sync")
    print("injected. listing:")
    run(f"sudo ls -la {mnt}/image/adsp.mdt {mnt}/image/adsp.b00 {mnt}/image/adsp.b04")
finally:
    run(f"sudo umount {mnt}")
print(f"-> {out}")
