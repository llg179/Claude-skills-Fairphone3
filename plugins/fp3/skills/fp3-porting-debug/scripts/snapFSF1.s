
    { r4 = #0x0 }
    { memw(r16+#0xe54) = r4 }          // force success: no error object
    { r0 = memw(r16+#0xe54) }          // replicate stock (now loads 0 -> r0=0)
    { r5 = ##0xf04d15c0 }
    { jumpr r5 }
