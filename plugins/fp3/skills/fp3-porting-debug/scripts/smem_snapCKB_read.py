#!/usr/bin/env python3
# snapCKB reader: framer-clock (0x12014) RCGR register block. SAFE bounded SMEM mmap.
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; HDR=0x2ab0
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA); buf=m.read(WIN); m.close()
ckb=buf[HDR:HDR+4]
print("CKB1 magic:", ckb, "->", "HIT (framer enable-method ran)" if ckb==b"CKB1" else "MISS (framer enable not run / filter miss)")
if ckb==b"CKB1":
    h,base,idx,cmd,cfg,M,N,D,r14,st=struct.unpack_from("<10I",buf,HDR+0x04)
    print(f"  handle              = {h:#010x}   handle+0x08(state)={st:#010x}  idx={idx}")
    print(f"  ★ RCGR BASE mem(h+0) = {base:#010x}")
    print(f"    CMD_RCGR (+0x00)   = {cmd:#010x}   (bit0=UPDATE, bit1=ROOT_OFF)")
    print(f"    CFG_RCGR (+0x04)   = {cfg:#010x}   (bits[10:8]=src-sel, [4:0]=div)")
    print(f"    M        (+0x08)   = {M:#010x}")
    print(f"    N        (+0x0c)   = {N:#010x}")
    print(f"    D        (+0x10)   = {D:#010x}")
    print(f"    +0x14              = {r14:#010x}")
