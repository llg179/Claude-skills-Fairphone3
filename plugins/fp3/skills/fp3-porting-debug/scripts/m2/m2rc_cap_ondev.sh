#!/bin/sh
# m2rc_cap_ondev.sh — runs on device via systemd-run (detached; survives SSH
# drop + a possible panic-reboot). Assumes the m2rc PATCHED fw is ALREADY
# cold-booted (cave wrote rc to carveout 0xf0ca0000 during bring-up). Fires ONE
# crash, grabs the coredump to PERSISTENT $HOME in <1s (before any reboot),
# then restores stock.

# Config lives in fp3-env.sh; every value there has a documented default.
for _d in "$(dirname "$0")" "$(dirname "$0")/.." "$(dirname "$0")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

FW=/lib/firmware/qcom/msm8953/fairphone/fp3/adsp.mbn
RP=/sys/class/remoteproc/remoteproc2
DBG=/sys/kernel/debug/remoteproc/remoteproc2
OUT=$HOME/m2rc.coredump
LOG=$HOME/m2rc-cap.log
: > "$LOG"; exec >>"$LOG" 2>&1
echo "=== $(date) START adsp=$(cat $RP/state) fw=$(md5sum $FW|cut -c1-8) ==="
rm -f "$OUT"
echo enabled > $RP/coredump; echo enabled > $RP/recovery
for d in /sys/class/devcoredump/devcd*; do echo 1 > "$d/data" 2>/dev/null; done
echo "arm coredump=$(cat $RP/coredump) recovery=$(cat $RP/recovery); firing crash"
echo 1 > $DBG/crash
i=0
while [ $i -lt 80 ]; do
  CD=$(ls -d /sys/class/devcoredump/devcd*/data 2>/dev/null | head -1)
  if [ -n "$CD" ]; then cat "$CD" > "$OUT"; sync; echo "SAVED $(stat -c %s "$OUT" 2>/dev/null)B -> $OUT"; echo 1 > "$CD" 2>/dev/null; break; fi
  i=$((i+1)); sleep 0.4
done
[ -s "$OUT" ] && echo GRABBED || echo NO-COREDUMP
cp ${FW}.stockbak $FW; sync; echo default > $RP/coredump
echo "restored fw=$(md5sum $FW|cut -c1-8); === $(date) DONE ==="
