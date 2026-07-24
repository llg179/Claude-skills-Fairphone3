#!/bin/bash
# snapCKB8 SSR-RELOAD deploy (dead side, reboot-free). Zero stash -> swap adsp.mbn -> stop/start
# ADSP remoteproc (re-request_firmware + re-init => cave fires) -> read SMEM -> restore stock + SSR heal.

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
SIG=$FP3_ROOT/adsp-snapCKB8-signed.mbn
r(){ timeout 40 $SSH "echo $PW | sudo -S bash -c \"$1\"" 2>/dev/null; }

echo "== [0] identify ADSP remoteproc =="
RP=$(r 'for d in /sys/class/remoteproc/remoteproc*; do n=$(cat $d/name 2>/dev/null); echo "$(basename $d) $n"; done')
echo "$RP"
ADSP=$(echo "$RP" | awk '/adsp/{print $1; exit}')
[ -z "$ADSP" ] && ADSP=remoteproc2
echo "  -> using $ADSP"

echo "== [1] preflight =="
r "md5sum $FWDIR/adsp.mbn; ls $FWDIR/adsp.mbn.stockbak; cat /sys/class/remoteproc/$ADSP/state"

echo "== [2] zero SMEM stash (0x86300000+0x2ab0, 0x30 B) =="
r "python3 - <<'PY'
import mmap,struct
f=open('/dev/mem','r+b'); m=mmap.mmap(f.fileno(),0x1000,offset=0x86302000)
m[0xab0:0xab0+0x30]=b'\x00'*0x30; m.flush(); m.close(); f.close(); print('zeroed')
PY"

echo "== [3] deploy patched CKB8 =="
$SCP "$SIG" "$DEV:/tmp/adsp-snapCKB8-signed.mbn" >/dev/null 2>&1
r "cp /tmp/adsp-snapCKB8-signed.mbn $FWDIR/adsp.mbn; sync; echo -n patched=; md5sum $FWDIR/adsp.mbn"

echo "== [4] SSR reload =="
r "echo stop > /sys/class/remoteproc/$ADSP/state; sleep 2; cat /sys/class/remoteproc/$ADSP/state"
r "echo start > /sys/class/remoteproc/$ADSP/state; sleep 6; cat /sys/class/remoteproc/$ADSP/state"

echo "== [5] read SMEM (CKB8 stash) =="
$SCP smem_snapCKB8_read.py "$DEV:/tmp/smem_snapCKB8_read.py" >/dev/null 2>&1
echo "---- CKB8 READOUT (pmOS/dead) ----"
r "python3 /tmp/smem_snapCKB8_read.py"
echo "----------------------------------"
echo "== [5b] framer/dmesg context =="
r "dmesg | grep -iE 'adsp|slim|framer|remoteproc' | tail -8"

echo "== [6] restore stock + SSR heal =="
r "cp $FWDIR/adsp.mbn.stockbak $FWDIR/adsp.mbn; sync; echo -n restored=; md5sum $FWDIR/adsp.mbn"
r "echo stop > /sys/class/remoteproc/$ADSP/state; sleep 2; echo start > /sys/class/remoteproc/$ADSP/state; sleep 6; echo -n healed_state=; cat /sys/class/remoteproc/$ADSP/state"
echo "DONE -> OK"
