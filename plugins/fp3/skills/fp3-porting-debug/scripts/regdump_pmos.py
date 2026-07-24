#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Read NGD + SLIMbus-BAM (v1.7.0) registers via /dev/mem to decide WHY mainline gets
# zero RX / TX-timeout: is the RX BAM pipe connected & is the framer moving pointers?
import mmap, os, struct
PG = 0x1000
def rd(pa):
    fd = os.open("/dev/mem", os.O_RDONLY | os.O_SYNC)
    base = pa & ~(PG - 1); off = pa - base
    try:
        m = mmap.mmap(fd, PG, mmap.MAP_SHARED, mmap.PROT_READ, offset=base)
        v = struct.unpack("<I", m[off:off + 4])[0]; m.close()
    except Exception as e:
        v = None; print("   (map err @%#x: %s)" % (pa, e))
    os.close(fd); return v
def show(label, pa):
    v = rd(pa); print("  %-22s @%#010x = %s" % (label, pa, ("0x%08x" % v) if v is not None else "ERR"))

NGD = 0xc141000   # ctrl 0xc140000 + id1*0x1000
print("== NGD (0xc141000) ==")
show("NGD_CFG",        NGD + 0x0)
show("NGD_STATUS",     NGD + 0x4)   # LADDR=BIT1; was 0x40c at fail
show("NGD_RX_MSGQ_CFG",NGD + 0x8)
show("NGD_INT_EN",     NGD + 0x10)
show("NGD_INT_STAT",   NGD + 0x14)
show("NGD_VERSION@ctrl",0xc140000)

BAM = 0xc104000   # qcom,bam-v1.7.0
print("== BAM core (0xc104000, v1.7.0) ==")
show("BAM_CTRL",     BAM + 0x0)
show("BAM_REVISION", BAM + 0x1000)
show("BAM_NUM_PIPES",BAM + 0x1008)
show("BAM_IRQ_STTS", BAM + 0x14)
for name, pipe in (("RX", 3), ("TX", 4)):
    pbase = 0x13000 + pipe * 0x1000
    print("== BAM pipe %d (%s) ==" % (pipe, name))
    show("P_CTRL",          BAM + pbase)            # bit1=EN, dir bit
    show("P_SW_OFSTS",      BAM + 0x13800 + pipe*0x1000)  # SW read ptr
    show("P_EVNT_REG",      BAM + 0x13818 + pipe*0x1000)  # HW write ptr (advances if data arrives)
    show("P_DESC_FIFO_ADDR",BAM + 0x1381C + pipe*0x1000)  # AP desc-fifo phys (0 => not connected)
    show("P_FIFO_SIZES",    BAM + 0x13820 + pipe*0x1000)
