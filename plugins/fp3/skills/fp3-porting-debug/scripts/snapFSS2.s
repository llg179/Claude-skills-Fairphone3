
    // entry: r16 = ctx (PRESERVE). scratch r2,r3,r4,r5,r6.
    { r3 = ##0xf090fcd4 }
    { r3 = memw(r3+#0) }                                    // SMEM base ptr (ADSP side)
    { p0 = cmp.eq(r3,#0x0); if (p0.new) jump:nt .Lrep }     // null -> replicate + return
    { r3 = add(r3,#0x640) }
    { r6 = memw(r3+#0x20) }                                 // hit-count
    { r5 = add(r6,#0x1) }
    { memw(r3+#0x20) = r5 }                                 // count++
    { p0 = cmp.eq(r6,#0x0); if (!p0.new) jump:nt .Lrep }    // not first hit -> skip stash (bounds SMEM writes)
    { r4 = ##0x32535346 }                                   // 'FSS2'
    { memw(r3+#0x00) = r4 }
    { r2 = memw(r16+#0x5c) }                                // framer base (0xee140000)
    { memw(r3+#0x04) = r2 }
    { r4 = memw(r2+#0x610) }                                // +0x610 right after FN_B store (expect 7 if latched)
    { memw(r3+#0x08) = r4 }
    { r4 = memw(r2+#0x600) }                                // enable
    { memw(r3+#0x0c) = r4 }
    { r4 = memw(r2+#0x604) }                                // FS/SFS/MS
    { memw(r3+#0x10) = r4 }
    { r4 = memw(r2+#0x404) }                                // FRM_STAT
    { memw(r3+#0x14) = r4 }
    { r4 = memw(r2+#0x804) }                                // running
    { memw(r3+#0x18) = r4 }
    { r4 = memw(r16+#0xec4) }                               // ctx+0xec4 (FN_B gate field)
    { memw(r3+#0x1c) = r4 }
.Lrep:
    { r0 = memw(r16+#0xec4) }                               // replicate spliced stock instruction
    { r5 = ##0xf04ca3dc }
    { jumpr r5 }
