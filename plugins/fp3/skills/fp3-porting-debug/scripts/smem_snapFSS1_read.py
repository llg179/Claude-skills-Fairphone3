#!/usr/bin/env python3
# Reads the FSS1 privileged-side framer-status snapshot: SMEM PA 0x86300000 + 0x2ab0 (same slot as FST1).
# All framer regs are read by the ADSP itself (base 0xee140000) at the capability-timeout instant.
# Layout: 'FSS1' | wait-ret | frmbase | +0x204 | +0x404 | +0x430 | +0x604 | +0x804 | +0x600 | +0x610 |
#         +0x604(re) | +0x804(re) | count
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; HDR=0x2ab0
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA); buf=m.read(WIN); m.close()
mg=buf[HDR:HDR+4]
print("FSS1 magic:", mg, "->", "HIT" if mg==b"FSS1" else "MISS")
if mg==b"FSS1":
    (wret,base,r204,r404,r430,r604,r804,r600,r610,r604b,r804b,cnt)=struct.unpack_from("<12I",buf,HDR+4)
    print(f"  reached-count        = {cnt}   (times framing-START post-wait executed this SSR init)")
    print(f"  wait-return (r0)     = {wret:#010x}   <- expect 0xfffffffe (-2 TIMEOUT), sanity vs FST1")
    print(f"  framer base (ctx+5c) = {base:#010x}   <- expect 0xee140000 (ADSP-side framer aperture)")
    print(f"  --- framer STATUS read from the ADSP's OWN privileged view (not the AP alias) ---")
    print(f"  +0x204               = {r204:#010x}   (AP-alias dead read was 0x00000002)")
    print(f"  +0x404 FRM_STAT      = {r404:#010x}   (AP-alias dead read was 0x00000000; UT/working = 0x060d1901)")
    print(f"  +0x430               = {r430:#010x}   (AP-alias dead read was 0xfe010000)")
    print(f"  +0x604 FS/SFS/MS     = {r604:#010x}   (AP-alias dead read was 0x00000000; UT/working = 0x00003e04)")
    print(f"  +0x804 running-bit   = {r804:#010x}   (AP-alias dead read was 0x00400710; UT/working = 0x00c00710)")
    print(f"  +0x600 ENABLE        = {r600:#010x}   <- expect 0x1 (frame-enable latched, both sides)")
    print(f"  +0x610 control       = {r610:#010x}   <- expect 0x7 (both sides)")
    print(f"  +0x604 re-read       = {r604b:#010x}   <- differs from first? -> status is oscillating (PHY start-then-die)")
    print(f"  +0x804 re-read       = {r804b:#010x}   <- differs from first? -> status is oscillating")
    print()
    print("  INTERPRETATION:")
    fs_first = r404 or r604 or (r804 & 0x00800000)
    if base != 0xee140000:
        print("  ?? framer base unexpected -> ctx layout drift; treat other fields with caution.")
    elif fs_first or r604b or r804b & 0x00800000:
        print("  ** NON-ZERO framer status from the ADSP side while the AP alias read 0 (or a transient")
        print("     appears in the re-read) -> the framer DID (momentarily) come up; the AP-alias/XPU read")
        print("     was masking it. Redirect: codec/bus side, or a self-clearing PHY pulse. HIGH-VALUE.")
    else:
        print("  == framer status 0 from the ADSP's OWN privileged view too, with enable=1/control=7 latched")
        print("     and wait=-2. Definitive privileged-side confirmation: the framer HW state machine never")
        print("     starts under PAS despite being configured+enabled. Wall is below the register file")
        print("     (PHY-pad / clock-domain / access precondition), consistent with the whole investigation.")
