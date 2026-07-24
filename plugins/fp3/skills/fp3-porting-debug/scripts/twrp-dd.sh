#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# TWRP-adb úton image partícióra írása (mert `fastboot boot` az FP3 abooton tiltott/megbízhatatlan).
# Sparse Android image-et simg2img-gal ír; nyers image-et dd-vel.
# usage: twrp-dd.sh <local.img> <by-name-part|/dev/block/...> [raw|sparse]
#   pl: twrp-dd.sh twrp-fp3.img boot_b raw
#       twrp-dd.sh sailfish.img001 userdata sparse
set -uo pipefail
source "$(dirname "$0")/fp3-env.sh"
IMG=${1:?local image kell}; PART=${2:?partíció kell (pl boot_b vagy userdata)}; MODE=${3:-raw}
have_recovery || { echo "Nem TWRP/recovery-ben van. Előbb twrp.sh boot."; exit 1; }
[ -f "$IMG" ] || { echo "nincs ilyen fájl: $IMG"; exit 1; }
case "$PART" in /dev/*) DST=$PART;; *) DST=/dev/block/bootdevice/by-name/$PART;; esac
B=/tmp/$(basename "$IMG")
log "push $IMG -> phone:$B"
adbr push "$IMG" "$B"
if [ "$MODE" = sparse ]; then
  log "simg2img $B -> $DST"
  adbr shell "simg2img $B $DST && sync && echo WROTE_SPARSE_OK"
else
  log "dd $B -> $DST"
  adbr shell "dd if=$B of=$DST bs=4096 && sync && echo WROTE_RAW_OK"
fi
adbr shell "rm -f $B"
