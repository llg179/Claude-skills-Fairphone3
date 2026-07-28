#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Deploy the rebuilt slim-qcom-ngd-ctrl.ko (CHECK_FRAMER_STATUS fix) + the
# slimbus-enabled sdm632-fairphone-fp3.dtb to the live pmOS, reboot, and capture
# the SLIMbus/NGD bring-up dmesg. Safe minimal swap: CONFIG_MODVERSIONS is off and
# vermagic matches, so the .ko loads against the running kernel without a reflash.
# Reversible: /boot/...dtb.bak (speaker-working) stays on the phone.

# Config lives in fp3-env.sh; every value there has a documented default.
# Resolve symlinks first: these scripts are commonly installed as symlinks in
# /usr/local/bin, where a bare $0 would look for fp3-env.sh next to the symlink.
_self="$(readlink -f "$0")"
for _d in "$(dirname "$_self")" "$(dirname "$_self")/.." "$(dirname "$_self")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

set -uo pipefail
SSHP="sshpass -p "$FP3_PW" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8"
HOST=fp3@$FP3_DEV_IP
APK=$(ls -t $FP3_PMOS/work/packages/edge/aarch64/linux-postmarketos-qcom-msm8953-*.apk 2>/dev/null | head -1)
OUT=${1:-$FP3_PMOS/pmos-backup-20260629/checkframer-$(date +%H%M)}
mkdir -p "$OUT"
echo "newest apk: $APK"

TMP=$(mktemp -d)
tar xzf "$APK" -C "$TMP" 2>/dev/null
DTB="$TMP/boot/dtbs/qcom/sdm632-fairphone-fp3.dtb"
KO="$TMP/usr/lib/modules/7.0.9-msm8953/kernel/drivers/slimbus/slim-qcom-ngd-ctrl.ko"
ls -l "$DTB" "$KO" || { echo "extract FAIL"; exit 1; }
echo "ko has fix:"; strings "$KO" | grep -c 'check_framer rc'

echo "=== phone up? ==="
$SSHP $HOST 'echo UP; uname -r' 2>&1 | head -2 || { echo "phone unreachable"; exit 1; }

echo "=== push .ko (both module trees) ==="
$SSHP $HOST 'mkdir -p /tmp/dep' 2>&1
sshpass -p "$FP3_PW" scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$KO" $HOST:/tmp/dep/ngd.ko 2>&1 | tail -1
sshpass -p "$FP3_PW" scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$DTB" $HOST:/tmp/dep/new.dtb 2>&1 | tail -1

$SSHP $HOST 'echo "$FP3_PW" | sudo -S sh -c "
  set -e
  M=/lib/modules/7.0.9-msm8953/kernel/drivers/slimbus/slim-qcom-ngd-ctrl.ko
  U=/usr/lib/modules/7.0.9-msm8953/kernel/drivers/slimbus/slim-qcom-ngd-ctrl.ko
  cp -n \$M \$M.bak 2>/dev/null || true
  cp /tmp/dep/ngd.ko \$M
  cp /tmp/dep/ngd.ko \$U 2>/dev/null || true
  cp -n /boot/sdm632-fairphone-fp3.dtb /boot/sdm632-fairphone-fp3.dtb.preCF 2>/dev/null || true
  cp /tmp/dep/new.dtb /boot/sdm632-fairphone-fp3.dtb
  cp /tmp/dep/new.dtb /boot/dtbs/qcom/sdm632-fairphone-fp3.dtb
  sync
  echo MODSHA; sha256sum \$M /boot/sdm632-fairphone-fp3.dtb
  echo KOFIX; strings \$M | grep -c \"check_framer rc\"
"' 2>&1

echo "=== reboot ==="
$SSHP $HOST 'echo "$FP3_PW" | sudo -S reboot' 2>&1 | head -1
echo "waiting..."; sleep 28
for i in $(seq 1 45); do
  if $SSHP $HOST 'echo BACK' 2>/dev/null | grep -q BACK; then echo "phone back (i=$i)"; break; fi
  sleep 5
done

echo "=== capture dmesg ==="
$SSHP $HOST 'echo "$FP3_PW" | sudo -S dmesg' 2>/dev/null > "$OUT/dmesg-full.txt"
wc -l "$OUT/dmesg-full.txt"
echo "--- check_framer + bring-up ---"
grep -iE 'check_framer|DBG power_up|DBG RX|capability|laddr|reconf|framer|slim|ngd|qmi|wcd9335|tasha|q6afe|sound|asoc' "$OUT/dmesg-full.txt" | tee "$OUT/dmesg-slim.txt" | tail -90
echo "=== slimbus devices ==="
$SSHP $HOST 'ls -la /sys/bus/slimbus/devices/ 2>&1; echo ---drv---; ls /sys/bus/slimbus/drivers/ 2>&1; echo ---lsmod---; lsmod | grep -iE "ngd|slim|wcd"' 2>&1 | tee "$OUT/slimbus-devices.txt"
echo "=== sound cards ==="
$SSHP $HOST 'cat /proc/asound/cards 2>&1' | tee "$OUT/asound-cards.txt"
echo "=== DONE -> $OUT ==="
