#!/bin/bash
# deploy_m2rcs.sh — NON-CRASHING SMEM-exfil of the DAL-op rc (folyt.31).
# Cold-boot the patched fw (cave writes rc to SMEM 0x2bbf8 during bring-up),
# then read it live via /dev/mem PA 0x8632bbf8. NO crash, NO coredump.
# Uses only synchronous ssh (no fragile backgrounded sudo). Restores stock.

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
PATCHED=adsp-m2rcs-signed.mbn
SMEM_PA=0x8632bbf8
cd "$(dirname "$0")"
sudos(){ timeout 25 $SSH $DEV "echo "$FP3_PW" | sudo -S $1" 2>/dev/null | grep -vi 'warning\|password'; }
wait_ssh(){ local t=0; while [ $t -lt "$1" ]; do $SSH $DEV true 2>/dev/null && return 0; sleep 6; t=$((t+6)); done; return 1; }

echo "== [0] preflight =="; $SSH $DEV true 2>/dev/null || { echo "unreachable"; exit 1; }
echo "  fw8=$(sudos "md5sum $FW" | grep -o '^[0-9a-f]\{8\}') adsp=$(sudos "cat $RP/state")"
sudos "test -f ${FW}.stockbak || cp $FW ${FW}.stockbak" >/dev/null

echo "== [1] push + swap patched =="
$SCP "$PATCHED" "$DEV:/tmp/$PATCHED" >/dev/null || { echo "scp fail"; exit 1; }
$SCP smem_peek.py "$DEV:/tmp/smem_peek.py" >/dev/null
sudos "cp /tmp/$PATCHED $FW; sync" >/dev/null
echo "  swapped fw8=$(sudos "md5sum $FW" | grep -o '^[0-9a-f]\{8\}') (patched=31770d59)"

echo "== [2] COLD BOOT (no crash; cave writes rc to SMEM during bring-up) =="
timeout 15 $SSH $DEV "echo "$FP3_PW" | sudo -S reboot" 2>/dev/null; echo "  reboot issued"
sleep 30
if wait_ssh 200; then echo "  [OK] pmOS back"; else echo "!! no return in 200s -> may be slow/flaky; will retry read loop"; fi

echo "== [3] read SMEM stash @PA $SMEM_PA (no crash) =="
for i in $(seq 1 15); do
  if wait_ssh 12; then
    ST=$(sudos "cat $RP/state"); F8=$(sudos "md5sum $FW" | grep -o '^[0-9a-f]\{8\}')
    HEX=$(sudos "python3 /tmp/smem_peek.py $SMEM_PA 20" | grep "^0x")
    echo "  [t$i] adsp=$ST fw8=$F8"
    echo "$HEX" | sed 's/^/    /'
    if echo "$HEX" | grep -qi '2900705a'; then echo "  >>> MARKER 0x5A700029 FOUND <<<"; break; fi
  else echo "  [t$i] unreachable (booting)..."; fi
  sleep 12
done

echo "== [4] restore stock =="
sudos "cp ${FW}.stockbak $FW; sync" >/dev/null
echo "  fw8=$(sudos "md5sum $FW" | grep -o '^[0-9a-f]\{8\}') (stock=3ed6924d) adsp=$(sudos "cat $RP/state")"
echo "DONE"
