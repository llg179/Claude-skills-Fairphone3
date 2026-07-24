#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# build_ut_cave_min.py — PARAMETRIZED minimal-change UT-PIL-TZ resign (generalizes build_ut_cave_minimal.py,
# folyt.165). Keeps stock QC split-MDT hashseg format byte-for-byte; changes only:
#   - adsp.b04 (.text): splice SPLICE_VA -> CAVE_VA (payload = <cavebin>, identical placement to the pmOS mbn)
#   - the hashseg b04-hash slot in BOTH adsp.b01 (@0xa8) and adsp.mdt (@0x234+0xa8=0x2dc): SHA256 refresh
# The signature over the table goes stale but is unverified with secure boot off (same premise as the pmOS/PAS
# qtestsign path). See build_ut_cave_minimal.py header + folyt.163 for the hashseg format RE.
#
# Usage: build_ut_cave_min.py --indir UTFW --outdir UTFW-min-X --cavebin snapFSS2.bin \
#            --splice 0xf04ca3d8 --stock 0x9390f620 --cave 0xf064e098
import hashlib, struct, os, argparse
TEXT_VA=0xf015f000; B04_HASH_OFF=0xa8; MDT_HASHSEG_OFF=0x234
HERE=os.path.dirname(os.path.abspath(__file__))

def enc_jump(pc,t):
    s=(t-pc)//4; imm=s&0x3FFFFF
    return ((0b0101100<<25)|(((imm>>13)&0x1FF)<<16)|(0b11<<14)|((imm&0x1FFF)<<1))&0xFFFFFFFF

def main(a):
    import shutil
    os.makedirs(a.outdir,exist_ok=True)
    for f in os.listdir(a.indir):
        if f.startswith("adsp."): shutil.copy(os.path.join(a.indir,f),os.path.join(a.outdir,f))
    b04=bytearray(open(os.path.join(a.indir,"adsp.b04"),"rb").read())
    sp=a.splice-TEXT_VA; cv=a.cave-TEXT_VA
    got=struct.unpack_from("<I",b04,sp)[0]
    assert got==a.stock, f"b04 splice stock mismatch: {got:#x} != {a.stock:#x} (wrong fw?)"
    cave=open(os.path.join(HERE,a.cavebin),"rb").read()
    assert b04[cv:cv+len(cave)]==b"\x00"*len(cave), "cave region in b04 not zero"
    b04[cv:cv+len(cave)]=cave
    struct.pack_into("<I",b04,sp,enc_jump(a.splice,a.cave))
    open(os.path.join(a.outdir,"adsp.b04"),"wb").write(b04)
    newh=hashlib.sha256(bytes(b04)).digest()
    oldh=hashlib.sha256(open(os.path.join(a.indir,"adsp.b04"),"rb").read()).digest()
    for fname,slot in (("adsp.b01",B04_HASH_OFF),("adsp.mdt",MDT_HASHSEG_OFF+B04_HASH_OFF)):
        d=bytearray(open(os.path.join(a.indir,fname),"rb").read())
        assert d[slot:slot+32]==oldh, f"{fname}@{slot:#x} != stock b04 hash (layout drift)"
        d[slot:slot+32]=newh
        open(os.path.join(a.outdir,fname),"wb").write(bytes(d))
    diff=[f for f in sorted(os.listdir(a.outdir)) if f.startswith("adsp.") and
          open(os.path.join(a.indir,f),"rb").read()!=open(os.path.join(a.outdir,f),"rb").read()]
    print(f"minimal-change UT cave ({a.cavebin}) splice={a.splice:#x} -> {a.outdir}/")
    print(f"  new b04 sha256 = {newh.hex()[:16]}…  (was {oldh.hex()[:16]}…)")
    print(f"  differ from stock: {diff}  (expect exactly adsp.b01, adsp.b04, adsp.mdt)")

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--indir",required=True); ap.add_argument("--outdir",required=True)
    ap.add_argument("--cavebin",required=True)
    ap.add_argument("--splice",required=True,type=lambda x:int(x,0))
    ap.add_argument("--stock",required=True,type=lambda x:int(x,0))
    ap.add_argument("--cave",required=True,type=lambda x:int(x,0))
    main(ap.parse_args())
