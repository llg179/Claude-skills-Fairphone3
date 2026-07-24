#!/bin/bash
# disfn.sh <vaddr> [len] : disasm a function from the full-seg elf, highlight MMIO/absolute stores
VA=$1; LEN=${2:-0xc0}
END=$(printf '0x%x' $(( VA + LEN )))
# seg2 covers 0xf015f000..; seg3 (0xf07fc000..) and seg1 (0xf0102000..) may hold apply_fn.
# Pick the right seg elf by address.
python3 - "$VA" <<'PY'
import sys
va=int(sys.argv[1],0)
# seg map: (foff, vaddr, filesz)
segs=[(0x5000,0xf0102000,0x5c35c),(0x62000,0xf015f000,0x69c910),(0x6ff000,0xf07fc000,0xb5ca6),(0x7b6000,0xf0cae000,0x67904)]
for foff,vaddr,fs in segs:
    if vaddr<=va<vaddr+fs:
        print(f"SEG foff={foff:#x} vaddr={vaddr:#x} filesz={fs:#x}"); break
else:
    print("VA not in a file-backed code seg")
PY
llvm-objdump -d --triple=hexagon --start-address=$VA --stop-address=$END seg2.elf 2>/dev/null | sed -n '5,200p' | \
  grep -E 'memw\(##|memd\(##|= ##0x[0-9a-f]|call 0x|callr|jump 0x|immext|dealloc|jumpr' 
