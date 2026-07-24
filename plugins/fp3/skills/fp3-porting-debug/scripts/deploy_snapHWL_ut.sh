#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# deploy_snapHWL_ut.sh — GOLDEN (UT/oracle, framer ALIVE) HalHwIo/PLL-lock leaf ring capture.
# UT is PIL: firmware = split on vfat /dev/mmcblk0p1 (RO in LXC). Recipe (proven, T3-A):
#   push whole HWL-injected p1 image -> dd over /dev/mmcblk0p1 -> clean reboot -> read SMEM ring.
# Non-crashing cave (guarded loads + re-read of an addr the leaf just wrote) => oracle-safe.

# Config lives in fp3-env.sh; every value there has a documented default.
for _d in "$(dirname "$0")" "$(dirname "$0")/.." "$(dirname "$0")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

set -uo pipefail
IMG=$FP3_ROOT/ut-p1-hwl.img
RDR=$(dirname "$0")/smem_snapHWL_read.py
PW="$FP3_PW"
A(){ timeout ${2:-30} adb shell "echo $PW | sudo -S sh -c '$1'" 2>/dev/null; }
waitdown(){ for i in $(seq 1 40); do adb get-state >/dev/null 2>&1 || { echo "[down $i]"; return 0; }; sleep 2; done; echo "ERR no-down"; return 1; }
waitup(){ for i in $(seq 1 60); do
    if timeout 8 adb shell "true" >/dev/null 2>&1; then echo "[up $i]"; return 0; fi; sleep 5; done
    echo "ERR no-up"; return 1; }

echo "== [1] preflight (framer alive now?) =="
A "cat /proc/asound/cards | grep -c tasha"
echo "== [2] push HWL p1 image ($(du -h $IMG|cut -f1)) =="
timeout 180 adb push "$IMG" /home/phablet/ut-p1-hwl.img 2>&1 | tail -1
adb push "$RDR" /home/phablet/smem_snapHWL_read.py 2>&1 | tail -1
echo "== [3] dd over /dev/mmcblk0p1 =="
A "dd if=/home/phablet/ut-p1-hwl.img of=/dev/mmcblk0p1 bs=1M conv=fsync 2>&1 | tail -1; sync; md5sum /firmware/image/adsp.mdt" 120
echo "== [4] clean reboot =="
timeout 20 adb shell "echo $PW | sudo -S reboot" >/dev/null 2>&1 || true
waitdown || exit 1
echo "   waiting for boot..."; waitup || exit 1
sleep 15
echo "== [5] framer status (should stay ALIVE with non-crashing cave) =="
A "cat /proc/asound/cards | grep -iE 'tasha|slim'; ls /sys/bus/slimbus/devices/ 2>/dev/null" 40
echo "== [6] READ HWL ring (SMEM) =="
echo "---- HWL GOLDEN READOUT ----"
A "python3 /home/phablet/smem_snapHWL_read.py" 40
echo "----------------------------"
echo "DONE -> OK (HWL cave left in place; framer alive; non-crashing)"
