#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-or-later
# FUTTASD a MŰKÖDŐ downstream rendszeren (Ubuntu Touch VAGY stock Android),
# rootként (UT: `sudo`; Android: `adb shell su`). A kimenetet küldd vissza.
OUT=/tmp/fp3-slim-trace.txt
{
echo "===== UNAME ====="; uname -a
echo "===== DMESG: slim/ngd/adsp/qmi/q6/avs/bam/capability ====="
dmesg | grep -iE "slim|ngd|adsp|qmi|q6|avs|bam|capability|master|laddr|framer|pd_?up|servreg|sysmon" 
echo "===== CLK SUMMARY (engedélyezett órajelek; ez a legfontosabb) ====="
cat /sys/kernel/debug/clk/clk_summary 2>/dev/null
echo "===== REGULATOR SUMMARY ====="
cat /sys/kernel/debug/regulator/regulator_summary 2>/dev/null
echo "===== SLIMBUS sysfs ====="
ls -l /sys/bus/slimbus/devices/ 2>/dev/null
} > "$OUT" 2>&1
echo "KESZ -> $OUT  (kuldd vissza ezt a fajlt)"
