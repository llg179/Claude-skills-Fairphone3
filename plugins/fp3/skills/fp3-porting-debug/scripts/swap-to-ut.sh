#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Installer-free, hands-free restore of the developer-enabled Ubuntu Touch backup
# (slot a, captured 2026-06-30) so pmOS<->UT can be swapped without the UBports GUI
# installer or any user interaction.
#
# FP3 quirk: `fastboot boot X.img` is BROKEN on this aboot, so TWRP is flashed to
# boot_b (boot_a/lk2nd untouched) and we dd from there. The gz images are STREAM-
# decompressed straight onto the block devices (no push: system_a=3G / userdata=48G
# don't fit the TWRP ramdisk /tmp). The dev-mode + passcode live in userdata, which
# must be restored; system_a/vendor_a actually survive a pmOS session untouched, so
# 'quick' skips them.
#
# usage: swap-to-ut.sh            (full: boot/dtbo/vbmeta/vendor/system/userdata)
#        swap-to-ut.sh quick      (boot/dtbo/vbmeta/userdata only -> much faster)
set -uo pipefail
source "$(dirname "$0")/fp3-env.sh"
HERE="$(dirname "$0")"
OUT=$FP3_PMOS/ut-backup-20260630
mode=${1:-full}

case "$mode" in
  full)  PARTS="boot_a dtbo_a vbmeta_a vendor_a system_a userdata";;
  quick) PARTS="boot_a dtbo_a vbmeta_a userdata";;
  *) echo "usage: $0 [full|quick]"; exit 2;;
esac

for p in $PARTS; do
  f="$OUT/$p.img.gz"
  [ -f "$f" ] || { echo "MISSING $f"; exit 1; }
  gunzip -t "$f" 2>/dev/null || { echo "CORRUPT $f"; exit 1; }
done
echo "backup set OK ($mode): $PARTS"

# 1) reach TWRP on boot_b (leaves boot_a/lk2nd alone; fastboot boot is broken on FP3)
if ! have_recovery; then
  have_fastboot || { echo "Put the phone in fastboot first (or TWRP)."; exit 1; }
  log "flash TWRP -> boot_b + set_active b + reboot to recovery"
  bash "$HERE/twrp.sh" flash-b
  wait_state recovery 90 || { echo "TWRP did not come up"; exit 1; }
fi
adbr wait-for-recovery 2>/dev/null || true
sleep 2

# 2) stream-restore each slot-a partition (by-name points at the physical slot-a part
#    regardless of which slot booted TWRP)
for p in $PARTS; do
  dev="/dev/block/bootdevice/by-name/$p"
  log "restore $p -> $dev (stream gunzip|dd)"
  gunzip -c "$OUT/$p.img.gz" | adbr shell "dd of=$dev bs=4M 2>/dev/null; sync; echo WROTE_$p"
done

# 3) make slot a active and boot UT
log "reboot to bootloader -> set_active a -> reboot to UT"
adbr reboot bootloader 2>&1 | tail -1
wait_state fastboot 90 || { echo "did not reach fastboot to set slot"; exit 1; }
fb set_active a 2>&1 | tail -1
fb reboot 2>&1 | tail -1
log "DONE -> the dev-enabled UT (slot a) boots. adb over USB after ~40s; kernel 4.9.218."
