# SPDX-License-Identifier: GPL-2.0-or-later
import mmap,struct,time
f=open("/dev/mem","r+b")
def rd(a):
    pa=a&~0xfff; m=mmap.mmap(f.fileno(),4096,mmap.MAP_SHARED,mmap.PROT_READ|mmap.PROT_WRITE,offset=pa)
    v=struct.unpack("<I",m[a-pa:a-pa+4])[0]; m.close(); return v
def wr(a,v):
    pa=a&~0xfff; m=mmap.mmap(f.fileno(),4096,mmap.MAP_SHARED,mmap.PROT_READ|mmap.PROT_WRITE,offset=pa)
    m[a-pa:a-pa+4]=struct.pack("<I",v); m.close()
print("BEFORE: FRM_STAT=0x%08X FRM_CLKCTL=0x%08X NGD_CFG=0x%08X NGD_STAT=0x%08X"%(rd(0x0c140404),rd(0x0c140420),rd(0x0c141000),rd(0x0c141004)),flush=True)
print("writing FRM_WAKEUP(0x41c)=1 ...",flush=True); wr(0x0c14041c,1); time.sleep(0.2)
print("re-writing FRM_CFG(0x400)=0x000D0C83 (re-assert active) ...",flush=True); wr(0x0c140400,0x000D0C83); time.sleep(0.3)
print("AFTER:  FRM_STAT=0x%08X FRM_CLKCTL=0x%08X FRM_WAKEUP=0x%08X NGD_CFG=0x%08X NGD_STAT=0x%08X"%(rd(0x0c140404),rd(0x0c140420),rd(0x0c14041c),rd(0x0c141000),rd(0x0c141004)),flush=True)
