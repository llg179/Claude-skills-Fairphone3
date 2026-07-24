#!/bin/bash
# snapCGP2 COLD-BOOT deploy (boot-time-once leaf event, fixed-VA stash).
# Deploy signed patch -> cold reboot -> read SMEM CGP stash -> framer snapshot -> restore -> heal.

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
SIG=$FP3_ROOT/adsp-snapCKB5-signed.mbn
r(){ timeout 30 $SSH "echo $PW | sudo -S bash -c \"$1\"" 2>/dev/null; }
do_reboot(){ timeout 20 $SSH "echo $PW | sudo -S systemctl reboot" >/dev/null 2>&1 || true; }
waitdown(){ for i in $(seq 1 30); do
    if ! timeout 6 $SSH "true" >/dev/null 2>&1; then echo "[down after ${i}]"; return 0; fi
    sleep 2; done; echo "ERROR: never went down"; return 1; }
waitup(){ for i in $(seq 1 60); do
    if timeout 10 $SSH "true" >/dev/null 2>&1; then echo "[up after ${i}]"; return 0; fi
    sleep 5; done; echo "ERROR: did not come back"; return 1; }

echo "== [1] preflight =="
r "md5sum $FWDIR/adsp.mbn; ls $FWDIR/adsp.mbn.stockbak; df -h / | tail -1"
echo "== [2] deploy patched CGP =="
$SCP "$SIG" "$DEV:/tmp/adsp-snapCKB5-signed.mbn" >/dev/null 2>&1
r "cp /tmp/adsp-snapCKB5-signed.mbn $FWDIR/adsp.mbn; sync; echo -n patched=; md5sum $FWDIR/adsp.mbn"
echo "== [2b] disk guardrail (journal vacuum + df gate) =="
r "journalctl --vacuum-size=30M 2>/dev/null | tail -1; df -h / | tail -1"
echo "== [3] COLD reboot =="
do_reboot
waitdown || { echo "DONE -> FAIL(no-reboot)"; exit 1; }
echo "   waiting for cold boot..."
waitup || { echo "DONE -> FAIL(no-boot)"; exit 1; }
sleep 12
echo "== [4] read SMEM (CGP stash) =="
$SCP smem_snapCKB5_read.py "$DEV:/tmp/smem_snapCKB5_read.py" >/dev/null 2>&1
echo "---- CGP READOUT ----"
r "python3 /tmp/smem_snapCKB5_read.py"
echo "----------------------"
echo "== [4b] framer status (context) =="
r "python3 /tmp/frm.py hwl4-ctx 2>/dev/null; dmesg | grep -iE 'slim|framer|laddr|capability|adsp is now' | tail -6"
echo "== [5] restore stock + heal =="
r "cp $FWDIR/adsp.mbn.stockbak $FWDIR/adsp.mbn; sync; echo -n restored=; md5sum $FWDIR/adsp.mbn"
do_reboot
waitdown || { echo "DONE -> WARN(heal-no-reboot: stock on disk)"; exit 0; }
waitup || { echo "DONE -> WARN(heal-boot-slow)"; exit 0; }
r "echo -n healed_state=; cat /sys/class/remoteproc/remoteproc2/state; md5sum $FWDIR/adsp.mbn"
echo "DONE -> OK"
