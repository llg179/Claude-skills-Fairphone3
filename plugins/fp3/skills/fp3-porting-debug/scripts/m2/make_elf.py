#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Wrap a raw code blob into a minimal elf32-hexagon with one .text at a given vaddr,
# so llvm-objdump -d gives correct PCs. Usage: make_elf.py in.bin out.elf 0xVADDR
import struct, sys
inb, outf, vaddr = sys.argv[1], sys.argv[2], int(sys.argv[3], 0)
code = open(inb, "rb").read()

shstr = b"\x00.text\x00.shstrtab\x00"
name_text = 1          # offset of ".text" in shstr
name_sst  = 7          # offset of ".shstrtab"

EHSIZE = 52
text_off = EHSIZE
sst_off  = text_off + len(code)
# align SHT to 4
sht_off  = (sst_off + len(shstr) + 3) & ~3
pad = sht_off - (sst_off + len(shstr))

# ELF32 header
e = b"\x7fELF" + bytes([1,1,1,0]) + b"\x00"*8   # e_ident
e += struct.pack("<HH", 2, 164)                  # e_type=EXEC, e_machine=EM_QDSP6
e += struct.pack("<I", 1)                        # e_version
e += struct.pack("<I", vaddr)                    # e_entry
e += struct.pack("<I", 0)                        # e_phoff
e += struct.pack("<I", sht_off)                  # e_shoff
e += struct.pack("<I", 0x60)                     # e_flags = Hexagon V60
e += struct.pack("<H", EHSIZE)                   # e_ehsize
e += struct.pack("<H", 0)                        # e_phentsize
e += struct.pack("<H", 0)                        # e_phnum
e += struct.pack("<H", 40)                       # e_shentsize
e += struct.pack("<H", 3)                        # e_shnum
e += struct.pack("<H", 2)                        # e_shstrndx
assert len(e) == EHSIZE, len(e)

def sh(name, typ, flags, addr, off, size, link=0, info=0, align=4, ent=0):
    return struct.pack("<10I", name, typ, flags, addr, off, size, link, info, align, ent)

sh0 = sh(0,0,0,0,0,0,align=0)
sh_text = sh(name_text, 1, 0x6, vaddr, text_off, len(code))          # PROGBITS ALLOC|EXEC
sh_sst  = sh(name_sst, 3, 0, 0, sst_off, len(shstr), align=1)        # STRTAB

out = e + code + shstr + b"\x00"*pad + sh0 + sh_text + sh_sst
open(outf, "wb").write(out)
print("wrote %s: %d bytes, .text @0x%08x size 0x%x" % (outf, len(out), vaddr, len(code)))
