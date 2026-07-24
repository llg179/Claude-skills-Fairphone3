#!/bin/bash
# Runs ON pmOS (slot_b). Deploys FSS2 via SSR-reload (NO reboot), captures the framer STATUS registers
# read from the ADSP's OWN privileged view at the capability-timeout instant on the DEAD side, writes the
# readout DIRECTLY to a synced disk file, then restores stock + heals. Mirrors the proven FST1 onboard.
# Preflight gate (folyt.134) aborts if the rootfs is too full. Coredump disabled to avoid a 17MB devcd.

# Config lives in fp3-env.sh; every value there has a documented default.
for _d in "$(dirname "$0")" "$(dirname "$0")/.." "$(dirname "$0")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

set -uo pipefail
FW=/lib/firmware/qcom/msm8953/fairphone/fp3
STAGE=$HOME/fss2-staging
RES=/root/fss2-result.txt
RP=remoteproc2
MIN_FREE_MB=200

echo "=== $(date) FSS2 onboard run (DEAD side, privileged framer-status snapshot) ===" > "$RES"; sync
{
echo "-- [preflight] free space + journal-vacuum --"
journalctl --vacuum-size=20M 2>&1 | tail -1
FREE_MB=$(df -Pm / | awk 'NR==2{print $4}')
echo "free after vacuum: ${FREE_MB}M (need >= ${MIN_FREE_MB}M)"
if [ "${FREE_MB:-0}" -lt "$MIN_FREE_MB" ]; then
  echo "ABORT: insufficient free space (${FREE_MB}M < ${MIN_FREE_MB}M)"; exit 3
fi
echo "-- coredump DISABLED guard (avoid 17MB devcd on any crash) --"
echo disabled > /sys/class/remoteproc/$RP/coredump 2>/dev/null; cat /sys/class/remoteproc/$RP/coredump 2>/dev/null
echo "-- state + fw baseline (expect stock md5 3ed6924d... on adsp.mbn before deploy) --"
cat /sys/class/remoteproc/$RP/state; md5sum $FW/adsp.mbn $FW/adsp.mbn.stockbak 2>/dev/null
echo "-- zero SMEM stash (0x60 @ 0x86302ab0) --"
python3 - <<'PY'
import mmap
f=open('/dev/mem','r+b'); m=mmap.mmap(f.fileno(),0x1000,offset=0x86302000)
m[0xab0:0xab0+0x60]=b'\x00'*0x60; m.close(); f.close(); print('zeroed 0x60 @0x86302ab0')
PY
echo "-- deploy FSS2 --"; cp $STAGE/adsp-snapFSS2-signed.mbn $FW/adsp.mbn; sync; md5sum $FW/adsp.mbn
echo "-- SSR stop --"; echo stop > /sys/class/remoteproc/$RP/state; sleep 2; cat /sys/class/remoteproc/$RP/state
echo "-- SSR start --"; echo start > /sys/class/remoteproc/$RP/state; sleep 9; cat /sys/class/remoteproc/$RP/state
} >> "$RES" 2>&1; sync

echo "-- FSS2 privileged framer-status trace (DEAD side) --" >> "$RES"
python3 $STAGE/smem_snapFSS2_read.py >> "$RES" 2>&1; sync

{
echo "-- dmesg framer/ngd/capability tail --"; dmesg | grep -iE 'slim-ngd|capability|logical address|adsp is now up' | tail -8
echo "-- restore stock + heal --"; cp $FW/adsp.mbn.stockbak $FW/adsp.mbn; sync
echo stop > /sys/class/remoteproc/$RP/state; sleep 2; echo start > /sys/class/remoteproc/$RP/state; sleep 9
echo -n "healed state="; cat /sys/class/remoteproc/$RP/state; md5sum $FW/adsp.mbn
echo "=== DONE ==="
} >> "$RES" 2>&1; sync
cat "$RES"
