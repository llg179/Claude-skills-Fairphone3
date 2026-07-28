#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Back up developer-enabled UT (slot a) partition images for installer-free pmOS<->UT swap.

# Config lives in fp3-env.sh; every value there has a documented default.
# Resolve symlinks first: these scripts are commonly installed as symlinks in
# /usr/local/bin, where a bare $0 would look for fp3-env.sh next to the symlink.
_self="$(readlink -f "$0")"
for _d in "$(dirname "$_self")" "$(dirname "$_self")/.." "$(dirname "$_self")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

set -uo pipefail
PW="$FP3_PW"
OUT=$FP3_PMOS/ut-backup-20260630
mkdir -p "$OUT"
# name:partnode:expected_bytes
SET="
boot_a:mmcblk0p27:67108864
dtbo_a:mmcblk0p23:8388608
vbmeta_a:mmcblk0p25:65536
vendor_a:mmcblk0p32:1073741824
system_a:mmcblk0p30:3221225472
userdata:mmcblk0p62:0
"
log(){ echo "[$(date +%H:%M:%S)] $*"; }
for line in $SET; do
  [ -z "$line" ] && continue
  name=${line%%:*}; rest=${line#*:}; node=${rest%%:*}; exp=${rest##*:}
  log "BACKUP $name ($node) -> $name.img.gz ..."
  adb exec-out "echo $PW | sudo -S dd if=/dev/$node bs=4M 2>/dev/null | gzip -1 -c -f" > "$OUT/$name.img.gz" 2>/dev/null
  us=$(gzip -l "$OUT/$name.img.gz" 2>/dev/null | awk 'NR==2{print $2}')
  cs=$(stat -c %s "$OUT/$name.img.gz")
  ok="?"; [ "$exp" != "0" ] && { [ "$us" = "$exp" ] && ok="OK" || ok="SIZE-MISMATCH(exp=$exp got=$us)"; }
  log "  done $name: gz=${cs}B uncompressed=${us}B $ok"
  gunzip -t "$OUT/$name.img.gz" 2>/dev/null && log "  gzip-integrity OK" || log "  !!! GZIP CORRUPT $name"
done
log "ALL DONE -> $OUT"
ls -la "$OUT"
