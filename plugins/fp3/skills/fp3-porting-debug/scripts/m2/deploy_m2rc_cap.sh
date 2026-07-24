#!/bin/bash
# deploy_m2rc_cap.sh — m2rc (carveout) crash-capture with a systemd-run detached
# on-device grab (folyt.33). m2rc boots clean; the grab saves the coredump to
# persistent $HOME in <1s, surviving the SSH drop + any panic-reboot.

# Config lives in fp3-env.sh; every value there has a documented default.
for _d in "$(dirname "$0")" "$(dirname "$0")/.." "$(dirname "$0")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

set -uo pipefail
DEV=fp3@$FP3_DEV_IP
SSH="sshpass -p "$FP3_PW" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8"
SCP="sshpass -p "$FP3_PW" scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
FWDIR=/lib/firmware/qcom/msm8953/fairphone/fp3
FW=$FWDIR/adsp.mbn
RP=/sys/class/remoteproc/remoteproc2
PATCHED=adsp-m2rc-signed.mbn
cd "$(dirname "$0")"
sudos(){ timeout 30 $SSH $DEV "echo "$FP3_PW" | sudo -S $1" 2>/dev/null | grep -vi 'warning\|password'; }
wait_ssh(){ local t=0; while [ $t -lt "$1" ]; do $SSH $DEV true 2>/dev/null && return 0; sleep 6; t=$((t+6)); done; return 1; }

echo "== [0] preflight =="; $SSH $DEV true 2>/dev/null || { echo unreachable; exit 1; }
echo "  fw8=$(sudos "md5sum $FW"|grep -o '^[0-9a-f]\{8\}') adsp=$(sudos "cat $RP/state")"
sudos "test -f ${FW}.stockbak || cp $FW ${FW}.stockbak" >/dev/null

echo "== [1] push fw + on-device capture script =="
$SCP "$PATCHED" "$DEV:/tmp/$PATCHED" >/dev/null && $SCP m2rc_cap_ondev.sh "$DEV:/tmp/m2rc_cap_ondev.sh" >/dev/null || { echo scp-fail; exit 1; }
sudos "cp /tmp/m2rc_cap_ondev.sh $HOME/m2rc_cap_ondev.sh" >/dev/null
sudos "chmod +x $HOME/m2rc_cap_ondev.sh" >/dev/null
sudos "cp /tmp/$PATCHED $FW" >/dev/null
sudos "sync" >/dev/null
echo "  swapped fw8=$(sudos "md5sum $FW"|grep -o '^[0-9a-f]\{8\}') (patched=68910a40)"

echo "== [2] CLEAN reboot (from running pmOS; cave writes carveout during bring-up) =="
timeout 15 $SSH $DEV "echo "$FP3_PW" | sudo -S reboot" 2>/dev/null; echo "  reboot issued"; sleep 30
if wait_ssh 240; then echo "  [OK] pmOS back adsp=$(sudos "cat $RP/state") fw8=$(sudos "md5sum $FW"|grep -o '^[0-9a-f]\{8\}')"
else echo "  [!] slow/flaky; continuing to grab loop anyway"; fi

echo "== [3] systemd-run detached capture (fires crash, grabs to $HOME, restores stock) =="
sudos "systemctl reset-failed m2rccap 2>/dev/null; systemd-run --unit=m2rccap --collect $HOME/m2rc_cap_ondev.sh" 2>&1 | sed 's/^/    /'
echo "  launched; crash may drop link/panic-reboot. Retrieving $HOME/m2rc.coredump..."

echo "== [4] retrieve coredump (survives reboot) =="
sleep 15; GOT=0
for i in $(seq 1 24); do
  if wait_ssh 10; then
    SZ=$(sudos "stat -c %s $HOME/m2rc.coredump 2>/dev/null")
    echo "  [t$i] up: coredump=${SZ:-none}B adsp=$(sudos "cat $RP/state") fw8=$(sudos "md5sum $FW"|grep -o '^[0-9a-f]\{8\}')"
    if [ -n "$SZ" ] && [ "$SZ" -gt 1000000 ] 2>/dev/null; then
      $SCP "$DEV:$HOME/m2rc.coredump" ./m2rc.coredump >/dev/null && { echo "  PULLED ./m2rc.coredump ($(wc -c < ./m2rc.coredump)B)"; GOT=1; sudos "cat $HOME/m2rc-cap.log" | sed 's/^/    /'; break; }
    fi
  else echo "  [t$i] unreachable (booting/panic-reboot)..."; fi
  sleep 10
done
[ "$GOT" = 1 ] || echo "  [!] not retrieved yet; $HOME/m2rc.coredump persists for later."
echo "== [5] heal check =="
if wait_ssh 60; then echo "  fw8=$(sudos "md5sum $FW"|grep -o '^[0-9a-f]\{8\}') (stock=3ed6924d) adsp=$(sudos "cat $RP/state")"; sudos "rm -f $HOME/m2rc.coredump" >/dev/null; fi
echo "DONE"
