#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, struct

FDT_MAGIC = 0xd00dfeed
FDT_BEGIN_NODE=1; FDT_END_NODE=2; FDT_PROP=3; FDT_NOP=4; FDT_END=9

def u32(b,o): return struct.unpack_from(">I",b,o)[0]

def find_fdts(data):
    out=[]; i=0
    while True:
        j=data.find(b"\xd0\x0d\xfe\xed", i)
        if j<0: break
        if j+40<=len(data):
            total=u32(data,j+4)
            ver=u32(data,j+20)
            if 0x30<total<6_000_000 and 16<=ver<=17 and j+total<=len(data):
                out.append((j,total))
                i=j+total; continue
        i=j+4
    return out

def parse(blob):
    magic=u32(blob,0); total=u32(blob,4)
    off_struct=u32(blob,8); off_strings=u32(blob,12)
    nodes=[]  # (path, {prop:bytes})
    stack=[]
    o=off_struct
    while o<total:
        tag=u32(blob,o); o+=4
        if tag==FDT_BEGIN_NODE:
            end=blob.index(b"\x00",o)
            name=blob[o:end].decode("latin1")
            o=end+1; o=(o+3)&~3
            stack.append(name)
            nodes.append(("/".join(stack), {}))
        elif tag==FDT_END_NODE:
            if stack: stack.pop()
        elif tag==FDT_PROP:
            plen=u32(blob,o); noff=u32(blob,o+4); o+=8
            nend=blob.index(b"\x00",off_strings+noff)
            pname=blob[off_strings+noff:nend].decode("latin1")
            val=blob[o:o+plen]; o+=plen; o=(o+3)&~3
            if nodes: nodes[-1][1][pname]=val
        elif tag==FDT_NOP: pass
        elif tag==FDT_END: break
        else: break
    return nodes

def show(val):
    # try string list
    if val and val[-1]==0 and all(32<=c<127 or c==0 for c in val):
        parts=[p.decode() for p in val.split(b"\x00") if p]
        return "str:"+",".join(parts)
    if len(val)%4==0 and len(val)>0:
        return "u32:"+",".join("0x%x"%u32(val,k) for k in range(0,len(val),4))
    return "raw:"+val.hex()

for path in sys.argv[1:]:
    data=open(path,"rb").read()
    fdts=find_fdts(data)
    print(f"=== {path}: {len(fdts)} FDT blobs ===")
    for (off,total) in fdts:
        blob=data[off:off+total]
        try: nodes=parse(blob)
        except Exception as e:
            print(f"  @{off:#x} parse err {e}"); continue
        hits=[n for n in nodes if any(k in n[0].lower() for k in ("slim","bam"))]
        if not hits: continue
        # model
        model=""
        for p,props in nodes:
            if p.count("/")<=1 and "model" in props:
                model=show(props["model"]); break
        print(f"  @{off:#x} size={total} {model}")
        for p,props in hits:
            if p.count("/")>4: continue
            interesting={k:v for k,v in props.items() if k in
              ("compatible","reg","qcom,ee","qcom,bam-pipes","qcom,ngd-pipes","dmas","dma-names",
               "qcom,apps-ch-pipes","qcom,ea-pc","interrupts","cell-index","qcom,slim-ngd","status",
               "qcom,rxreg-access","label","qcom,slimbus-clk-gear","qcom,min-clk-gear")}
            print(f"    {p}")
            for k,v in interesting.items():
                print(f"       {k} = {show(v)}")
