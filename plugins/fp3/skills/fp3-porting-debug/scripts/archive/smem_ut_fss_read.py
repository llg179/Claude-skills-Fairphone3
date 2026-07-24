#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Reads the UT-side FSS1 cave (WORKING side): framer regs at the framing-START code point when capability
# SUCCEEDS. Same SMEM slot/layout as FSS1 (magic 'FSS1'). SMEM PA 0x86300000 + 0x2ab0.
# On UT the STRICT_DEVMEM path is OFF, so /dev/mem RAM reads (SMEM is DDR, not gated MMIO) work.
# THE DISAMBIGUATING VALUE = wait-return (expect 0 = success on UT) + +0x600 ENABLE at that instant.
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; HDR=0x2ab0
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA); buf=m.read(WIN); m.close()
mg=buf[HDR:HDR+4]
print("UT-FSS magic:", mg, "->", "HIT" if mg==b"FSS1" else "MISS")
if mg==b"FSS1":
    (wret,base,r204,r404,r430,r604,r804,r600,r610,r604b,r804b,cnt)=struct.unpack_from("<12I",buf,HDR+4)
    print(f"  reached-count        = {cnt}")
    print(f"  wait-return (r0)     = {wret:#010x}   <- expect 0x0 on UT (capability SUCCEEDED); vs 0xfffffffe on dead")
    print(f"  framer base          = {base:#010x}   <- expect 0xee140000")
    print(f"  +0x600 ENABLE        = {r600:#010x}   <<< THE ANSWER")
    print(f"  +0x610 control       = {r610:#010x}")
    print(f"  +0x604 FS/SFS/MS     = {r604:#010x}")
    print(f"  +0x404 FRM_STAT      = {r404:#010x}")
    print(f"  +0x804 running-bit   = {r804:#010x}")
    print(f"  +0x204/+0x430        = {r204:#010x} / {r430:#010x}")
    print()
    print("  DISAMBIGUATION (vs FSS1 dead-side: wait=-2, enable=0, FS=0, FRM_STAT=0):")
    if base!=0xee140000:
        print("  ?? framer base unexpected -> ctx drift; caution.")
    elif r600==0x1 or r604 or r404:
        print("  ** UT has ENABLE=1 (and/or FS/FRM_STAT set) AT the framing-START code point, while the dead side")
        print("     had enable=0 there. => the framer enable PRECEDES / is independent of the capability handshake.")
        print("     => the dead side SKIPS the enable (upstream lever), NOT merely a downstream capability timeout.")
        print("     Redirect: locate what gates the enable write on the dead side (a real AP/PAS-fixable lever?).")
    else:
        print("  == UT ALSO has enable=0 at this code point (capability just succeeded). => the enable FOLLOWS the")
        print("     capability handshake on both sides. => on the dead side the capability timeout is the GATE")
        print("     (revises folyt.131b 'capability subsumed'). Redirect: the capability handshake itself (why it")
        print("     times out under PAS) is the true locus.")
