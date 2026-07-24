#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# SD-kártya debug-log workflow: ha a telefon az SD-jére írja a boot/debug logot,
# a (vfat) "dirty bit" miatt máshol nem/koszosan mountolódik. Ez umountol + fsck-zik.
# Két mód:
#   phone  : a telefon SD-je (TWRP-ben, pl. mmcblk1p1) — umount + fsck a TELEFONON
#   host   : az SD a host kártyaolvasójában (pl. /dev/sdX1) — umount + fsck a HOSTON
# usage: sd-fsck.sh phone [mmcblk1p1] | host /dev/sdX1
set -uo pipefail
source "$(dirname "$0")/fp3-env.sh"
mode=${1:?phone|host}
case "$mode" in
  phone)
    dev=${2:-mmcblk1p1}
    have_recovery || { echo "TWRP kell ehhez."; exit 1; }
    log "phone SD fsck: /dev/block/$dev"
    adbr shell "umount /dev/block/$dev 2>/dev/null; umount /external_sd 2>/dev/null; \
                busybox fsck -y /dev/block/$dev 2>&1 || fsck.fat -a -w /dev/block/$dev 2>&1; sync; echo FSCK_DONE"
    ;;
  host)
    dev=${2:?/dev/sdX1 kell}
    log "host SD fsck: $dev (dirty-bit törlés)"
    sudo umount "$dev" 2>/dev/null || true
    sudo fsck.fat -a -w "$dev" 2>&1 || sudo fsck -y "$dev" 2>&1 || true
    sync; echo FSCK_DONE
    ;;
  *) echo "usage: $0 phone [mmcblk1p1] | host /dev/sdX1"; exit 2;;
esac
