#!/bin/bash
# deploy_m2rc.sh — COLD-BOOT crash-capture of the m2rc DAL-rc trace (folyt.29).
# Framer-bring-up caves need a COLD boot (SSR-warm-reload hangs; folyt.16). Flow:
#   backup stock -> swap patched -> arm coredump+recovery -> REBOOT (cold) ->
#   wait SSH -> verify adsp running -> fire ONE crash -> grab coredump ->
#   RESTORE stock -> reboot -> verify stock. Boot-loop guard: if SSH doesn't
#   return in time, STOP and alert (needs physical fastboot recovery).

# Config lives in fp3-env.sh; every value there has a documented default.
for _d in "$(dirname "$0")" "$(dirname "$0")/.." "$(dirname "$0")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

set -uo pipefail
DEV=fp3@$FP3_DEV_IP
SSH="sshpass -p "$FP3_PW" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8"
SCP="sshpass -p "$FP3_PW" scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
FW=/lib/firmware/qcom/msm8953/fairphone/fp3/adsp.mbn
RP=/sys/class/remoteproc/remoteproc2
CRASH=/sys/kernel/debug/remoteproc/remoteproc2/crash
STOCK_MD5=3ed6924da0017c5027cd78a0998bf8c3
PATCHED=adsp-m2rc-signed.mbn
OUT=m2rc.coredump
cd "$(dirname "$0")"
r(){ $SSH $DEV "echo "$FP3_PW" | sudo -S sh -c '$1'" 2>/dev/null; }
wait_ssh(){ # $1=timeout sec
  local t=0; while [ $t -lt "$1" ]; do
    if $SSH $DEV true 2>/dev/null; then return 0; fi; sleep 5; t=$((t+5)); done; return 1; }

echo "== [0] preflight =="
$SSH $DEV true 2>/dev/null || { echo "ERROR: device not reachable via SSH"; exit 1; }
CUR=$(r "md5sum $FW | cut -d' ' -f1"); echo "current fw md5=$CUR (stock=$STOCK_MD5)"
r "[ -f ${FW}.stockbak ] || cp $FW ${FW}.stockbak"
if [ "$CUR" != "$STOCK_MD5" ]; then
  echo "current fw NOT stock; restoring from stockbak before proceeding"
  r "cp ${FW}.stockbak $FW; sync"
fi

echo "== [1] push + swap patched ($PATCHED md5=$(md5sum $PATCHED|cut -d' ' -f1)) =="
$SCP "$PATCHED" "$DEV:/tmp/$PATCHED" >/dev/null || { echo "ERROR scp"; exit 1; }
r "cp /tmp/$PATCHED $FW; sync; echo -n swapped-md5=; md5sum $FW | cut -d' ' -f1"
echo "== [2] arm coredump+recovery =="
r "echo enabled > $RP/coredump; echo enabled > $RP/recovery; echo -n coredump=; cat $RP/coredump; echo -n recovery=; cat $RP/recovery"

echo "== [3] COLD BOOT (reboot) =="
r "sync; (sleep 1; reboot) >/dev/null 2>&1 &"; sleep 8
echo "   waiting for SSH to drop then return (boot-loop guard 150s)..."
sleep 20
if wait_ssh 150; then echo "   [OK] pmOS back up"; else
  echo "!! BOOT-LOOP / device did not return in 150s."
  echo "!! RECOVERY NEEDED: physical Power(10s)+VolDown -> fastboot; 'sudo fastboot set_active a' -> UT;"
  echo "!! then restore stock adsp.mbn on pmOS rootfs (see skill). ABORTING."
  exit 2
fi

echo "== [4] verify adsp + FRM state, fire ONE crash =="
r "echo -n adsp-state=; cat $RP/state; echo -n fw-md5=; md5sum $FW|cut -d' ' -f1"
r "dmesg | grep -iE 'q6afe|slim|adsp|lpass|wcd9335|capability|framer' | tail -20"
r "for d in /sys/class/devcoredump/devcd*; do echo 1 > \$d/data 2>/dev/null; done"  # clear old
echo "   firing crash..."
r "echo 1 > $CRASH"
echo "== [5] grab coredump =="
GOT=0
for i in $(seq 1 20); do
  CD=$(r "ls -d /sys/class/devcoredump/devcd*/data 2>/dev/null | head -1")
  if [ -n "$CD" ]; then
    r "cat $CD > /tmp/$OUT; chmod 644 /tmp/$OUT; echo 1 > $CD"
    SZ=$(r "stat -c %s /tmp/$OUT 2>/dev/null"); echo "   coredump $SZ bytes"; GOT=1; break
  fi; sleep 2
done
[ "$GOT" = 1 ] && $SCP "$DEV:/tmp/$OUT" "./$OUT" >/dev/null && echo "   pulled ./$OUT ($(wc -c < ./$OUT) B)"

echo "== [6] RESTORE stock + reboot to heal =="
r "cp ${FW}.stockbak $FW; sync; echo default > $RP/coredump; echo -n restored-md5=; md5sum $FW|cut -d' ' -f1"
r "(sleep 1; reboot) >/dev/null 2>&1 &"; sleep 8
if wait_ssh 150; then r "echo -n healed-state=; cat $RP/state; echo -n fw=; md5sum $FW|cut -d' ' -f1"; echo "DONE -> ./$OUT"; else
  echo "!! device did not return after stock-restore reboot; check physically."; exit 3; fi
