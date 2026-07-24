#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# SAFE: reads ONLY the proven-safe SMEM base 0x86300000 (single bounded mmap).
# Parses the legacy SMEM header + TOC to locate item id=469 (IMAGE_VERSION_TABLE)
# and dump the ADSP version slot (#12). No speculative PAs. Rule-4b compliant.
import mmap, struct, sys

SMEM_PA   = 0x86300000
WIN       = 0x40000        # 256 KB window, entirely inside the SMEM region
ITEM_ID   = 469            # IMAGE_VERSION_TABLE
SLOT      = 128            # per-image slot size
ADSP_IDX  = 12

def u32(b, o): return struct.unpack_from("<I", b, o)[0]

with open("/dev/mem", "rb") as f:
    m = mmap.mmap(f.fileno(), WIN, mmap.MAP_SHARED, mmap.PROT_READ, offset=SMEM_PA)
    buf = m.read(WIN)
    m.close()

# legacy heap_info @ +0xC0: initialized, free_offset, heap_remaining, reserved
init      = u32(buf, 0xC0)
free_off  = u32(buf, 0xC4)
heap_rem  = u32(buf, 0xC8)
print(f"heap_info: initialized={init:#x} free_offset={free_off:#x} heap_remaining={heap_rem:#x}")

# TOC entry for ITEM_ID @ 0xD0 + id*16 : allocated, offset, size, aux_base
toc = 0xD0 + ITEM_ID * 16
alloc  = u32(buf, toc + 0)
offset = u32(buf, toc + 4)
size   = u32(buf, toc + 8)
aux    = u32(buf, toc + 12)
print(f"item {ITEM_ID}: alloc={alloc:#x} offset={offset:#x} size={size:#x} aux={aux:#x}")
print(f"  -> item PA = {SMEM_PA + offset:#010x}")

if not alloc or offset == 0 or offset + size > WIN:
    print("!! item not allocated or outside window -- STOP")
    sys.exit(1)

# dump each 128-byte slot; highlight ADSP (#12)
for i in range(min(size // SLOT, 16)):
    s = buf[offset + i*SLOT: offset + i*SLOT + SLOT]
    txt = s.split(b"\x00")[0].decode("latin1", "replace")
    star = " <== ADSP #12" if i == ADSP_IDX else ""
    if txt.strip() or i == ADSP_IDX:
        print(f"  slot {i:2d} @+{offset + i*SLOT:#06x} (PA {SMEM_PA+offset+i*SLOT:#010x}): {txt!r}{star}")

adsp_pa = SMEM_PA + offset + ADSP_IDX*SLOT
print(f"\nADSP version slot PA = {adsp_pa:#010x}  (offset-in-smem {offset + ADSP_IDX*SLOT:#x})")
