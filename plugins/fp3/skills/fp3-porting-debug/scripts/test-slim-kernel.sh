#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Install the freshly-built patched kernel into the pmOS rootfs, flash it to
# system_b (dual-slot), boot, and capture the slim/NGD bring-up dmesg (incl. the
# experiment's per-retry NGD register dump). Device must be in pmOS (slot_b) or
# fastboot. usage: test-slim-kernel.sh
set -uo pipefail
source "$(dirname "$0")/fp3-env.sh"
SSH(){ timeout "${2:-30}" sshpass -p "$FP3_PW" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null fp3@$FP3_DEV_IP "echo "$FP3_PW" | sudo -S sh -c '$1'" 2>/dev/null; }
OUT=$FP3_PMOS/pmos-slimtest-$(date +%Y%m%d-%H%M); mkdir -p "$OUT"; echo "OUT=$OUT"

echo "=== [1] pmb install (regenerate rootfs with new kernel, FOREGROUND) ==="
timeout 600 "$PMB" install --password "$FP3_PW" 2>&1 | tail -15

echo "=== [2] device -> bootloader ==="
if timeout 8 sshpass -p "$FP3_PW" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null fp3@$FP3_DEV_IP true 2>/dev/null; then
  SSH 'reboot bootloader' 10
fi
for i in $(seq 1 45); do sudo fastboot devices 2>/dev/null | grep -q fastboot && { echo "fastboot UP @ $((i*2))s"; break; }; sleep 2; done

echo "=== [3] flash system_b + ensure slot b ==="
sudo fastboot set_active b 2>&1 | tail -1
yes '' | "$PMB" flasher flash_rootfs --partition system_b 2>&1 | tail -10
sudo fastboot set_active b 2>&1 | tail -1
sudo fastboot reboot 2>&1 | tail -1

echo "=== [4] wait pmOS SSH ==="
for i in $(seq 1 50); do
  r=$(timeout 10 sshpass -p "$FP3_PW" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=4 fp3@$FP3_DEV_IP 'uname -r' 2>/dev/null)
  [ -n "$r" ] && { echo "pmOS UP @ ~$((i*3))s ($r)"; break; }
  sleep 3
done

echo "=== [5] capture slim/NGD bring-up dmesg (incl. retry NGD dumps) ==="
SSH 'dmesg | grep -iE "slim|ngd|qmi|capability|laddr|reconf|retry|STATUS=|CFG=|INT_STAT=|adsp"' | tee "$OUT/dmesg-slim.txt"
echo "=== slimbus devices (framer up if codec enumerated) ==="
SSH 'ls /sys/bus/slimbus/devices/ 2>/dev/null' | tee "$OUT/slimbus-devices.txt"
echo "=== DONE -> $OUT ==="
