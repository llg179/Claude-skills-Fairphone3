
    // entry: r0 = wait-return value, r16 = ctx (PRESERVE r16). scratch r3,r4,r5.
    { r5 = r0 }                                             // save wait-return before clobbering r0
    { r3 = ##0xf090fcd4 }
    { r3 = memw(r3+#0) }                                    // SMEM base ptr (ADSP side)
    { p0 = cmp.eq(r3,#0x0); if (p0.new) jump:nt .Lrep }     // null -> just replicate + return
    { r3 = add(r3,#0x640) }
    { r4 = ##0x31545346 }                                   // 'FST1'
    { memw(r3+#0x00) = r4 }
    { memw(r3+#0x04) = r5 }                                 // wait-return (r0 at entry)
    { r4 = memw(r16+#0xe54) }
    { memw(r3+#0x08) = r4 }
    { r4 = memw(r16+#0xe0c) }
    { memw(r3+#0x0c) = r4 }
    { r4 = memw(r16+#0xe08) }
    { memw(r3+#0x10) = r4 }
    { r4 = memw(r16+#0xeb0) }
    { memw(r3+#0x14) = r4 }
    { r4 = memw(r16+#0xeb4) }
    { memw(r3+#0x18) = r4 }
    { r4 = memw(r16+#0x5c) }
    { memw(r3+#0x1c) = r4 }
    { r4 = memw(r3+#0x20) }                                 // reached-count++
    { r4 = add(r4,#0x1) }
    { memw(r3+#0x20) = r4 }
.Lrep:
    { r0 = memw(r16+#0xe54) }                               // replicate spliced stock instruction
    { r5 = ##0xf04d15c0 }
    { jumpr r5 }
