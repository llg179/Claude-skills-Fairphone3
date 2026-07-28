#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
#
# ############################################################################
# ##  THIS IS *NOT* HOW YOU SWITCH OS.  Read this before running it.        ##
# ############################################################################
#
# Switching between the two OSes is FREE and involves NO flashing at all:
#
#     scripts/slot.sh set a     # -> Ubuntu Touch   (boot_a = UT Halium boot image)
#     scripts/slot.sh set b     # -> postmarketOS   (boot_b = lk2nd -> pmOS)
#     then reboot
#
# That works because `setup-dualslot.sh` has already been run once: it puts the
# pmOS rootfs on `system_b` instead of `userdata`, so UT keeps `userdata` to
# itself and the two OSes never overwrite each other.  Full description of the
# layout and its one-time preparation:
#   https://github.com/llg179/Claude-skills-Fairphone3#installing-the-two-oses
#   ("Both at once: the dual-slot setup")
#
# THIS script is the REPAIR path, for one situation only: the developer-enabled
# Ubuntu Touch install on slot a has been damaged or overwritten (userdata wiped,
# dev mode / passcode lost, system_a clobbered) and has to be restored from the
# 2026-06-30 backup without the UBports GUI installer.
#
# ☠️ It flashes TWRP onto `boot_b` — which on the current dual-slot device holds
#    lk2nd, i.e. the postmarketOS boot path.  Running it therefore BREAKS pmOS
#    booting until lk2nd is reflashed (`pmbootstrap flasher flash_lk2nd`).
# ☠️ It restores `userdata` from the 2026-06-30 backup, which DESTROYS anything
#    staged into userdata since then — including the unattended-access setup
#    (ssh key, ssh.service symlink, ut-force-usbnet.service).  See the README
#    section "Unattended access: no on-device login, no USB replug".
#    If you only need UT's boot/dtbo/vbmeta back, drop `userdata` from PARTS.
#
# History: the header used to describe this as the normal pmOS<->UT swap.  That
# was true BEFORE the dual-slot install existed, when both OSes wanted slot a.
# It is no longer true; do not infer the disk layout from this file — read the
# partitions (`dd if=/dev/disk/by-partlabel/boot_a bs=1 count=64 | strings`).
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
