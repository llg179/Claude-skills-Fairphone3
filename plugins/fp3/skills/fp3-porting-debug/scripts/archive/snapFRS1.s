
    // entry: r0=ctx (incoming). scratch r3,r4,r5; preserve r0.
    { r3 = ##0xf090fcd4 }
    { r3 = memw(r3+#0) }
    { p0 = cmp.eq(r3,#0x0); if (p0.new) jump:nt .Lset }
    { r3 = add(r3,#0x640) }
    { r4 = ##0x31535246 }                 // 'FRS1'
    { memw(r3+#0x00) = r4 }
    { memw(r3+#0x04) = r0 }
    { r4 = memw(r0+#0x78) }
    { memw(r3+#0x08) = r4 }
    { r4 = memw(r0+#0xdfc) }
    { memw(r3+#0x0c) = r4 }
    { r4 = memw(r0+#0xe00) }
    { memw(r3+#0x10) = r4 }
    { r5 = memw(r0+#0x5c) }               // framer MMIO base
    { memw(r3+#0x14) = r5 }
    { p0 = cmp.eq(r5,#0x0); if (p0.new) jump:nt .Lset }   // null-guard the MMIO reads
    { r4 = memw(r5+#0x600) }
    { memw(r3+#0x18) = r4 }
    { r4 = memw(r5+#0x604) }
    { memw(r3+#0x1c) = r4 }
    { r4 = memw(r5+#0x608) }
    { memw(r3+#0x20) = r4 }
    { r4 = memw(r5+#0x60c) }
    { memw(r3+#0x24) = r4 }
    { r4 = ##0x0000f00d }
    { memw(r3+#0x28) = r4 }
.Lset:
    { r16 = r0 }
    { r5 = ##0xf04c3544 }
    { jumpr r5 }
