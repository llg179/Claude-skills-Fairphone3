#!/bin/bash
# deploy_m2rc_v2.sh — HARDENED cold-boot crash-capture (folyt.30 lessons).
# Fixes vs v1: (a) coredump grabbed to PERSISTENT $HOME by an on-device
# nohup script (survives the SSH drop AND a panic-reboot); (b) stock restored
# by that same on-device script right after the grab; (c) no host-side scp in
# the fragile post-crash window. Host only cold-boots, launches, then retrieves
# $HOME/m2rc.coredump once the device is reachable again.

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
STOCK8=3ed6924d
PATCHED=adsp-m2rc-signed.mbn
cd "$(dirname "$0")"
r(){ $SSH $DEV "echo "$FP3_PW" | sudo -S sh -c \"$1\"" 2>/dev/null; }
wait_ssh(){ local t=0; while [ $t -lt "$1" ]; do $SSH $DEV true 2>/dev/null && return 0; sleep 5; t=$((t+5)); done; return 1; }

echo "== [0] preflight =="
$SSH $DEV true 2>/dev/null || { echo "ERROR: device unreachable"; exit 1; }
echo "current fw8=$(r "md5sum $FW | cut -c1-8") (stock=$STOCK8) adsp=$(r "cat $RP/state")"
r "[ -f ${FW}.stockbak ] || cp $FW ${FW}.stockbak"

echo "== [1] push patched + on-device capture script =="
$SCP "$PATCHED" "$DEV:/tmp/$PATCHED" >/dev/null || { echo "scp fw fail"; exit 1; }
$SCP m2rc_ondev.sh "$DEV:/tmp/m2rc_ondev.sh" >/dev/null || { echo "scp script fail"; exit 1; }
r "cp /tmp/m2rc_ondev.sh $HOME/m2rc_ondev.sh; chmod +x $HOME/m2rc_ondev.sh; cp /tmp/$PATCHED $FW; sync; echo swapped8=\$(md5sum $FW|cut -c1-8)"

echo "== [2] COLD BOOT (cave writes stash during bring-up) =="
r "sync; (sleep 1; reboot) >/dev/null 2>&1 &"; sleep 25
if wait_ssh 180; then echo "  [OK] pmOS back"; else
  echo "!! did not return in 180s -> physical fastboot recovery needed (set_active a -> UT -> e2fsck loopXp1+p2 -> set_active b)."; exit 2; fi
echo "  adsp=$(r "cat $RP/state") fw8=$(r "md5sum $FW|cut -c1-8")"

echo "== [3] launch on-device capture (nohup; fires crash, grabs to $HOME, restores stock) =="
$SSH $DEV "echo "$FP3_PW" | sudo -S sh -c \"setsid nohup $HOME/m2rc_ondev.sh >/dev/null 2>&1 < /dev/null &\"" 2>/dev/null
echo "  launched; the crash may drop the link / panic-reboot. Waiting for coredump to land..."

echo "== [4] retrieve $HOME/m2rc.coredump (survives reboot) =="
sleep 20
GOT=0
for i in $(seq 1 24); do   # up to ~4 min
  if wait_ssh 10; then
    SZ=$(r "stat -c %s $HOME/m2rc.coredump 2>/dev/null")
    ST=$(r "cat $RP/state"); F8=$(r "md5sum $FW|cut -c1-8")
    echo "  [t$((i))] reachable: coredump=${SZ:-none}B adsp=$ST fw8=$F8"
    if [ -n "$SZ" ] && [ "$SZ" -gt 1000000 ] 2>/dev/null; then
      $SCP "$DEV:$HOME/m2rc.coredump" ./m2rc.coredump >/dev/null && { echo "  PULLED ./m2rc.coredump ($(wc -c < ./m2rc.coredump) B)"; GOT=1;
        r "cat $HOME/m2rc-ondev.log"; break; }
    fi
  else echo "  [t$((i))] unreachable (booting/panic-reboot)..."; fi
  sleep 10
done
[ "$GOT" = 1 ] || { echo "!! coredump not retrieved; check $HOME/m2rc-ondev.log after recovery"; }

echo "== [5] final heal check =="
if wait_ssh 60; then
  echo "  fw8=$(r "md5sum $FW|cut -c1-8") (stock=$STOCK8) adsp=$(r "cat $RP/state") up=$(r "uptime | grep -o 'up [^,]*'")"
  r "rm -f $HOME/m2rc.coredump"   # free the 17MB on the tight rootfs
  echo "DONE -> ./m2rc.coredump"
else echo "!! device not reachable at final check."; fi
