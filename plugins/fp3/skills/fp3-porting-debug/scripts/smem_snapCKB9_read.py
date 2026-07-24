#!/usr/bin/env python3
# snapCKB9 reader: framer-clock RCGR RATE/SOURCE. Decodes CFG src-mux + divider + M/N/D.
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; HDR=0x2ab0
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA); buf=m.read(WIN); m.close()
mg=buf[HDR:HDR+4]
print("CB9 magic:", mg, "->", "HIT" if mg==b"CB9 " else "MISS")
if mg==b"CB9 ":
    cmd,cfg,M,N,D,cbcr14,cbcr18,caller=struct.unpack_from("<8I",buf,HDR+0x04)
    src=(cfg>>8)&0x7; div=cfg&0x1f; mnd_mode=(cfg>>12)&0x3
    # RCGR div field encodes (2*divider-1); actual pre-div = (div+1)/2
    predi=(div+1)/2
    print(f"  RCGR base 0xee012000  caller={caller:#010x}")
    print(f"  CMD (0xee012000) = {cmd:#010x}  (UPDATE bit0={cmd&1}, ROOT_OFF bit31={(cmd>>31)&1})")
    print(f"  CFG (0xee012004) = {cfg:#010x}")
    print(f"      src_sel[10:8] = {src}   div[4:0] = {div} (pre-div = {predi})   mode[13:12] = {mnd_mode} (MND={'on' if mnd_mode else 'off'})")
    print(f"  M   (0xee012008) = {M:#010x} ({M})")
    print(f"  N   (0xee01200c) = {N:#010x} ({N})   (dual-edge N = ~N+M form)")
    print(f"  D   (0xee012010) = {D:#010x} ({D})")
    print(f"  CBCR14 (0xee012014) = {cbcr14:#010x}  (EN={cbcr14&1}, CLK_OFF={(cbcr14>>31)&1})")
    print(f"  CBCR18 (0xee012018) = {cbcr18:#010x}  (EN={cbcr18&1}, CLK_OFF={(cbcr18>>31)&1})")
