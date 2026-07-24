#!/bin/bash
# deploy_snapCKB7_ut.sh — GOLDEN CBCR branch-enable capture on the UT oracle (framer ALIVE).
# CKB7 = corrected branch-enable hook (0xf04df0c8, both selector paths; folyt.127 fixes the
# CKB4/5 path-blindness). UT is PIL: push CKB7-injected p1 -> dd over /dev/mmcblk0p1 -> clean
# reboot -> read SMEM. Cave replicates every enable store (boot-safe). Answers: does the framer
# branch (0xee00d01c) get ENABLE-set on the WORKING side, and from where (caller r31)?

# Config lives in fp3-env.sh; every value there has a documented default.
for _d in "$(dirname "$0")" "$(dirname "$0")/.." "$(dirname "$0")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

set -uo pipefail
IMG=$FP3_ROOT/ut-p1-ckb7.img
RDR=$(dirname "$0")/smem_snapCKB7_read.py
PW="$FP3_PW"
A(){ timeout ${2:-30} adb shell "echo $PW | sudo -S sh -c '$1'" 2>/dev/null; }
waitdown(){ for i in $(seq 1 40); do adb get-state >/dev/null 2>&1 || { echo "[down $i]"; return 0; }; sleep 2; done; echo "ERR no-down"; return 1; }
waitup(){ for i in $(seq 1 60); do if timeout 8 adb shell "true" >/dev/null 2>&1; then echo "[up $i]"; return 0; fi; sleep 5; done; echo "ERR no-up"; return 1; }

echo "== [1] preflight (framer alive now? expect tasha=2) =="
A "cat /proc/asound/cards | grep -c tasha"
echo "== [2] push CKB7 p1 image ($(du -h $IMG|cut -f1)) =="
timeout 240 adb push "$IMG" /home/phablet/ut-p1-ckb7.img 2>&1 | tail -1
adb push "$RDR" /home/phablet/smem_snapCKB7_read.py 2>&1 | tail -1
echo "== [3] dd over /dev/mmcblk0p1 =="
A "dd if=/home/phablet/ut-p1-ckb7.img of=/dev/mmcblk0p1 bs=1M conv=fsync 2>&1 | tail -1; sync; md5sum /firmware/image/adsp.mdt" 180
echo "== [4] clean reboot =="
timeout 20 adb shell "echo $PW | sudo -S reboot" >/dev/null 2>&1 || true
waitdown || exit 1
echo "   waiting for boot..."; waitup || exit 1
sleep 18
echo "== [5] framer status (should STAY ALIVE with boot-safe cave) =="
A "cat /proc/asound/cards | grep -iE 'tasha|slim'; ls /sys/bus/slimbus/devices/ 2>/dev/null" 40
echo "== [6] READ CKB7 (SMEM) — golden branch-enable =="
echo "---- CKB7 GOLDEN READOUT (UT) ----"
A "python3 /home/phablet/smem_snapCKB7_read.py" 40
echo "----------------------------------"
echo "DONE -> OK"
