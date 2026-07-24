
    // entry: r0 = wait-return value, r16 = ctx (PRESERVE r16). scratch r2,r3,r4,r5,r6.
    { r5 = r0 }                                             // save wait-return before clobbering r0
    { r3 = ##0xf090fcd4 }
    { r3 = memw(r3+#0) }                                    // SMEM base ptr (ADSP side)
    { p0 = cmp.eq(r3,#0x0); if (p0.new) jump:nt .Lrep }     // null -> just replicate + return
    { r3 = add(r3,#0x640) }
    { r4 = ##0x31535346 }                                   // 'FSS1'
    { memw(r3+#0x00) = r4 }
    { memw(r3+#0x04) = r5 }                                 // wait-return (r0 at entry)
    { r2 = memw(r16+#0x5c) }                                // framer base (0xee140000)
    { memw(r3+#0x08) = r2 }
    { r4 = memw(r2+#0x204) }
    { memw(r3+#0x0c) = r4 }
    { r4 = memw(r2+#0x404) }                                // FRM_STAT
    { memw(r3+#0x10) = r4 }
    { r4 = memw(r2+#0x430) }
    { memw(r3+#0x14) = r4 }
    { r4 = memw(r2+#0x604) }                                // FS/SFS/MS
    { memw(r3+#0x18) = r4 }
    { r4 = memw(r2+#0x804) }                                // running bit
    { memw(r3+#0x1c) = r4 }
    { r4 = memw(r2+#0x600) }                                // enable (expect 1)
    { memw(r3+#0x20) = r4 }
    { r4 = memw(r2+#0x610) }                                // control (expect 7)
    { memw(r3+#0x24) = r4 }
    { r6 = #0x800 }                                         // short delay to sample a second time
.Ldly:
    { r6 = add(r6,#-0x1); p0 = cmp.gt(r6,#0x1); if (p0.new) jump:nt .Ldly }
    { r4 = memw(r2+#0x604) }                                // FS/SFS/MS re-read
    { memw(r3+#0x28) = r4 }
    { r4 = memw(r2+#0x804) }                                // running bit re-read
    { memw(r3+#0x2c) = r4 }
    { r4 = memw(r3+#0x30) }                                 // reached-count++
    { r4 = add(r4,#0x1) }
    { memw(r3+#0x30) = r4 }
.Lrep:
    { r0 = memw(r16+#0xe54) }                               // replicate spliced stock instruction
    { r5 = ##0xf04d15c0 }
    { jumpr r5 }
