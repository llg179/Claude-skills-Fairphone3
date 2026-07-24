
    { r3 = ##0xf090fcd4 }
    { r3 = memw(r3+#0) }
    { p0 = cmp.eq(r3,#0x0); if (p0.new) jump:nt .Lx }
    { r3 = add(r3,#0x640) }
    { r4 = ##0x41444d46 }
    { memw(r3+#0) = r4 }
    { memw(r3+#4) = r16 }
    { r4 = memw(r16+#0x78) }
    { memw(r3+#8) = r4 }
    { r4 = memw(r16+#0xe08) }
    { memw(r3+#12) = r4 }
    { r4 = memw(r16+#0xe58) }
    { memw(r3+#16) = r4 }
    { r4 = memw(r16+#0xdb4) }
    { memw(r3+#20) = r4 }
    { r4 = memw(r16+#0x6c) }
    { memw(r3+#24) = r4 }
    { memw(r3+#28) = r31 }
.Lx:
    { r5 = ##0xf04c3808 }
    { jumpr r5 }
