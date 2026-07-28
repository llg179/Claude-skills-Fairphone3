#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# READ-ONLY discovery on UT (downstream slot_a) to find the real node paths the
# SLIMbus framer SSR-recovery trace will need, before we trigger anything.
# Requires adb in DEVICE mode (USB debugging ON). NEVER use `sudo adb`.
# usage: ut-discover.sh

# Config lives in fp3-env.sh; every value there has a documented default.
# Resolve symlinks first: these scripts are commonly installed as symlinks in
# /usr/local/bin, where a bare $0 would look for fp3-env.sh next to the symlink.
_self="$(readlink -f "$0")"
for _d in "$(dirname "$_self")" "$(dirname "$_self")/.." "$(dirname "$_self")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

set -uo pipefail
OUT=$FP3_PMOS/ut-discover-$(date +%Y%m%d-%H%M); mkdir -p "$OUT"; echo "OUT=$OUT"

if [ "$(adb get-state 2>/dev/null)" != "device" ]; then
  echo "!! UT adb NOT in device mode (got: $(adb get-state 2>/dev/null || echo none))."
  echo "   Enable USB debugging / switch USB mode on UT, then re-run."; exit 1
fi
SH(){ adb shell "su -c '$1' 2>/dev/null || $1" 2>/dev/null; }

echo "=== kernel / build ===" | tee "$OUT/00-info.txt"
SH 'uname -a; getprop ro.build.fingerprint' | tee -a "$OUT/00-info.txt"

echo "=== SSR trigger candidate nodes ===" | tee "$OUT/01-ssr-nodes.txt"
SH 'ls -l /sys/kernel/debug/msm_subsys/ 2>/dev/null;
    echo ---; for d in /sys/bus/msm_subsys/devices/subsys*; do echo "$d:"; cat $d/name 2>/dev/null; ls $d 2>/dev/null; done;
    echo ---; for d in /sys/class/subsys/*; do echo "$d:"; cat $d/name 2>/dev/null; done;
    echo ---restart_level---; for f in /sys/kernel/debug/msm_subsys/*; do echo "$f="; cat $f 2>/dev/null; done' \
  | tee -a "$OUT/01-ssr-nodes.txt"

echo "=== ipc_logging channels (slim/qmi) ===" | tee "$OUT/02-ipc.txt"
SH 'ls /sys/kernel/debug/ipc_logging/ 2>/dev/null | grep -iE "slim|qmi|ngd|adsp|lpass|q6"' | tee -a "$OUT/02-ipc.txt"

echo "=== clk_summary present? ===" | tee "$OUT/03-clk.txt"
SH 'wc -l /sys/kernel/debug/clk/clk_summary 2>/dev/null;
    grep -iE "slim|lpass|q6|bb_clk1|gcc_ultaudio|gcc_lpa" /sys/kernel/debug/clk/clk_summary 2>/dev/null' \
  | tee -a "$OUT/03-clk.txt"

echo "=== slimbus devices (framer up = codec laddr present) ===" | tee "$OUT/04-slim.txt"
SH 'ls -l /sys/bus/slimbus/devices/ 2>/dev/null; echo ---; ls /sys/bus/slimbus/drivers/ 2>/dev/null' | tee -a "$OUT/04-slim.txt"

echo "=== /dev/mem + busybox devmem availability ===" | tee "$OUT/05-devmem.txt"
SH 'ls -l /dev/mem 2>/dev/null; which devmem busybox toybox 2>/dev/null;
    grep -i strict_devmem /proc/config.gz >/dev/null 2>&1 && echo "config.gz present" ' \
  | tee -a "$OUT/05-devmem.txt"

echo "=== audio/slim user processes + open chardevs ===" | tee "$OUT/06-proc.txt"
SH 'ps -A 2>/dev/null | grep -iE "audio|acdb|adsp|qmux|qrtr|pd-mapper|hal" || ps 2>/dev/null | grep -iE "audio|acdb|adsp|qmux";
    echo ---lsof---; lsof 2>/dev/null | grep -iE "slim|msm_|smd|qmi|adsp|acdb" | head -40' \
  | tee -a "$OUT/06-proc.txt"

echo "=== tinymix / mixer present ===" | tee "$OUT/07-mixer.txt"
SH 'which tinymix 2>/dev/null; tinymix 2>/dev/null | head -5; ls /proc/asound/ 2>/dev/null' | tee -a "$OUT/07-mixer.txt"

echo "=== boot dmesg: framer-up evidence (golden) ==="
SH 'dmesg | grep -iE "slim|ngd|laddr|reconf|framer|capabilit|qmi|wcd93|tasha|adsp" | head -60' | tee "$OUT/08-dmesg-boot.txt"

echo "=== DONE -> $OUT ==="
ls -1 "$OUT"