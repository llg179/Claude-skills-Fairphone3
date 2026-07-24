#!/bin/bash
# Runs ON pmOS (slot_b). Deploys CKB9, SSR-reloads, reads SMEM to BOTH stdout and a disk file
# (/root/ckb9-result.txt) so a flaky USB link can't lose the measurement, then restores stock + heals.
set -uo pipefail
FWDIR=/lib/firmware/qcom/msm8953/fairphone/fp3
STAGE=/root/ckb9-staging
RES=/root/ckb9-result.txt
RP=remoteproc2
{
echo "=== $(date) CKB9 onboard run ==="
echo "-- preflight --"; cat /sys/class/remoteproc/$RP/state; md5sum $FWDIR/adsp.mbn; df -h / | tail -1
echo "-- zero SMEM stash --"
python3 - <<'PY'
import mmap
f=open('/dev/mem','r+b'); m=mmap.mmap(f.fileno(),0x1000,offset=0x86302000)
m[0xab0:0xab0+0x30]=b'\x00'*0x30; m.flush(); m.close(); f.close(); print('zeroed')
PY
echo "-- deploy CKB9 --"; cp $STAGE/adsp-snapCKB9-signed.mbn $FWDIR/adsp.mbn; sync; md5sum $FWDIR/adsp.mbn
echo "-- SSR stop --"; echo stop > /sys/class/remoteproc/$RP/state; sleep 2; cat /sys/class/remoteproc/$RP/state
echo "-- SSR start --"; echo start > /sys/class/remoteproc/$RP/state; sleep 7; cat /sys/class/remoteproc/$RP/state
echo "-- CKB9 SMEM readout (DEAD side) --"; python3 $STAGE/smem_snapCKB9_read.py 2>&1
echo "-- dmesg framer ctx --"; dmesg | grep -iE 'slim-ngd|capability|logical address|adsp' | tail -6
echo "-- restore stock + heal --"; cp $FWDIR/adsp.mbn.stockbak $FWDIR/adsp.mbn; sync
echo stop > /sys/class/remoteproc/$RP/state; sleep 2; echo start > /sys/class/remoteproc/$RP/state; sleep 7
echo -n "healed="; cat /sys/class/remoteproc/$RP/state; md5sum $FWDIR/adsp.mbn
echo "=== DONE ==="
} 2>&1 | tee $RES
