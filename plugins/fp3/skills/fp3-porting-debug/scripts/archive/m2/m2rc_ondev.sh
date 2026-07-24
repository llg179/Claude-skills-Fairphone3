#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-or-later
# m2rc_ondev.sh — runs ON the pmOS device as root, nohup'd (survives SSH drop +
# a possible panic-reboot 120s later). Assumes the PATCHED fw is ALREADY
# cold-booted & running (cave stash already written to the ADSP carveout during
# bring-up). Fires ONE crash and grabs the coredump to PERSISTENT $HOME
# BEFORE anything can reboot (cat of ~17MB is <1s). Then restores stock.

# Config lives in fp3-env.sh; every value there has a documented default.
for _d in "$(dirname "$0")" "$(dirname "$0")/.." "$(dirname "$0")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

FW=/lib/firmware/qcom/msm8953/fairphone/fp3/adsp.mbn
RP=/sys/class/remoteproc/remoteproc2
DBG=/sys/kernel/debug/remoteproc/remoteproc2
OUT=$HOME/m2rc.coredump
LOG=$HOME/m2rc-ondev.log
exec >>"$LOG" 2>&1
echo "=== $(date) START adsp=$(cat $RP/state) fw=$(md5sum $FW|cut -c1-8) ==="
rm -f "$OUT"
echo enabled > $RP/coredump; echo enabled > $RP/recovery
for d in /sys/class/devcoredump/devcd*; do echo 1 > "$d/data" 2>/dev/null; done
echo "arm: coredump=$(cat $RP/coredump) recovery=$(cat $RP/recovery); firing crash"
echo 1 > $DBG/crash
# grab ASAP to persistent storage
i=0
while [ $i -lt 60 ]; do
  CD=$(ls -d /sys/class/devcoredump/devcd*/data 2>/dev/null | head -1)
  if [ -n "$CD" ]; then
    cat "$CD" > "$OUT"; sync
    echo "SAVED $(stat -c %s "$OUT" 2>/dev/null) B -> $OUT"
    echo 1 > "$CD" 2>/dev/null
    break
  fi
  i=$((i+1)); sleep 0.5
done
[ -s "$OUT" ] && echo "GRABBED OK" || echo "NO COREDUMP APPEARED"
# restore stock (so any later reboot cold-boots clean stock)
cp ${FW}.stockbak $FW; sync; echo default > $RP/coredump
echo "restored fw=$(md5sum $FW|cut -c1-8) (stock=3ed6924d)"
echo "=== $(date) DONE ==="
