
    { r3 = add(r1,r0) }                                     // replicate: r3 = target addr
    { r4 = and(r3,##0xffff0000) }
    { p0 = cmp.eq(r4,##0xee140000); if (!p0.new) jump:nt .Lout }   // framer aperture only
    { r4 = ##0xf090fcd4 }
    { r4 = memw(r4+#0) }
    { p0 = cmp.eq(r4,#0x0); if (p0.new) jump:nt .Lout }
    { r4 = add(r4,#0x680) }                                 // ring base
    { r6 = ##0x46545746 }                                   // 'FWTF'
    { memw(r4+#0x00) = r6 }
    { r5 = memw(r4+#0x04) }                                 // count
    { p0 = cmp.gtu(r5,#0x3f); if (p0.new) jump:nt .Lout }   // cap 64 entries
    { r6 = asl(r5,#0x3) }
    { r6 = add(r6,#0x08) }
    { r7 = add(r4,r6) }
    { memw(r7+#0x00) = r3 }                                 // addr
    { memw(r7+#0x04) = r2 }                                 // value written
    { r5 = add(r5,#0x1) }
    { memw(r4+#0x04) = r5 }
.Lout:
    { r5 = ##0xf04bfe84 }
    { jumpr r5 }
