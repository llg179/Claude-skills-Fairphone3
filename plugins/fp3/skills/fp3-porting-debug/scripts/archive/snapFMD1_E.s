
    { r3 = ##0xf090fcd4 }
    { r3 = memw(r3+#0) }
    { p0 = cmp.eq(r3,#0x0); if (p0.new) jump:nt .Lx }
    { r3 = add(r3,#0x640) }
    { r4 = ##0x45444d46 }
    { memw(r3+#64) = r4 }
    { memw(r3+#68) = r16 }
    { r4 = memw(r16+#0x78) }
    { memw(r3+#72) = r4 }
    { r4 = memw(r16+#0xe08) }
    { memw(r3+#76) = r4 }
    { r4 = memw(r16+#0xe58) }
    { memw(r3+#80) = r4 }
    { r4 = memw(r16+#0xdb4) }
    { memw(r3+#84) = r4 }
    { r4 = memw(r16+#0x6c) }
    { memw(r3+#88) = r4 }
    { memw(r3+#92) = r31 }
.Lx:
    { r5 = ##0xf04c37ac }
    { jumpr r5 }
