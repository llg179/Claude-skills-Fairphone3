#!/usr/bin/env python3
# Correct per-segment ELF32(Hexagon) phdr mapper + xref/string tool for adsp mbn.
import struct, sys

FN = "adsp-orig-signed.mbn"
data = open(FN, "rb").read()

# ELF32 header
assert data[:4] == b"\x7fELF", "not ELF"
e_phoff  = struct.unpack_from("<I", data, 0x1c)[0]
e_phentsize = struct.unpack_from("<H", data, 0x2a)[0]
e_phnum  = struct.unpack_from("<H", data, 0x2c)[0]

SEGS = []  # (off, vaddr, filesz, memsz, flags)
for i in range(e_phnum):
    base = e_phoff + i*e_phentsize
    p_type, p_off, p_vaddr, p_paddr, p_filesz, p_memsz, p_flags, p_align = \
        struct.unpack_from("<8I", data, base)
    if p_type == 1 and p_filesz > 0:  # PT_LOAD, file-backed
        SEGS.append((p_off, p_vaddr, p_filesz, p_memsz, p_flags))

def o2v(off):
    for (o, v, fs, ms, fl) in SEGS:
        if o <= off < o + fs:
            return v + (off - o)
    return None

def v2o(vaddr):
    for (o, v, fs, ms, fl) in SEGS:
        if v <= vaddr < v + fs:
            return o + (vaddr - v)
    return None

def seg_of_v(vaddr):
    for idx,(o, v, fs, ms, fl) in enumerate(SEGS):
        if v <= vaddr < v + ms:  # by memsz (covers bss)
            return idx,(o,v,fs,ms,fl)
    return None,None

def find_le32(val):
    """all file offsets where the 4-byte LE of val appears"""
    pat = struct.pack("<I", val & 0xffffffff)
    out = []; i = data.find(pat)
    while i != -1:
        out.append(i); i = data.find(pat, i+1)
    return out

def strings_at(vaddr, maxlen=64):
    o = v2o(vaddr)
    if o is None: return None
    end = data.find(b"\x00", o)
    s = data[o:end if end!=-1 else o+maxlen]
    try: return s.decode("ascii")
    except: return repr(s[:maxlen])

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "segs"
    if cmd == "segs":
        print("idx  fileoff    vaddr       filesz    memsz     flg  delta(v-o)")
        for i,(o,v,fs,ms,fl) in enumerate(SEGS):
            print("%2d  0x%08x 0x%08x 0x%08x 0x%08x  %d   0x%08x"%(i,o,v,fs,ms,fl,(v-o)&0xffffffff))
    elif cmd == "xref":
        val = int(sys.argv[2], 0)
        print("=== file occurrences of LE32 0x%08x (= '%s') ==="%(val, strings_at(val) or "?"))
        for off in find_le32(val):
            vv = o2v(off)
            si,_ = seg_of_v(vv) if vv is not None else (None,None)
            print("  fileoff=0x%08x  vaddr=%s  seg=%s"%(off, ("0x%08x"%vv) if vv is not None else "None", si))
    elif cmd == "str":
        v = int(sys.argv[2], 0)
        print("vaddr 0x%08x -> fileoff %s -> '%s'"%(v, ("0x%x"%v2o(v)) if v2o(v) is not None else None, strings_at(v)))
    elif cmd == "v2o":
        v=int(sys.argv[2],0); print("0x%x"%v2o(v) if v2o(v) is not None else "None")
    elif cmd == "o2v":
        o=int(sys.argv[2],0); print("0x%x"%o2v(o) if o2v(o) is not None else "None")
