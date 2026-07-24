#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# deploy_m4.sh — NON-crashing SMEM exfil. Deploy patched fw, SSR-reload (ADSP boots
# normally, trampoline writes SMEM item-469 + continues), read SMEM PA 0x86302a70,
# restore stock, heal. Every ssh has a hard timeout so a stuck SSR can't hang us.

# Config lives in fp3-env.sh; every value there has a documented default.
for _d in "$(dirname "$0")" "$(dirname "$0")/.." "$(dirname "$0")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

set -uo pipefail
cd "$(dirname "$0")"
DEV=fp3@$FP3_DEV_IP; PW="$FP3_PW"
SSHO="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o GlobalKnownHostsFile=/dev/null -o ConnectTimeout=8"
SSH="sshpass -p $PW ssh $SSHO $DEV"
SCP="sshpass -p $PW scp $SSHO"
FWDIR=/lib/firmware/qcom/msm8953/fairphone/fp3
RP=/sys/class/remoteproc/remoteproc2
SIG=adsp-m4-signed.mbn
PA=0x86302a70
r(){ timeout 25 $SSH "echo $PW | sudo -S bash -c \"$1\"" 2>/dev/null; }

echo "== baseline SMEM @ $PA (stock, before) =="
$SCP smem_peek.py "$DEV:/tmp/" >/dev/null 2>&1
r "python3 /tmp/smem_peek.py $PA 32"

echo "== deploy patched (non-crashing) =="
$SCP "$SIG" "$DEV:/tmp/$SIG" >/dev/null 2>&1
r "cp /tmp/$SIG $FWDIR/adsp.mbn; md5sum $FWDIR/adsp.mbn"

echo "== SSR reload =="
r "echo stop > $RP/state"; sleep 1; r "echo start > $RP/state"; sleep 5
r "echo -n state=; cat $RP/state"

echo "== read SMEM @ $PA (expect word0 magic 37 00 de c0 + FRM_STAT...) =="
r "python3 /tmp/smem_peek.py $PA 32"

echo "== restore stock + heal =="
r "cp $FWDIR/adsp.mbn.stockbak $FWDIR/adsp.mbn"
r "echo stop > $RP/state"; sleep 1; r "echo start > $RP/state"; sleep 3
r "echo -n healed=; cat $RP/state; md5sum $FWDIR/adsp.mbn"
