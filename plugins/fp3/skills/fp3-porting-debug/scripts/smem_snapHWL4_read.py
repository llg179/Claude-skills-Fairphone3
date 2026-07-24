#!/usr/bin/env python3
# snapHWL4 reader: fixed-VA HalHwIo CGC-enable leaf trace (magic 'HWL4', fresh tag).
# Reads PA 0x86302ab0 (= stash VA 0xe1302ab0). SAFE: single bounded mmap of SMEM only.
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; HDR=0x2ab0
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA); buf=m.read(WIN); m.close()
magic=buf[HDR:HDR+4]
print("magic :", magic, "->", "HWL4 OK" if magic==b"HWL4" else "NOT HWL4 (absent/stale — leaf didn't run or wrong tag)")
if magic!=b"HWL4": raise SystemExit
tot,pmnz=struct.unpack_from("<2I",buf,HDR+4)
print(f"total leaf invocations (any clock)    = {tot}")
print(f"pollmask!=0 (lock-bearing) invocations = {pmnz}")
if pmnz:
    h,ba,off,val,pm,d10=struct.unpack_from("<6I",buf,HDR+0x0c)
    print("last lock-bearing clock enabled through the leaf:")
    print(f"  handle   = {h:#010x}")
    print(f"  base     = {ba:#010x}   (runtime-mapped HWIO base — the UT-vs-pmOS differential)")
    print(f"  offset   = {off:#010x}  (memw 0xf0914258)  -> reg = base+offset = {(ba+off)&0xffffffff:#010x}")
    print(f"  value    = {val:#010x}  (enable bits OR'd in)")
    print(f"  pollmask = {pm:#010x}  (lock/CGC-status bits the leaf spins on)")
    print(f"  desc+0x10= {d10:#010x}")
