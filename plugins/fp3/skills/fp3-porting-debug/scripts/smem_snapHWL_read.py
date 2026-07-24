#!/usr/bin/env python3
# HWL0 reader: the HalHwIo/PLL-lock LEAF ring. SAFE single mmap of 0x86300000.
# Ring A = last 16 of ALL CGC-enable-leaf invocations; Ring B = last 4 with pollmask!=0.
# Entry (8 words): handle, base(runtime HWIO), offset(memw 0xf0914258), value/mask,
#                  pollmask(lock mask), desc+0x10, seq, regaddr(computed).
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; HDR=0x2ab0
RA=HDR+0x40; RB=HDR+0x240
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA)
    buf=m.read(WIN); m.close()
magic=buf[HDR:HDR+4]
ok = magic==b"HWL0"
print("magic     :", magic, "->", "HWL0 OK" if ok else "NOT PRESENT (stale/absent)")
if not ok: raise SystemExit
totA=struct.unpack_from("<I",buf,HDR+4)[0]
totB=struct.unpack_from("<I",buf,HDR+8)[0]
print(f"totalA (all invocations)      = {totA}")
print(f"totalB (pollmask!=0 clocks)   = {totB}")
def dump(name,off,cap,tot):
    print(f"\n=== {name}  (cap {cap}, total {tot}) ===")
    n=min(tot,cap)
    # entries in ring order; seq tells real order
    rows=[]
    for i in range(cap):
        e=off+i*32
        h,ba,offs,val,pm,st,seq,ra=struct.unpack_from("<8I",buf,e)
        rows.append((seq,h,ba,offs,val,pm,st,ra,i))
    rows.sort()
    print(f"  {'seq':>4} {'handle':>10} {'base':>10} {'offset':>8} {'value':>10} {'pollmsk':>10} {'d+0x10':>10} {'regaddr':>10}")
    for seq,h,ba,offs,val,pm,st,ra,i in rows:
        # only show plausibly-written rows: seq < tot (or tot large)
        if tot<=cap and seq>=tot: continue
        print(f"  {seq:>4} {h:#010x} {ba:#010x} {offs:#08x} {val:#010x} {pm:#010x} {st:#010x} {ra:#010x}")
dump("RING A (all clocks)",RA,16,totA)
dump("RING B (lock-bearing, pollmask!=0)",RB,4,totB)
print("\nNote: base = runtime-mapped HWIO base (target differential UT vs pmOS). No cave MMIO read (v2).")
