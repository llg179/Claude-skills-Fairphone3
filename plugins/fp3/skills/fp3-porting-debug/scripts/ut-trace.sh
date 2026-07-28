#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# DOWNSTREAM (Ubuntu Touch / Halium 10, downstream 4.9.218 kernel) SLIMbus trace.
# Run from HOST while phone is booted into UT with adb (Halium adb runs as phablet; use sudo).
# Captures the WORKING SLIMbus framer bring-up to diff vs pmOS (mainline) baseline.
# usage: ut-trace.sh [outdir]

# Config lives in fp3-env.sh; every value there has a documented default.
# Resolve symlinks first: these scripts are commonly installed as symlinks in
# /usr/local/bin, where a bare $0 would look for fp3-env.sh next to the symlink.
_self="$(readlink -f "$0")"
for _d in "$(dirname "$_self")" "$(dirname "$_self")/.." "$(dirname "$_self")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

set -uo pipefail
OUT=${1:-$FP3_PMOS/pmos-backup-20260629/ut-trace}
mkdir -p "$OUT"
# UT: phablet user, default password "phablet" (or whatever set). sudo for root.
PW="${UT_PW:-phablet}"
S(){ adb shell "echo $PW | sudo -S sh -c '$1'" 2>/dev/null; }

echo "=== adb up? ==="; adb wait-for-device; adb shell 'echo connected; whoami' 2>&1 | head
echo "=== meta ==="; S 'uname -a; cat /etc/os-release | grep PRETTY' | tee "$OUT/meta.txt"

echo "=== full dmesg ==="; S 'dmesg' > "$OUT/dmesg-full.txt"; wc -l "$OUT/dmesg-full.txt"
echo "=== slim/ngd/qmi/tasha/wcd/avs/adsp/pil/q6/framer/pd/lpass grep ==="
grep -iE 'slim|ngd|msm_slim|qmi|tasha|wcd93|wcd9326|avs|adsp|pil |q6afe|q6voice|slimbus|framer|laddr|capability|servreg|sysmon|lpass|reconf|satellite' \
  "$OUT/dmesg-full.txt" | tee "$OUT/dmesg-slim.txt" | tail -100

echo "=== clk_summary FULL (KEY diff) ==="
S 'cat /sys/kernel/debug/clk/clk_summary' > "$OUT/clk_summary.txt"; wc -l "$OUT/clk_summary.txt"
echo "--- enabled slim/lpass/audio clocks (downstream) ---"
grep -iE 'slim|lpass|audio|mclk|q6|ult|bb_clk|cxo' "$OUT/clk_summary.txt" | awk '$3+0>0 || /slim/i' | head -60

echo "=== regulator_summary ==="; S 'cat /sys/kernel/debug/regulator/regulator_summary' > "$OUT/regulator_summary.txt"; wc -l "$OUT/regulator_summary.txt"

echo "=== slimbus bus devices (codec enumerated => framer UP) ==="
S 'ls -l /sys/bus/slimbus/devices/ 2>/dev/null; for d in /sys/bus/slimbus/devices/*/; do echo "## $d"; cat $d/modalias 2>/dev/null; done' | tee "$OUT/slimbus-devices.txt"

echo "=== ASoC cards + mixer (tasha) ==="; S 'cat /proc/asound/cards; ls /proc/asound/' | tee "$OUT/asound.txt"
echo "=== tinymix (downstream mixer_paths source-of-truth) ==="; S 'tinymix' > "$OUT/tinymix.txt"; wc -l "$OUT/tinymix.txt"

echo "=== PIL / subsystem state (downstream uses msm_subsys) ==="
S 'ls /sys/bus/msm_subsys/devices/ 2>/dev/null; for s in /sys/bus/msm_subsys/devices/*/; do echo -n "$s "; cat $s/name 2>/dev/null; cat $s/state 2>/dev/null; done' | tee "$OUT/subsys.txt"

echo "=== msm_slim debugfs / slim driver state ==="
S 'for f in /sys/kernel/debug/msm_slim* /sys/kernel/debug/*slim*; do echo "## $f"; ls -l $f 2>/dev/null; cat $f 2>/dev/null | head; done' > "$OUT/slim-debug.txt"; cat "$OUT/slim-debug.txt" | head -40

echo "=== DT slim + lpass (downstream) ==="
S 'ls /proc/device-tree/soc/*slim* 2>/dev/null; echo ---; ls /proc/device-tree/soc/*c140000* 2>/dev/null; echo ---q6; ls /proc/device-tree/soc/qcom,msm-* 2>/dev/null' | tee "$OUT/dt-slim.txt"

echo "=== DONE -> $OUT ==="; ls -l "$OUT"
