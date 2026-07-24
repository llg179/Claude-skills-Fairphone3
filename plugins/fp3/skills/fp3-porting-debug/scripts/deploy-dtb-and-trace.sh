#!/bin/bash
# Deploy a freshly-built sdm632-fairphone-fp3.dtb to the live pmOS /boot (extlinux
# loads it standalone), reboot, then capture the SLIMbus/NGD bring-up dmesg to diff
# vs the proven downstream working trace. dtb-only = minimal + reversible (.bak kept).

# Config lives in fp3-env.sh; every value there has a documented default.
for _d in "$(dirname "$0")" "$(dirname "$0")/.." "$(dirname "$0")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

set -uo pipefail
SSHP="sshpass -p "$FP3_PW" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
SCPP="sshpass -p "$FP3_PW" scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
HOST=fp3@$FP3_DEV_IP
OUT=${1:-$FP3_PMOS/pmos-backup-20260629/slimbus-resume}
mkdir -p "$OUT"

APK=$(ls -t $FP3_PMOS/work/packages/edge/aarch64/linux-postmarketos-qcom-msm8953-*.apk 2>/dev/null | head -1)
echo "newest apk: $APK"
TMP=$(mktemp -d)
tar xzf "$APK" -C "$TMP" boot/dtbs/qcom/sdm632-fairphone-fp3.dtb 2>/dev/null
DTB="$TMP/boot/dtbs/qcom/sdm632-fairphone-fp3.dtb"
ls -l "$DTB" || { echo "DTB extract FAIL"; exit 1; }

echo "=== phone up? ==="
$SSHP $HOST 'echo UP' 2>&1 | head -1 || { echo "phone not reachable via ssh"; exit 1; }

echo "=== backup current dtb + push new ==="
$SSHP $HOST 'echo "$FP3_PW" | sudo -S sh -c "cp -n /boot/sdm632-fairphone-fp3.dtb /boot/sdm632-fairphone-fp3.dtb.bak; sha256sum /boot/sdm632-fairphone-fp3.dtb"' 2>&1
$SCPP "$DTB" $HOST:/tmp/new.dtb 2>&1 | tail -1
$SSHP $HOST 'echo "$FP3_PW" | sudo -S sh -c "cp /tmp/new.dtb /boot/sdm632-fairphone-fp3.dtb && cp /tmp/new.dtb /boot/dtbs/qcom/sdm632-fairphone-fp3.dtb && sync && echo PUSHED && sha256sum /boot/sdm632-fairphone-fp3.dtb"' 2>&1

echo "=== reboot ==="
$SSHP $HOST 'echo "$FP3_PW" | sudo -S reboot' 2>&1 | head -1
echo "waiting for phone to go down + come back..."
sleep 25
for i in $(seq 1 40); do
  if $SSHP -o ConnectTimeout=5 $HOST 'echo BACK' 2>/dev/null | grep -q BACK; then echo "phone back (i=$i)"; break; fi
  sleep 5
done

echo "=== capture SLIMbus/NGD bring-up dmesg ==="
$SSHP $HOST 'echo "$FP3_PW" | sudo -S dmesg' 2>/dev/null > "$OUT/dmesg-full.txt"
wc -l "$OUT/dmesg-full.txt"
grep -iE 'slim|ngd|laddr|capability|qmi|servreg|pdr|audio_pd|wcd9335|tasha|q6afe|sound|asoc|glink|reconf|framer' "$OUT/dmesg-full.txt" | tee "$OUT/dmesg-slim.txt" | tail -80
echo "=== slimbus bus devices (codec enumerated => framer UP) ==="
$SSHP $HOST 'ls -la /sys/bus/slimbus/devices/; echo ---drv---; ls /sys/bus/slimbus/drivers/' 2>&1 | tee "$OUT/slimbus-devices.txt"
echo "=== sound cards ==="
$SSHP $HOST 'cat /proc/asound/cards' 2>&1 | tee "$OUT/asound-cards.txt"
echo "=== DONE -> $OUT ==="