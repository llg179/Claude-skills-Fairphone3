# SPDX-License-Identifier: MIT
import mmap,struct,sys
f=open("/dev/mem","rb")
def rd(a):
    pa=a&~0xfff; m=mmap.mmap(f.fileno(),4096,mmap.MAP_SHARED,mmap.PROT_READ,offset=pa); v=struct.unpack("<I",m[a-pa:a-pa+4])[0]; m.close(); return v
print("%-26s FRM_STAT=0x%08X FRM_CLKCTL=0x%08X NGD_CFG=0x%08X NGD_STAT=0x%08X"%(sys.argv[1],rd(0x0c140404),rd(0x0c140420),rd(0x0c141000),rd(0x0c141004)),flush=True)
