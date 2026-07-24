#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Resolve ADSP VIRTUAL addresses (0xf0xxxxxx) into the remoteproc COREDUMP, which is indexed by PHYSICAL
# address. Bridge = the static adsp.mbn phdr table (each LOAD gives vaddr+paddr) for VA->PA, then the
# coredump phdr table (vaddr field = PA) for PA->file-offset. Reads RUNTIME values (heap/BSS populated),
# unlike the static image. Usage: import and call read_words(va,n) / hexdump(va,n), or run with VAs as argv.
import os

# Config: override via the environment (see fp3-env.sh in this skill's scripts/ directory). The value after the comma is the default.
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root (device images, dumps, journal)

import struct, sys
MBN=f"{FP3_ROOT}/scratchpad-durable-adsp.mbn"
DUMP=f"{FP3_ROOT}/adsp-coredump.elf"
def phdrs(data):
    e_phoff=struct.unpack_from("<I",data,0x1c)[0]; e_phnum=struct.unpack_from("<H",data,0x2c)[0]
    out=[]
    for i in range(e_phnum):
        typ,off,va,pa,fsz,msz,fl,al=struct.unpack_from("<8I",data,e_phoff+i*32)
        if typ==1: out.append(dict(off=off,va=va,pa=pa,fsz=fsz,msz=msz))
    return out
_mbn=open(MBN,"rb").read(); _dump=open(DUMP,"rb").read()
_MP=phdrs(_mbn); _DP=phdrs(_dump)     # mbn: va/pa valid.  dump: 'va' field actually holds PA.
def va2pa(va):
    for p in _MP:
        if p["va"] and p["va"]<=va<p["va"]+p["msz"]: return p["pa"]+(va-p["va"])
    return None
def pa2foff(pa):
    for p in _DP:
        if p["pa"]<=pa<p["pa"]+p["fsz"]: return p["off"]+(pa-p["pa"])
    return None
def resolve(va):
    pa=va2pa(va)
    if pa is None: return None,None
    return pa, pa2foff(pa)
def read_words(va,n=1):
    pa,fo=resolve(va)
    if fo is None: return None
    return [struct.unpack_from("<I",_dump,fo+i*4)[0] for i in range(n)]
def tag(w):
    if 0xee000000<=w<0xee400000: return "  <== ★ LPASS MMIO base"
    if 0xf0000000<=w<0xf1000000: return "  <- ADSP ptr"
    return ""
if __name__=="__main__":
    vas=[int(x,0) for x in sys.argv[1:]] or [0xf0953ed8,0xf0a02250,0xf0a03cd0,0xf0a07cf0]
    for va in vas:
        pa,fo=resolve(va)
        if fo is None: print(f"{va:#010x}: unresolved (pa={pa})"); continue
        print(f"{va:#010x} (pa {pa:#010x}, foff {fo:#x}):")
        for i,w in enumerate(read_words(va,16)):
            t=tag(w)
            if t or w: print(f"    +{i*4:#04x} = {w:#010x}{t}")
