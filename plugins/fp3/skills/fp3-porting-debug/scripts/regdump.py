# SPDX-License-Identifier: MIT
import mmap,os,struct
def dump(base,offs,label):
    fd=os.open("/dev/mem",os.O_RDONLY|os.O_SYNC)
    pg=0x1000; pa=base & ~(pg-1); d=base-pa
    m=mmap.mmap(fd,pg,mmap.MAP_SHARED,mmap.PROT_READ,offset=pa)
    print("==",label,hex(base),"==")
    for o in offs:
        try: print("  +0x%04x = 0x%08x"%(o,struct.unpack("<I",m[d+o:d+o+4])[0]))
        except Exception as e: print("  +0x%04x err %s"%(o,e))
    m.close(); os.close(fd)
dump(0xc140000,[0x0,0x4,0x800,0x804,0x810,0x814,0x818,0x820,0x1000,0x1004,0x1010,0x1014,0x1018,0x1020,0x1024],"NGD")
