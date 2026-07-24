#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# snapFMD1 reader: framer-MODE decision (folyt.130). FMDA block = ACTIVE branch taken,
# FMDE block = EXTERNAL branch taken. Exactly one should be present per boot/SSR.
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; HDR=0x2ab0
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA); buf=m.read(WIN); m.close()
def blk(off, tag):
    mg=buf[HDR+off:HDR+off+4]
    hit = mg==tag
    print(f"{tag.decode()} magic @+{off:#x}: {mg} -> {'HIT' if hit else 'miss'}")
    if hit:
        ctx,mode,e08,e58,db4,x6c,caller=struct.unpack_from("<7I",buf,HDR+off+4)
        print(f"    ctx           = {ctx:#010x}")
        print(f"    memw(ctx+0x78)= {mode:#010x}  (mode-flag: 1=active-prev, 0=external-prev)")
        print(f"    memw(ctx+0xe08)= {e08:#010x}  (detector input, bit0 tested = {e08&1})")
        print(f"    memw(ctx+0xe58)= {e58:#010x}")
        print(f"    memw(ctx+0xdb4)= {db4:#010x}")
        print(f"    memw(ctx+0x6c) = {x6c:#010x}")
        print(f"    caller r31    = {caller:#010x}")
    return hit
print("==== FMD1 framer-mode capture ====")
a=blk(0x00, b"FMDA")   # ACTIVE  framer mode (ADSP drives framer = healthy)
e=blk(0x40, b"FMDE")   # EXTERNAL framer mode (waits for external = dead behaviour)
print("---- verdict ----")
if a and not e: print("  ACTIVE  branch taken (framer driven by this ADSP)")
elif e and not a: print("  EXTERNAL branch taken (ADSP waiting for external framer) *** (C1) SMOKING GUN ***")
elif a and e: print("  BOTH stamped (decision re-ran / both branches hit) — inspect callers")
else: print("  NEITHER fired (mode-decision code not reached this run)")
