#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import mmap, os, struct, sys, hashlib
BASE=0x86300000; SIZE=0x100000
fd=os.open("/dev/mem", os.O_RDONLY)
try:
    m=mmap.mmap(fd, SIZE, mmap.MAP_SHARED, mmap.PROT_READ, offset=BASE)
except Exception as e:
    print("MMAP FAIL:", e); sys.exit(1)
data=m[:]
# --- partition table at end? (qcom_smem ptable magic "$PRt" reversed etc) ---
ptable_off=SIZE-0x1000
magic=data[ptable_off:ptable_off+4]
print("=== ptable magic @end:", magic.hex(), "===")
# --- legacy global header ---
# proc_comm[4]=64B, version[32]=128B, initialized/free_offset/available/reserved=16B, toc@208
toc_off=64+128+16
items={}
ITEMS=512
for i in range(ITEMS):
    o=toc_off+i*16
    allocated,offset,size,aux=struct.unpack_from("<IIII", data, o)
    if allocated and size and offset+size<=SIZE:
        blob=data[offset:offset+min(size,0x40)]
        items[i]=(size, hashlib.sha1(data[offset:offset+size]).hexdigest()[:12], blob[:24].hex())
print("=== LEGACY TOC allocated items:", len(items), "===")
for i in sorted(items):
    sz,h,head=items[i]
    print(f"ID={i:4d} size={sz:7d} sha={h} head={head}")
open("/tmp/smem_raw.bin","wb").write(data)
print("raw saved /tmp/smem_raw.bin")
