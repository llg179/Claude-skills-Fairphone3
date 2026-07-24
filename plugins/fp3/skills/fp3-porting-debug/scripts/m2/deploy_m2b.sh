#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# deploy_m2b.sh — v2 capture: recovery=ENABLED so rproc_coredump() runs (v1 bug:
# recovery=disabled also disabled the dump). Poll fast for the devcd, grab it, then
# restore stock to break the crash-reload loop. Reversible; a few controlled crashes.

# Config lives in fp3-env.sh; every value there has a documented default.
for _d in "$(dirname "$0")" "$(dirname "$0")/.." "$(dirname "$0")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

set -uo pipefail
cd "$(dirname "$0")"
DEV=fp3@$FP3_DEV_IP; PW="$FP3_PW"
SSH="sshpass -p $PW ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o GlobalKnownHostsFile=/dev/null -o ConnectTimeout=8 $DEV"
SCP="sshpass -p $PW scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o GlobalKnownHostsFile=/dev/null"
FWDIR=/lib/firmware/qcom/msm8953/fairphone/fp3
RP=/sys/class/remoteproc/remoteproc2
SIG=adsp-m2-signed.mbn
r() { $SSH "echo $PW | sudo -S bash -c '$1'" 2>/dev/null; }

echo "== arm: coredump=enabled, recovery=ENABLED =="
r "echo enabled > $RP/coredump; echo -n coredump=; cat $RP/coredump"
echo "== deploy patched =="
$SCP "$SIG" "$DEV:/tmp/$SIG" >/dev/null; r "cp /tmp/$SIG $FWDIR/adsp.mbn"
echo "== trigger (SSR): patched boots -> trampoline writes marker + faults -> coredump =="
r "echo stop > $RP/state; sleep 1; echo start > $RP/state"

echo "== poll for devcd (grab first, then restore stock to stop the loop) =="
GOT=""
for i in $(seq 1 40); do
  CD=$(r "ls -d /sys/class/devcoredump/devcd* 2>/dev/null | head -1")
  if [ -n "$CD" ]; then
    echo "  devcd @ $CD (poll $i)"
    r "cp $FWDIR/adsp.mbn.stockbak $FWDIR/adsp.mbn"   # restore FIRST so next reload is clean
    r "cat $CD/data > /tmp/adsp-m2.coredump; chmod 644 /tmp/adsp-m2.coredump; ls -l /tmp/adsp-m2.coredump"
    r "echo 1 > $CD/data 2>/dev/null || true"
    GOT=1; break
  fi
  sleep 0.3
done

echo "== heal: stock restored, coredump=default, SSR clean =="
r "cp $FWDIR/adsp.mbn.stockbak $FWDIR/adsp.mbn; echo default > $RP/coredump; echo stop > $RP/state; sleep 1; echo start > $RP/state; sleep 3; echo -n state=; cat $RP/state; md5sum $FWDIR/adsp.mbn"

if [ -n "$GOT" ]; then
  $SCP "$DEV:/tmp/adsp-m2.coredump" ./adsp-m2.coredump >/dev/null && echo "pulled $(wc -c < ./adsp-m2.coredump) bytes"
else
  echo "!! still no devcd after ~12s. qcom_q6v5_pas may not register dump segments."
  echo "   dmesg tail:"; r "dmesg | tail -20"
fi
