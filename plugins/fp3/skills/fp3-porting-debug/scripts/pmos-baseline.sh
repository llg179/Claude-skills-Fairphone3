#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-or-later
# pmOS-side (mainline, "broken" SLIMbus) baseline capture for downstream diff

# Config lives in fp3-env.sh; every value there has a documented default.
for _d in "$(dirname "$0")" "$(dirname "$0")/.." "$(dirname "$0")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

PW="$FP3_PW"
S() { echo "$PW" | sudo -S sh -c "$1" 2>/dev/null; }
OUT=/tmp/pmos-baseline
mkdir -p "$OUT"
echo "=== meta ==="; uname -a; date; cat /etc/os-release | grep PRETTY

echo; echo "=== remoteproc states ==="
for r in /sys/class/remoteproc/remoteproc*; do
  [ -e "$r" ] || continue
  printf "%s  name=%s  state=%s\n" "$r" "$(cat $r/name 2>/dev/null)" "$(cat $r/state 2>/dev/null)"
done

echo; echo "=== fastrpc / PD / dsp devices ==="
ls -l /dev/ | grep -iE 'fastrpc|adsp|slim|cdsp|dsp' || echo "(none in /dev)"

echo; echo "=== pd-mapper / qrtr services ==="
S "systemctl status pd-mapper 2>/dev/null | head -6"
S "pgrep -a pd-mapper"; S "pgrep -a rmtfs"; S "pgrep -a qrtr"
echo "--- qrtr lookup ---"; S "qrtr-lookup 2>/dev/null | head -40"

echo; echo "=== slim/ngd/lpass/adsp/q6/apr/qmi/pil/wcd dmesg ==="
S "dmesg | grep -iE 'slim|ngd|lpass|adsp|q6|apr|qmi|pil |remoteproc|wcd|glink|smp2p|protection|spawn|pdr' " | tail -120

echo; echo "=== clk_summary: slim/lpass/audio/mclk/bb lines ==="
S "grep -iE 'slim|lpass|audio|mclk|bi_tcxo|cxo|gcc_ultaudio|ult_|q6' /sys/kernel/debug/clk/clk_summary"

echo; echo "=== saving FULL clk_summary + dmesg to $OUT ==="
S "cat /sys/kernel/debug/clk/clk_summary" > "$OUT/clk_summary.txt" 2>/dev/null
wc -l "$OUT/clk_summary.txt"
S "dmesg" > "$OUT/dmesg.txt" 2>/dev/null
wc -l "$OUT/dmesg.txt"

echo; echo "=== ADSP DT node (mainline) ==="
S "find /proc/device-tree -iname '*remoteproc*' -o -iname '*lpass*' -o -iname '*adsp*' 2>/dev/null | head"
echo "--- adsp pas-id / smd-edge ---"
for n in $(S "ls -d /proc/device-tree/soc@0/remoteproc* 2>/dev/null"); do
  echo "node: $n"; S "ls $n"
done

echo; echo "=== genpd / power domains (audio?) ==="
S "cat /sys/kernel/debug/pm_genpd/pm_genpd_summary 2>/dev/null | grep -iE 'lcx|lmx|mss|adsp|cx|mx' | head"

echo "=== DONE ==="
