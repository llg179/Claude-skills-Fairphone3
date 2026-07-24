#!/usr/bin/env python3
# Wrap a raw code blob into a minimal ELF32-hexagon with one .text section at a given VA,
# so llvm-objdump -d gives real addresses + packet grouping. Usage: make_disasm_elf.py in.bin baseVA out.elf
import sys, struct
inp, baseVA, out = sys.argv[1], int(sys.argv[2],0), sys.argv[3]
code=open(inp,"rb").read()
EM_HEXAGON=164
# layout: [ehdr 52][code][shstrtab][shdrs]
ehsz=52; shentsz=40
code_off=ehsz
shstr=b"\x00.text\x00.shstrtab\x00"
shstr_off=code_off+len(code)
sht_off=shstr_off+len(shstr)
# section headers: null, .text, .shstrtab
def shdr(name,typ,flags,addr,off,size,link=0,info=0,align=4,entsz=0):
    return struct.pack("<10I",name,typ,flags,addr,off,size,link,info,align,entsz)
sh_null=shdr(0,0,0,0,0,0)
sh_text=shdr(1,1,0x6,baseVA,code_off,len(code),align=4)          # PROGBITS, ALLOC|EXECINSTR
sh_str =shdr(7,3,0,0,shstr_off,len(shstr),align=1)               # STRTAB
shnum=3; shstrndx=2
ehdr=struct.pack("<16sHHIIIIIHHHHHH",
    b"\x7fELF\x01\x01\x01"+b"\x00"*9, 2, EM_HEXAGON, 1,
    baseVA, 0, sht_off, 0, ehsz, 0, 0, shentsz, shnum, shstrndx)
open(out,"wb").write(ehdr+code+shstr+sh_null+sh_text+sh_str)
print(f"wrote {out}: .text @ {baseVA:#x} size {len(code):#x}")
