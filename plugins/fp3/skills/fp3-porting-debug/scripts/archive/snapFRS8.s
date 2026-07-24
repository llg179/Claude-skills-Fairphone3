
    // entry: r0 = framer ctx (PRESERVE for replication). scratch r3,r4,r5,r6,r7,r8.
    { r3 = ##0xf090fcd4 }
    { r3 = memw(r3+#0) }
    { p0 = cmp.eq(r3,#0x0); if (p0.new) jump:nt .Lrep }     // SMEM ptr null -> can't stash, just return
    { r3 = add(r3,#0x640) }                                 // stash base
    { r4 = ##0x38535246 }                                   // 'FRS8'
    { memw(r3+#0x00) = r4 }
    { r6 = #0 }                                             // pair count
    { p0 = cmp.eq(r0,#0x0); if (p0.new) jump:nt .Ldone }    // ctx null -> store count=0
    { r7 = #0 }                                             // ctx offset iterator
.Lloop:
    { r5 = memw(r0+r7<<#0) }                                // val = *(ctx + off)  [DDR read, not MMIO]
    { r4 = and(r5,##0xff000000) }
    { p0 = cmp.eq(r4,##0xee000000) }                               // A: LPASS MMIO pointer (0xee..)
    { p1 = cmp.eq(r4,##0xf0000000) }                               // B: ADSP image/data pointer (0xf0..)
    { p0 = or(p0,p1) }
    { if (!p0) jump:nt .Lnext }                                    // neither -> skip
    { p1 = cmp.gtu(r6,#0x7); if (p1.new) jump:nt .Lnext }   // already have MAX_PAIRS=8 -> skip store
    { r4 = asl(r6,#0x3) }                                   // pair byte-offset = count*8
    { r4 = add(r4,#0x08) }                                  // + 8-byte header (magic+count)
    { r8 = add(r3,r4) }
    { memw(r8+#0x00) = r7 }                                 // store ctx offset
    { memw(r8+#0x04) = r5 }                                 // store LPASS pointer value
    { r6 = add(r6,#0x1) }
.Lnext:
    { r7 = add(r7,#0x4) }
    { p0 = cmp.gtu(r7,##0xdfc); if (!p0.new) jump:nt .Lloop }   // loop while off <= SCAN_MAX
.Ldone:
    { memw(r3+#0x04) = r6 }                                 // count
.Lrep:
    { r16 = r0 }                                            // replicate spliced word
    { r5 = ##0xf04c36ec }
    { jumpr r5 }
