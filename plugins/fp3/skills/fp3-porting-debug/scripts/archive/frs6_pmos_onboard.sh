#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Runs ON pmOS (slot_b). Deploys FRS6 via SSR-reload (no reboot), reads SMEM to BOTH stdout and a disk
# file (/root/frs6-result.txt) so a flaky USB link can't lose the measurement, then restores stock + heals.

# Config lives in fp3-env.sh; every value there has a documented default.
for _d in "$(dirname "$0")" "$(dirname "$0")/.." "$(dirname "$0")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

set -uo pipefail
FW=/lib/firmware/qcom/msm8953/fairphone/fp3
STAGE=$HOME/frs6-staging
RES=/root/frs6-result.txt
RP=remoteproc2
{
echo "=== $(date) FRS6 onboard run (DEAD side) ==="
echo "-- preflight --"; cat /sys/class/remoteproc/$RP/state; md5sum $FW/adsp.mbn $FW/adsp.mbn.stockbak; df -h / | tail -1
echo "-- zero SMEM stash (no flush: EINVAL on /dev/mem offset map) --"
python3 - <<'PY'
import mmap
f=open('/dev/mem','r+b'); m=mmap.mmap(f.fileno(),0x1000,offset=0x86302000)
m[0xab0:0xab0+0x50]=b'\x00'*0x50; m.close(); f.close(); print('zeroed 0x50 @0x86302ab0')
PY
echo "-- deploy FRS6 --"; cp $STAGE/adsp-snapFRS6-signed.mbn $FW/adsp.mbn; sync; md5sum $FW/adsp.mbn
echo "-- SSR stop --"; echo stop > /sys/class/remoteproc/$RP/state; sleep 2; cat /sys/class/remoteproc/$RP/state
echo "-- SSR start --"; echo start > /sys/class/remoteproc/$RP/state; sleep 8; cat /sys/class/remoteproc/$RP/state
echo "-- FRS6 SMEM readout (DEAD side) --"; python3 $STAGE/smem_snapFRS6_read.py 2>&1
echo "-- dmesg framer ctx --"; dmesg | grep -iE 'slim-ngd|capability|logical address|adsp' | tail -6
echo "-- restore stock + heal --"; cp $FW/adsp.mbn.stockbak $FW/adsp.mbn; sync
echo stop > /sys/class/remoteproc/$RP/state; sleep 2; echo start > /sys/class/remoteproc/$RP/state; sleep 8
echo -n "healed state="; cat /sys/class/remoteproc/$RP/state; md5sum $FW/adsp.mbn
echo "=== DONE ==="
} 2>&1 | tee $RES
