#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# build_ut_cave_minimal.py — MINIMAL-CHANGE packaging of the FSS1 cave for UT PIL-TZ (folyt.163).
# The qtestsign path is rejected by subsys-pil-tz (rc:-22, folyt.162). This keeps the stock QC metadata
# format byte-for-byte and changes only what MUST change:
#   - adsp.b04  (the .text segment): splice 0xf04d15bc -> cave 0xf064e098 (identical cave to FSS1)
#   - the hashseg's b04 hash slot: SHA256(stock b04) -> SHA256(caved b04)
# QC hashseg format (RE'd folyt.163): [0x28-byte header][ SHA256(seg_i) at 0x28 + i*0x20 ][signature][cert].
# The full hashseg lives in BOTH adsp.b01 (offset 0xa8 = b04 slot) AND packed in adsp.mdt (at file 0x234, so
# b04 slot at 0x234+0xa8 = 0x2dc). We update BOTH so they stay consistent. hash[0]=SHA256(metadata) and the
# header are untouched (we don't touch ehdr/phdrs). The signature over the table goes stale but is not verified
# with secure boot off (same premise that lets qtestsign work on the pmOS/PAS side).
import hashlib, struct, os, sys, shutil, argparse

SPLICE_VA=0xf04d15bc; STOCK=0x9390f2a0; CAVE_VA=0xf064e098; RET_VA=0xf04d15c0
TEXT_VA=0xf015f000                      # adsp.b04 = ELF seg4, base vaddr (b04 offset 0 == this VA)
B04_HASH_OFF=0xa8                       # b04 hash slot within the hashseg
MDT_HASHSEG_OFF=0x234                   # hashseg is packed at 0x234 in adsp.mdt (right after ehdr+phdrs)
HERE=os.path.dirname(os.path.abspath(__file__))
CAVE_BIN=os.path.join(HERE,"snapFSS1.bin")

def enc_jump(pc,t):
    s=(t-pc)//4; imm=s&0x3FFFFF
    return ((0b0101100<<25)|(((imm>>13)&0x1FF)<<16)|(0b11<<14)|((imm&0x1FFF)<<1))&0xFFFFFFFF

def main(indir,outdir):
    os.makedirs(outdir,exist_ok=True)
    # 1. copy every stock file verbatim
    for f in os.listdir(indir):
        if f.startswith("adsp."): shutil.copy(os.path.join(indir,f),os.path.join(outdir,f))
    # 2. patch b04 (.text) in place
    b04=bytearray(open(os.path.join(indir,"adsp.b04"),"rb").read())
    sp=SPLICE_VA-TEXT_VA; cv=CAVE_VA-TEXT_VA
    got=struct.unpack_from("<I",b04,sp)[0]
    assert got==STOCK, f"b04 splice stock mismatch: {got:#x} != {STOCK:#x} (wrong fw?)"
    cave=open(CAVE_BIN,"rb").read()
    assert b04[cv:cv+len(cave)]==b"\x00"*len(cave), "cave region in b04 not zero"
    b04[cv:cv+len(cave)]=cave
    struct.pack_into("<I",b04,sp,enc_jump(SPLICE_VA,CAVE_VA))
    open(os.path.join(outdir,"adsp.b04"),"wb").write(b04)
    # 3. new hash of the patched b04
    newh=hashlib.sha256(bytes(b04)).digest()
    oldh=hashlib.sha256(open(os.path.join(indir,"adsp.b04"),"rb").read()).digest()
    # 4. update the hashseg's b04 slot in BOTH adsp.b01 and adsp.mdt
    for fname,slot in (("adsp.b01",B04_HASH_OFF),("adsp.mdt",MDT_HASHSEG_OFF+B04_HASH_OFF)):
        d=bytearray(open(os.path.join(indir,fname),"rb").read())
        assert d[slot:slot+32]==oldh, f"{fname}@{slot:#x} != stock b04 hash (layout drift)"
        d[slot:slot+32]=newh
        open(os.path.join(outdir,fname),"wb").write(bytes(d))
    print(f"minimal-change UT cave -> {outdir}/")
    print(f"  patched: adsp.b04 (.text), adsp.b01 & adsp.mdt (b04 hash slot)")
    print(f"  new b04 sha256 = {newh.hex()[:16]}…  (was {oldh.hex()[:16]}…)")
    # 5. report which files differ from stock
    diff=[f for f in sorted(os.listdir(outdir)) if f.startswith("adsp.") and
          open(os.path.join(indir,f),"rb").read()!=open(os.path.join(outdir,f),"rb").read()]
    print(f"  differ from stock: {diff}  (expect exactly adsp.b01, adsp.b04, adsp.mdt)")

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--indir",required=True); ap.add_argument("--outdir",required=True)
    a=ap.parse_args(); main(a.indir,a.outdir)
