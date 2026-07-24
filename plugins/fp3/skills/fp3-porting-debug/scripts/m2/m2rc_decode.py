#!/usr/bin/env python3
# m2rc_decode.py <coredump> — decode the m2rc DAL-rc stash (marker 0x5A700029).
# fields: [0]=marker [4]=DAL_rc [8]=handle_ptr [12]=handle+0x2c(after) [16]=count
import sys, struct
d = open(sys.argv[1], "rb").read()
MARKER = 0x5A700029
i = d.find(struct.pack("<I", MARKER))
if i < 0:
    print("marker 0x5A700029 NOT found (%d bytes) -> cave did not fire (gear!=0xA path, or bring-up didn't run)." % len(d))
    sys.exit(1)
m, rc, hp, h2c, cnt = struct.unpack_from("<5I", d, i)
print("marker @0x%x" % i)
print("  DAL_rc (0xf019f134 return) = 0x%08x  (%d)" % (rc, rc))
print("  handle_ptr                 = 0x%08x" % hp)
print("  handle+0x2c (after enable) = 0x%08x  (%d)  [6 = cmd-6 enable dispatched]" % (h2c, h2c))
print("  count                      = %d" % cnt)
print()
if rc == 0 and h2c == 6:
    print("==> ADSP clock-enable SUCCEEDED (rc=0) AND dispatched (0x2c=6).")
    print("    If FRM_STAT is still 0 -> firmware reports success but rclk physically dead")
    print("    -> HW/power BSP precondition (rail_cx / parent-PLL) missing under PAS. [folyt.29]")
elif rc != 0:
    print("==> ADSP clock-enable RETURNED ERROR rc=0x%08x -> the missing resource is named by this rc." % rc)
else:
    print("==> unexpected combo (rc=0x%x, 0x2c=%d) -> inspect." % (rc, h2c))
