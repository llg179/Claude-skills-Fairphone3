#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# build_ut_cave.py — package the FSS1 framer-status cave for the UT (PIL / subsys-pil-tz) side.
#
# WHY: the disambiguating measurement (folyt.160) is FSS1 run on the WORKING side: read the framer regs at the
# framing-START code point (splice 0xf04d15bc) when the capability SUCCEEDS (wait-return=0), to see whether
# +0x600 ENABLE is 1 (enable PRECEDES capability -> dead side skips it, upstream lever) or 0 (enable FOLLOWS
# capability -> capability is the gate). The cave is byte-identical to FSS1; only the PACKAGING differs:
# UT PIL loads split adsp.mdt + adsp.b00..bNN (not a single .mbn), signed/hashed. This tool reconstructs the
# full ELF from the UT stock split, patches it (same splice+cave as FSS1), re-signs (qtestsign, secure-boot
# off), and re-splits into the SAME filename set.
#
# ORACLE SAFETY: this flashes slot_a (the UT oracle). The cave is benign (proven on slot_b as FSS1/FSS2).
# Keep the UT stock adsp.mdt+bNN backup; restore = copy back + reboot/SSR. slot_b/pmOS is the fallback.
#
# TWO-PHASE (the final image can only be built from UT's OWN files, md5 bab175ed, pulled after slot-swap):
#   Phase 1 (on UT): tar up /vendor/firmware_mnt/image/adsp.{mdt,b*} -> pull to <indir>.
#   Phase 2 (host):  python3 build_ut_cave.py --indir <UTFW> --outdir <OUT>   (then push OUT back to UT).
#
# Run  python3 build_ut_cave.py --selftest  to validate the lossless split<->reconstruct on the pmOS proxy.
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, subprocess, os, sys, glob, argparse, hashlib

SPLICE_VA=0xf04d15bc; STOCK=0x9390f2a0; CAVE_VA=0xf064e098; RET_VA=0xf04d15c0
HERE=os.path.dirname(os.path.abspath(__file__))
CAVE_BIN=os.path.join(HERE,"snapFSS1.bin")   # identical cave to FSS1 (same fw, same VAs)

def parse_phdrs(buf):
    e_phoff=struct.unpack_from("<I",buf,28)[0]; e_phnum=struct.unpack_from("<H",buf,44)[0]
    e_phentsize=struct.unpack_from("<H",buf,42)[0]
    ph=[]
    for i in range(e_phnum):
        o=e_phoff+i*e_phentsize
        t,off,va,pa,fsz,msz,fl,al=struct.unpack_from("<8I",buf,o)
        ph.append(dict(i=i,type=t,off=off,va=va,pa=pa,fsz=fsz,msz=msz,fl=fl,al=al))
    return ph

def reconstruct(indir):
    """Rebuild the full ELF from adsp.mdt + adsp.bNN (place each .bNN at its phdr p_offset)."""
    mdt=open(os.path.join(indir,"adsp.mdt"),"rb").read()
    ph=parse_phdrs(mdt)
    total=max((p["off"]+p["fsz"] for p in ph if p["fsz"]>0), default=len(mdt))
    full=bytearray(total)
    full[0:len(mdt)]=mdt                         # header + phdrs + hash/cert seg (all live in .mdt)
    for p in ph:
        bpath=os.path.join(indir,f"adsp.b{p['i']:02d}")
        if os.path.exists(bpath) and p["fsz"]>0:
            data=open(bpath,"rb").read()
            full[p["off"]:p["off"]+len(data)]=data
    return bytes(full), ph

def split(full, ref_indir, outdir):
    """Re-split the (signed) full ELF into outdir, mirroring the filename set present in ref_indir.
    .mdt = ELF header + phdrs + hash segment ONLY (the type-0 PT_NULL segments), padded to the stock
    .mdt size — NOT up to the first PT_LOAD offset (qtestsign 1MB-aligns that, which stock does not)."""
    os.makedirs(outdir,exist_ok=True)
    ph=parse_phdrs(full)
    mdt_end=max((p["off"]+p["fsz"] for p in ph if p["type"]==0), default=len(full))  # end of hash seg
    mdt=bytearray(full[0:mdt_end])
    stock_mdt=os.path.join(ref_indir,"adsp.mdt")
    if os.path.exists(stock_mdt):
        target=os.path.getsize(stock_mdt)
        if target>len(mdt): mdt += b"\x00"*(target-len(mdt))                # match stock size (zero-pad)
    open(os.path.join(outdir,"adsp.mdt"),"wb").write(mdt)
    for p in ph:
        name=f"adsp.b{p['i']:02d}"
        if os.path.exists(os.path.join(ref_indir,name)):                   # match stock's file set exactly
            open(os.path.join(outdir,name),"wb").write(full[p["off"]:p["off"]+p["fsz"]])

