#!/bin/bash
# deploy_snapFRS2_ut.sh — GOLDEN FRS2 on the UT oracle (framer ALIVE, PIL cold boot).
# Reads back the framer-branch CBCR (CLK_OFF=bit31) + root guess after the enable, to diff vs the
# pmOS/dead side (folyt.128). UT is PIL: push FRS2-injected p1 -> dd over /dev/mmcblk0p1 -> clean
# reboot (COLD, clocks start gated) -> read SMEM. Cave is boot-safe (replicates every enable store).

# Config lives in fp3-env.sh; every value there has a documented default.
for _d in "$(dirname "$0")" "$(dirname "$0")/.." "$(dirname "$0")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

set -uo pipefail
IMG=$FP3_ROOT/ut-p1-frs2.img
RDR=$(dirname "$0")/smem_snapFRS2_read.py
PW="$FP3_PW"
A(){ timeout ${2:-30} adb shell "echo $PW | sudo -S sh -c '$1'" 2>/dev/null; }
waitdown(){ for i in $(seq 1 40); do adb get-state >/dev/null 2>&1 || { echo "[down $i]"; return 0; }; sleep 2; done; echo "ERR no-down"; return 1; }
waitup(){ for i in $(seq 1 60); do if timeout 8 adb shell "true" >/dev/null 2>&1; then echo "[up $i]"; return 0; fi; sleep 5; done; echo "ERR no-up"; return 1; }

echo "== [1] preflight (framer alive now? expect tasha=2) =="
A "cat /proc/asound/cards | grep -c tasha"
echo "== [2] push FRS2 p1 image ($(du -h $IMG|cut -f1)) =="
timeout 240 adb push "$IMG" /home/phablet/ut-p1-frs2.img 2>&1 | tail -1
adb push "$RDR" /home/phablet/smem_snapFRS2_read.py 2>&1 | tail -1
echo "== [3] dd over /dev/mmcblk0p1 =="
A "dd if=/home/phablet/ut-p1-frs2.img of=/dev/mmcblk0p1 bs=1M conv=fsync 2>&1 | tail -1; sync; md5sum /firmware/image/adsp.mdt" 180
echo "== [4] clean reboot (COLD PIL bring-up) =="
timeout 20 adb shell "echo $PW | sudo -S reboot" >/dev/null 2>&1 || true
waitdown || exit 1
echo "   waiting for boot..."; waitup || exit 1
sleep 18
echo "== [5] framer status (should STAY ALIVE — boot-safe cave) =="
A "cat /proc/asound/cards | grep -iE 'tasha|slim'; ls /sys/bus/slimbus/devices/ 2>/dev/null" 40
echo "== [6] READ FRS2 (SMEM) — GOLDEN framer-regs =="
echo "---- FRS2 GOLDEN READOUT (UT/alive) ----"
A "python3 /home/phablet/smem_snapFRS2_read.py" 40
echo "----------------------------------------"
echo "== [7] restore stock p1 (heal oracle) =="
echo "   (manual: dd ut-p1-stock.img over p1 if you want stock adsp back on UT)"
echo "DONE -> OK"
