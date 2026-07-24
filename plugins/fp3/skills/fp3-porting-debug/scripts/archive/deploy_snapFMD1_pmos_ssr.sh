#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# snapFMD1 SSR-RELOAD deploy (dead/pmOS side, reboot-free). Framer-MODE decision capture (folyt.130).
# Zero stash(0x60) -> swap adsp.mbn -> stop/start ADSP remoteproc (re-request_firmware + re-init =>
# framer bring-up re-runs => mode-decision cave fires) -> read SMEM -> restore stock + SSR heal.
# SSR is reboot-free so no dirty-rootfs risk; df-gate added (need room for ~11MB signed mbn).

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
SIG=$FP3_ROOT/adsp-snapFMD1-signed.mbn
r(){ timeout 45 $SSH "echo $PW | sudo -S bash -c \"$1\"" 2>/dev/null; }

echo "== [0] connectivity =="
if ! r 'echo alive' | grep -q alive; then echo "ERR: no SSH to pmOS (boot it / flush neigh / replug)"; exit 2; fi

echo "== [0b] identify ADSP remoteproc =="
RP=$(r 'for d in /sys/class/remoteproc/remoteproc*; do n=$(cat $d/name 2>/dev/null); echo "$(basename $d) $n"; done')
echo "$RP"
ADSP=$(echo "$RP" | awk '/adsp/{print $1; exit}'); [ -z "$ADSP" ] && ADSP=remoteproc2
echo "  -> using $ADSP"

echo "== [1] preflight (stock md5, stockbak, state, FREE SPACE) =="
r "md5sum $FWDIR/adsp.mbn; ls -l $FWDIR/adsp.mbn.stockbak 2>/dev/null || echo 'NO stockbak!'; cat /sys/class/remoteproc/$ADSP/state"
FREE=$(r "df -Pk $FWDIR | awk 'NR==2{print \$4}'"); echo "  free KB on fw fs: ${FREE:-?}"
if [ -n "${FREE:-}" ] && [ "$FREE" -lt 30000 ]; then echo "ERR: <30MB free, abort (df-gate)"; exit 3; fi
# ensure a stockbak exists before we overwrite
r "test -f $FWDIR/adsp.mbn.stockbak || { cp $FWDIR/adsp.mbn $FWDIR/adsp.mbn.stockbak && echo 'made stockbak'; }"

echo "== [2] zero SMEM stash (0x86302ab0, 0x60 B) =="
r "python3 - <<'PY'
import mmap
f=open('/dev/mem','r+b'); m=mmap.mmap(f.fileno(),0x1000,offset=0x86302000)
m[0xab0:0xab0+0x60]=b'\x00'*0x60; m.flush(); m.close(); f.close(); print('zeroed 0x60')
PY"

echo "== [3] deploy patched FMD1 =="
$SCP "$SIG" "$DEV:/tmp/adsp-snapFMD1-signed.mbn" >/dev/null 2>&1 || { echo "ERR scp"; exit 4; }
r "cp /tmp/adsp-snapFMD1-signed.mbn $FWDIR/adsp.mbn; sync; echo -n patched=; md5sum $FWDIR/adsp.mbn"

echo "== [4] SSR reload (framer bring-up re-runs) =="
r "echo stop > /sys/class/remoteproc/$ADSP/state; sleep 2; echo -n stopped=; cat /sys/class/remoteproc/$ADSP/state"
r "echo start > /sys/class/remoteproc/$ADSP/state; sleep 7; echo -n started=; cat /sys/class/remoteproc/$ADSP/state"

echo "== [5] read SMEM (FMD1 stash) =="
$SCP smem_snapFMD1_read.py "$DEV:/tmp/smem_snapFMD1_read.py" >/dev/null 2>&1
echo "---- FMD1 READOUT (pmOS/dead) ----"
r "python3 /tmp/smem_snapFMD1_read.py | tee /root/fmd1-result.txt"
echo "----------------------------------"
echo "== [5b] framer/dmesg context =="
r "dmesg | grep -iE 'adsp|slim|framer|remoteproc' | tail -8"

echo "== [6] restore stock + SSR heal =="
r "cp $FWDIR/adsp.mbn.stockbak $FWDIR/adsp.mbn; sync; echo -n restored=; md5sum $FWDIR/adsp.mbn"
r "echo stop > /sys/class/remoteproc/$ADSP/state; sleep 2; echo start > /sys/class/remoteproc/$ADSP/state; sleep 7; echo -n healed_state=; cat /sys/class/remoteproc/$ADSP/state"
echo "DONE -> OK"
