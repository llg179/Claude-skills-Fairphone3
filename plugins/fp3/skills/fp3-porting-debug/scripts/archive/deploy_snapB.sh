#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# deploy_snapA.sh — Step-1 (SNPB) COLD-BOOT deploy (boot-time-once event).
# Deploy signed patch -> reboot -> cold boot -> read SMEM leaf/handle -> restore -> heal.

# Config lives in fp3-env.sh; every value there has a documented default.
for _d in "$(dirname "$0")" "$(dirname "$0")/.." "$(dirname "$0")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

set -uo pipefail
cd "$(dirname "$0")"
DEV=fp3@$FP3_DEV_IP; PW="$FP3_PW"
SSHO="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o GlobalKnownHostsFile=/dev/null -o ConnectTimeout=8 -o PreferredAuthentications=password -o PubkeyAuthentication=no"
SSH="sshpass -p $PW ssh $SSHO $DEV"
SCP="sshpass -p $PW scp $SSHO"
FWDIR=/lib/firmware/qcom/msm8953/fairphone/fp3
SIG=$FP3_ROOT/adsp-snapB-signed.mbn
r(){ timeout 30 $SSH "echo $PW | sudo -S bash -c \"$1\"" 2>/dev/null; }
do_reboot(){ # synchronous: issue reboot, connection drops (ignore rc)
  timeout 20 $SSH "echo $PW | sudo -S systemctl reboot" >/dev/null 2>&1 || true
}
waitdown(){ # confirm the device actually went DOWN (proves a real reboot)
  for i in $(seq 1 30); do
    if ! timeout 6 $SSH "true" >/dev/null 2>&1; then echo "[down after ${i}]"; return 0; fi
    sleep 2
  done
  echo "ERROR: device never went down (reboot failed)"; return 1
}
waitup(){ # poll SSH until device answers (fresh NCM link after reboot)
  for i in $(seq 1 50); do
    if timeout 10 $SSH "true" >/dev/null 2>&1; then echo "[up after ${i} tries]"; return 0; fi
    sleep 5
  done
  echo "ERROR: device did not come back"; return 1
}

echo "== [1] preflight =="
r "md5sum $FWDIR/adsp.mbn; ls $FWDIR/adsp.mbn.stockbak"

echo "== [2] deploy patched (SNPB) =="
$SCP "$SIG" "$DEV:/tmp/adsp-snapB-signed.mbn" >/dev/null 2>&1
r "cp /tmp/adsp-snapB-signed.mbn $FWDIR/adsp.mbn; echo -n patched=; md5sum $FWDIR/adsp.mbn"

echo "== [3] COLD reboot =="
do_reboot
waitdown || { echo "DONE -> FAIL(no-reboot)"; exit 1; }
echo "   waiting for cold boot..."
waitup || { echo "DONE -> FAIL(no-boot)"; exit 1; }
sleep 12   # let ADSP finish bring-up + write stash

echo "== [4] read SMEM (SNPB stash) =="
$SCP smem_snapB_read.py "$DEV:/tmp/smem_snapB_read.py" >/dev/null 2>&1
echo "---- SNPB READOUT ----"
r "python3 /tmp/smem_snapB_read.py"
echo "----------------------"

echo "== [5] restore stock + heal reboot =="
r "cp $FWDIR/adsp.mbn.stockbak $FWDIR/adsp.mbn; echo -n restored=; md5sum $FWDIR/adsp.mbn"
do_reboot
waitdown || { echo "DONE -> WARN(heal-no-reboot: stock on disk, will load next boot)"; exit 0; }
waitup || { echo "DONE -> WARN(heal-boot-slow)"; exit 0; }
r "echo -n healed_state=; cat /sys/class/remoteproc/remoteproc2/state; md5sum $FWDIR/adsp.mbn"
echo "DONE -> OK"
