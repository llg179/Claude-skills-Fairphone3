#!/bin/bash
# Runs ON UT / Ubuntu Touch (slot_a, the ORACLE). Deploys the caved adsp.mdt+bNN, triggers a framer bring-up,
# reads the framer-status SMEM stash (working side), then restores stock. UT loads the ADSP via PIL
# (subsys-pil-tz) from /vendor/firmware_mnt/image. Prefers an SSR restart node (re-runs PIL bring-up without a
# reboot); if none exists, falls back to the REBOOT flow (see README — this script prints the two-stage steps).
#
# ORACLE CAUTION: this modifies slot_a firmware. Stock backup is kept; restore = copy back + SSR/reboot.
# Run as root (sudo). PIN "$FP3_PW".

# Config lives in fp3-env.sh; every value there has a documented default.
for _d in "$(dirname "$0")" "$(dirname "$0")/.." "$(dirname "$0")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

set -uo pipefail
IMG=/vendor/firmware_mnt/image
STAGE=/home/phablet/ut-fss-staging     # UT is Ubuntu: home is /home/phablet
BK=/home/phablet/ut-adsp-stock-bak
RES=/home/phablet/ut-fss-result.txt

echo "=== $(date) UT-FSS onboard (WORKING side) ===" > "$RES"; sync
{
echo "-- writability + baseline --"
mount | grep -E 'firmware_mnt|/vendor' | head
ls -la $IMG/adsp.mdt $IMG/adsp.b00 2>/dev/null | head
md5sum $IMG/adsp.mdt 2>/dev/null   # stock expected bab175ed...

echo "-- backup stock adsp.{mdt,b*} (once) --"
if [ ! -d "$BK" ]; then mkdir -p "$BK"; cp $IMG/adsp.mdt $IMG/adsp.b* "$BK"/; echo "backed up to $BK"; else echo "backup already exists"; fi

echo "-- zero SMEM stash (0x60 @ 0x86302ab0) --"
python3 - <<'PY'
import mmap
f=open('/dev/mem','r+b'); m=mmap.mmap(f.fileno(),0x1000,offset=0x86302000)
m[0xab0:0xab0+0x60]=b'\x00'*0x60; m.close(); f.close(); print('zeroed')
PY

echo "-- remount rw if needed + deploy caved firmware --"
mount -o remount,rw $IMG 2>/dev/null || mount -o remount,rw /vendor 2>/dev/null || true
cp $STAGE/adsp.mdt $STAGE/adsp.b* $IMG/; sync; md5sum $IMG/adsp.mdt

echo "-- locate an ADSP SSR restart node --"
SSR=""
for c in /sys/kernel/debug/msm_subsys/adsp /sys/bus/msm_subsys/devices/subsys*/restart; do
  [ -e "$c" ] && { SSR="$c"; break; }
done
# also try name-matched subsys
if [ -z "$SSR" ]; then
  for d in /sys/bus/msm_subsys/devices/subsys*; do
    [ -e "$d/name" ] && grep -qi adsp "$d/name" && SSR="$d/restart" && break
  done
fi
echo "SSR node = ${SSR:-NONE}"

if [ -n "$SSR" ]; then
  echo "-- SSR restart adsp (re-runs PIL bring-up, framing-START executes) --"
  echo restart > "$SSR" 2>&1 || echo "restart" > "$SSR" 2>&1 || echo "SSR write failed"
  sleep 12
else
  echo "!! NO SSR node. REBOOT FLOW REQUIRED (do NOT auto-reboot here):"
  echo "   1) firmware already deployed above. Run: sudo reboot"
  echo "   2) after boot, as root: python3 $STAGE/smem_ut_fss_read.py"
  echo "   3) then restore: cp $BK/* $IMG/ && sync && sudo reboot"
  echo "-- stopping here; SMEM read + restore must follow the reboot --"
  exit 7
fi
} >> "$RES" 2>&1; sync

echo "-- UT-FSS working-side framer read --" >> "$RES"
python3 $STAGE/smem_ut_fss_read.py >> "$RES" 2>&1; sync

{
echo "-- restore stock + SSR --"
cp $BK/* $IMG/; sync; md5sum $IMG/adsp.mdt
if [ -n "$SSR" ]; then echo restart > "$SSR" 2>/dev/null; sleep 12; fi
echo "-- dmesg framer/laddr tail --"; dmesg | grep -iE 'slim|laddr|logical address|framer|adsp' | tail -8
echo "=== DONE (verify stock md5 restored; if anything is off, reboot UT) ==="
} >> "$RES" 2>&1; sync
cat "$RES"