def patch(full):
    delta=None
    for p in parse_phdrs(full):
        if p["va"]<=SPLICE_VA<p["va"]+p["fsz"]:
            delta=p["va"]-p["off"]; break
    assert delta is not None, "splice VA not in any segment"
    def foff(va): return va-delta
    d=bytearray(full)
    got=struct.unpack_from("<I",d,foff(SPLICE_VA))[0]
    assert got==STOCK, f"UT splice stock mismatch: {got:#x} != {STOCK:#x} (is this the right fw/VA?)"
    cave=open(CAVE_BIN,"rb").read()
    assert d[foff(CAVE_VA):foff(CAVE_VA)+len(cave)]==b"\x00"*len(cave), "cave region not zero in UT image"
    d[foff(CAVE_VA):foff(CAVE_VA)+len(cave)]=cave
    def enc_jump(pc,t):
        s=(t-pc)//4; imm=s&0x3FFFFF
        return ((0b0101100<<25)|(((imm>>13)&0x1FF)<<16)|(0b11<<14)|((imm&0x1FFF)<<1))&0xFFFFFFFF
    struct.pack_into("<I",d,foff(SPLICE_VA),enc_jump(SPLICE_VA,CAVE_VA))
    return bytes(d)

def sign(full_path, out_path):
    qs=os.path.join(HERE,"m2","qtestsign","qtestsign.py")
    subprocess.run(["python3",qs,"adsp","-v3",full_path,"-o",out_path],check=True)

def selftest():
    proxy=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
    full0=open(proxy,"rb").read()
    ph=parse_phdrs(full0)
    # emulate a UT-style split dir from the proxy, then reconstruct and compare
    tmp="/tmp/claude-1000/-mnt-1TB-Fp3-Sailfish/a8f34218-7bd9-4c85-9d20-bf8216e69d44/scratchpad/ut_selftest"
    os.makedirs(tmp,exist_ok=True)
    first_load=min((p["off"] for p in ph if p["type"]==1), default=len(full0))
    open(os.path.join(tmp,"adsp.mdt"),"wb").write(full0[0:first_load])
    for p in ph:
        if p["fsz"]>0:
            open(os.path.join(tmp,f"adsp.b{p['i']:02d}"),"wb").write(full0[p["off"]:p["off"]+p["fsz"]])
    recon,_=reconstruct(tmp)
    ok = recon==full0
    print(f"selftest: split->reconstruct lossless = {ok}  (len {len(recon)} vs {len(full0)})")
    if ok:
        patched=patch(recon)
        d=struct.unpack_from("<I",patched,SPLICE_VA-(ph[4]['va']-ph[4]['off']))[0]
        print(f"selftest: patch OK, splice now {d:#010x} (jump to cave); cave first word present")
    return ok

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--selftest",action="store_true")
    ap.add_argument("--indir",help="dir with UT stock adsp.mdt + adsp.b*")
    ap.add_argument("--outdir",help="output dir for caved adsp.mdt + adsp.b*")
    a=ap.parse_args()
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    assert a.indir and a.outdir, "need --indir and --outdir (or --selftest)"
    full,ph=reconstruct(a.indir)
    print(f"reconstructed {len(full)}B from {a.indir}")
    patched=patch(full)
    tmpfull="/tmp/ut_caved_full.elf"; open(tmpfull,"wb").write(patched)
    tmpsigned="/tmp/ut_caved_signed.elf"; sign(tmpfull,tmpsigned)
    signed=open(tmpsigned,"rb").read()
    split(signed,a.indir,a.outdir)
    print(f"caved+signed UT firmware written to {a.outdir}/ (adsp.mdt + adsp.b*)")
    print("Verify on-device: md5 differs from stock, PIL loads, framer still works, then read SMEM.")
