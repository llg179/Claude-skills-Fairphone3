#!/bin/bash
# Runs ON pmOS (slot_b). Deploys FRS8 via SSR-reload (no reboot), scans the framer ctx for LPASS pointers,
# writes the readout DIRECTLY to a synced disk file (NOT a { }|tee pipe — folyt.134: the pipe loses late
# lines if the device resets mid-run), then restores stock + heals.
# ★ PREFLIGHT GATE (folyt.134): the SSR measurement campaign itself can disk-full -> reboot-loop, so before
#   doing anything we journal-vacuum to free headroom and ABORT if the rootfs is too full or not clean.

# Config lives in fp3-env.sh; every value there has a documented default.
for _d in "$(dirname "$0")" "$(dirname "$0")/.." "$(dirname "$0")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

set -uo pipefail
FW=/lib/firmware/qcom/msm8953/fairphone/fp3
STAGE=$HOME/frs8-staging
RES=/root/frs8-result.txt
RP=remoteproc2
MIN_FREE_MB=200          # abort if less than this free (folyt.134: 210M looped, 272M stable)

echo "=== $(date) FRS8 onboard run (DEAD side) ===" > "$RES"; sync
{
echo "-- [preflight] free space + journal-vacuum + clean-rootfs gate --"
journalctl --vacuum-size=30M 2>&1 | tail -1
FREE_MB=$(df -Pm / | awk 'NR==2{print $4}')
echo "free after vacuum: ${FREE_MB}M (need >= ${MIN_FREE_MB}M)"
DIRTY=$(dmesg 2>/dev/null | grep -c 'EXT4-fs .*recovery\|orphan')
echo "rootfs recovery/orphan markers in dmesg: $DIRTY"
if [ "${FREE_MB:-0}" -lt "$MIN_FREE_MB" ]; then
  echo "ABORT: insufficient free space (${FREE_MB}M < ${MIN_FREE_MB}M) — free disk cross-slot before running."
  exit 3
fi
echo "-- preflight OK --"
echo "-- state + fw baseline --"; cat /sys/class/remoteproc/$RP/state; md5sum $FW/adsp.mbn $FW/adsp.mbn.stockbak 2>/dev/null
echo "-- zero SMEM stash --"
python3 - <<'PY'
import mmap
f=open('/dev/mem','r+b'); m=mmap.mmap(f.fileno(),0x1000,offset=0x86302000)
m[0xab0:0xab0+0x50]=b'\x00'*0x50; m.close(); f.close(); print('zeroed 0x50 @0x86302ab0')
PY
echo "-- deploy FRS8 --"; cp $STAGE/adsp-snapFRS8-signed.mbn $FW/adsp.mbn; sync; md5sum $FW/adsp.mbn
echo "-- SSR stop --"; echo stop > /sys/class/remoteproc/$RP/state; sleep 2; cat /sys/class/remoteproc/$RP/state
echo "-- SSR start --"; echo start > /sys/class/remoteproc/$RP/state; sleep 8; cat /sys/class/remoteproc/$RP/state
} >> "$RES" 2>&1; sync

# ★ readout written DIRECTLY to the synced file, on its own, BEFORE the heal (folyt.134 lesson)
echo "-- FRS8 ctx-scan readout (DEAD side) --" >> "$RES"
python3 $STAGE/smem_snapFRS8_read.py >> "$RES" 2>&1; sync

{
echo "-- dmesg framer ctx --"; dmesg | grep -iE 'slim-ngd|capability|logical address|adsp' | tail -6
echo "-- restore stock + heal --"; cp $FW/adsp.mbn.stockbak $FW/adsp.mbn; sync
echo stop > /sys/class/remoteproc/$RP/state; sleep 2; echo start > /sys/class/remoteproc/$RP/state; sleep 8
echo -n "healed state="; cat /sys/class/remoteproc/$RP/state; md5sum $FW/adsp.mbn
echo "=== DONE ==="
} >> "$RES" 2>&1; sync
cat "$RES"
