# SPDX-License-Identifier: GPL-2.0-or-later
import mmap,struct
f=open("/dev/mem","rb")
BASE=0x86300000
m=mmap.mmap(f.fileno(),0x1000,mmap.MAP_SHARED,mmap.PROT_READ,offset=BASE)
print("=== SMEM header @0x%08x ==="%BASE,flush=True)
for off in range(0,0x100,16):
    w=struct.unpack("<4I", m[off:off+16])
    print("+0x%03x: %08x %08x %08x %08x"%(off,w[0],w[1],w[2],w[3]),flush=True)
init,free,avail,resv=struct.unpack("<4I",m[0xC0:0xD0])
ver=struct.unpack("<I",m[0x40+7*4:0x40+7*4+4])[0]
print("initialized=0x%x free_offset=0x%x available=0x%x version[7]=0x%x"%(init,free,avail,ver),flush=True)
# first few TOC entries (global heap) at 0xD0: allocated,offset,size,aux_base per item id
print("=== first TOC entries (id: alloc off size aux) ===",flush=True)
for i in range(0,8):
    a,o,s,ax=struct.unpack("<4I",m[0xD0+i*16:0xD0+i*16+16])
    print("id%02d: alloc=%x off=0x%x size=0x%x aux=0x%x"%(i,a,o,s,ax),flush=True)
m.close()
print("OK-SMEM-READ-DID-NOT-WEDGE",flush=True)
