
    // entry: r0=ctx (incoming arg), frame allocated. scratch r3,r4,r5; preserve r0.
    { r3 = ##0xf090fcd4 }
    { r3 = memw(r3+#0) }
    { p0 = cmp.eq(r3,#0x0); if (p0.new) jump:nt .Lset }
    { r3 = add(r3,#0x640) }
    { r4 = ##0x32444d46 }                 // 'FMD2'
    { memw(r3+#0x00) = r4 }
    { memw(r3+#0x04) = r0 }
    { r4 = memw(r0+#0x78) }
    { memw(r3+#0x08) = r4 }
    { r4 = memw(r0+#0xe08) }
    { memw(r3+#0x0c) = r4 }
    { r4 = memw(r0+#0xe58) }
    { memw(r3+#0x10) = r4 }
    { r4 = memw(r0+#0xdb4) }
    { memw(r3+#0x14) = r4 }
    { r4 = memw(r0+#0x6c) }
    { memw(r3+#0x18) = r4 }
    { memw(r3+#0x1c) = r31 }
    { r4 = memw(r3+#0x20) }
    { r4 = add(r4,#1) }
    { memw(r3+#0x20) = r4 }
.Lset:
    { r16 = r0 }
    { r5 = ##0xf04c36ec }
    { jumpr r5 }
