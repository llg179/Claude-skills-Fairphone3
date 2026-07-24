#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# pmOS flash-szekvencia (fastboot módban). Tartalmazza a vbmeta-disable lépést,
# ami a hybris/AVB-gyanú miatt KELL ("Fairphone powered by android -> fastboot" tünet).
# usage: flash-pmos.sh [full|lk2nd|vbmeta|rootfs]   (default: full)
#   full  = vbmeta(disable) + lk2nd + rootfs(userdata) + reboot
# lk2nd a boot partícióra megy (PARTITION_KERNEL), rootfs a userdata-ra; boot-ot KÜLÖN nem flashelünk.
set -uo pipefail
source "$(dirname "$0")/fp3-env.sh"
step=${1:-full}
have_fastboot || { echo "fastboot mód kell. (TWRP-ből: adbr reboot bootloader)"; exit 1; }
do_vbmeta(){ log "flash_vbmeta (AVB verify OFF)"; yes '' | $PMB flasher flash_vbmeta 2>&1 | tail -8; }
do_lk2nd(){  log "flash_lk2nd -> boot"; yes '' | $PMB flasher flash_lk2nd 2>&1 | tail -8; }
do_rootfs(){ log "flash_rootfs -> userdata"; yes '' | $PMB flasher flash_rootfs --partition userdata 2>&1 | tail -10; }
case "$step" in
  vbmeta) do_vbmeta;;
  lk2nd)  do_lk2nd;;
  rootfs) do_rootfs;;
  full)   do_vbmeta; do_lk2nd; do_rootfs; log "reboot"; fb reboot 2>&1|tail -1;;
  *) echo "usage: $0 [full|lk2nd|vbmeta|rootfs]"; exit 2;;
esac
