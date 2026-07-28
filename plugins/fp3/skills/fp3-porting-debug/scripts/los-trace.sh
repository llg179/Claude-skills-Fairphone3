#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# DOWNSTREAM (LineageOS A15 eng/userdebug, downstream 4.9 kernel) SLIMbus trace capture.
# Run from HOST while the phone is booted into LineageOS with adb. Captures the WORKING
# SLIMbus framer bring-up to diff against the pmOS (mainline) baseline in /tmp/pmos-baseline.
# usage: los-trace.sh [outdir]

# Config lives in fp3-env.sh; every value there has a documented default.
# Resolve symlinks first: these scripts are commonly installed as symlinks in
# /usr/local/bin, where a bare $0 would look for fp3-env.sh next to the symlink.
_self="$(readlink -f "$0")"
for _d in "$(dirname "$_self")" "$(dirname "$_self")/.." "$(dirname "$_self")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

set -uo pipefail
OUT=${1:-$FP3_PMOS/pmos-backup-20260629/los-trace}
mkdir -p "$OUT"
A(){ adb shell "$@" 2>/dev/null; }

echo "=== adb root (userdebug) ==="
adb root 2>&1 | tail -1; adb wait-for-device
echo "=== meta ==="
A 'uname -a; getprop ro.build.fingerprint; getprop ro.build.version.release' | tee "$OUT/meta.txt"

echo "=== full dmesg ==="; A 'dmesg' > "$OUT/dmesg-full.txt"; wc -l "$OUT/dmesg-full.txt"
echo "=== slim/ngd/qmi/tasha/wcd/avs/adsp/pil/q6/framer/pd grep ==="
grep -iE 'slim|ngd|msm_slim|qmi|tasha|wcd93|avs|adsp|pil |q6afe|q6voice|slimbus|framer|laddr|capability|servreg|pd_up|sysmon|lpass' \
  "$OUT/dmesg-full.txt" | tee "$OUT/dmesg-slim.txt" | tail -80

echo "=== clk_summary (FULL — key diff) ==="
A 'cat /sys/kernel/debug/clk/clk_summary 2>/dev/null || cat /d/clk/clk_summary 2>/dev/null' > "$OUT/clk_summary.txt"; wc -l "$OUT/clk_summary.txt"
echo "--- slim/lpass/audio/slimbus enabled-clock lines ---"
grep -iE 'slim|lpass|audio|mclk|q6|ult|bb_clk|cxo|rco' "$OUT/clk_summary.txt" | grep -ivE ' 0 +0 ' | head -60

echo "=== regulator_summary ==="; A 'cat /sys/kernel/debug/regulator/regulator_summary 2>/dev/null || cat /d/regulator/regulator_summary 2>/dev/null' > "$OUT/regulator_summary.txt"; wc -l "$OUT/regulator_summary.txt"

echo "=== slimbus bus devices (codec enumerated => framer UP) ==="
A 'ls -l /sys/bus/slimbus/devices/ 2>/dev/null; echo ---; cat /sys/bus/slimbus/devices/*/modalias 2>/dev/null' | tee "$OUT/slimbus-devices.txt"

echo "=== ASoC / sound cards ==="
A 'cat /proc/asound/cards 2>/dev/null; echo ---; ls /proc/asound/ 2>/dev/null' | tee "$OUT/asound.txt"

echo "=== tinymix (mixer state, for UCM) ==="; A 'tinymix 2>/dev/null' > "$OUT/tinymix.txt"; wc -l "$OUT/tinymix.txt"

echo "=== subsystem/PIL + remoteproc/ADSP PD ==="
A 'for f in /sys/kernel/debug/msm_slim* /sys/devices/soc*/*.slim* ; do echo "## $f"; ls -l $f 2>/dev/null; done
   echo "--- pil/subsys ---"; ls /sys/bus/msm_subsys/devices/ 2>/dev/null; cat /sys/bus/msm_subsys/devices/*/state 2>/dev/null
   echo "--- avs/pd ---"; ls /sys/class/remoteproc/ 2>/dev/null' | tee "$OUT/subsys.txt"

echo "=== DT: slim + lpass nodes (downstream) ==="
A 'ls /proc/device-tree/soc/*slim* 2>/dev/null; echo ---; ls /proc/device-tree/soc/*c140000* 2>/dev/null' | tee "$OUT/dt-slim.txt"

echo "=== DONE -> $OUT ==="; ls -l "$OUT"
