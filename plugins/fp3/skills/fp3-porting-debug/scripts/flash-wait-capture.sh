#!/bin/bash
# Wait for the device to appear in fastboot (user puts it there with Power+VolDown),
# then flash the already-built rootfs (pmb install already ran) to system_b, boot
# pmOS, and capture the power_req/framer bring-up result. Fully autonomous once the
# device reaches fastboot. Logs everything to $LOG.

# Config lives in fp3-env.sh; every value there has a documented default.
for _d in "$(dirname "$0")" "$(dirname "$0")/.." "$(dirname "$0")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

set -uo pipefail
cd $FP3_PMOS
PMB=./pmb
LOG=$FP3_PMOS/flash-capture-power.log
OUT=$FP3_PMOS/pmos-slimtest-power-$(date +%H%M)
mkdir -p "$OUT"
FB(){ echo "$FP3_PW" | sudo -S fastboot "$@" 2>&1; }
SSH(){ timeout "${2:-30}" sshpass -p "$FP3_PW" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=5 fp3@$FP3_DEV_IP "echo "$FP3_PW" | sudo -S sh -c '$1'" 2>/dev/null; }
say(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }

say "=== waiting up to 40 min for FASTBOOT (put device in fastboot: Power+VolDown) ==="
GOT=""
for i in $(seq 1 400); do
  if echo "$FP3_PW" | sudo -S fastboot devices 2>/dev/null | grep -q fastboot; then GOT=fb; break; fi
  # also accept: device already booted pmOS (ssh works) -> reboot to bootloader
  if timeout 6 sshpass -p "$FP3_PW" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=4 fp3@$FP3_DEV_IP true 2>/dev/null; then
     say "pmOS ssh reachable -> reboot bootloader"; SSH 'reboot bootloader' 10; sleep 20; continue
  fi
  sleep 6
done
[ "$GOT" = fb ] || { say "TIMEOUT waiting for fastboot"; exit 1; }
say "FASTBOOT detected: $(echo "$FP3_PW"|sudo -S fastboot devices 2>/dev/null)"

say "=== flash rootfs -> system_b (image from prior pmb install) ==="
FB set_active b | tail -1 | tee -a "$LOG"
yes '' | "$PMB" flasher flash_rootfs --partition system_b 2>&1 | tail -12 | tee -a "$LOG"
FB set_active b | tail -1 | tee -a "$LOG"
say "=== reboot ==="
FB reboot | tail -1 | tee -a "$LOG"

say "=== wait pmOS SSH (up to ~4min) ==="
UP=""
for i in $(seq 1 60); do
  r=$(timeout 8 sshpass -p "$FP3_PW" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=4 fp3@$FP3_DEV_IP 'uname -r' 2>/dev/null)
  [ -n "$r" ] && { say "pmOS UP ($r) @ ~$((i*4))s"; UP=1; break; }
  sleep 4
done
[ -n "$UP" ] || { say "pmOS did NOT come up"; exit 2; }

say "=== capture: DBG power_req + framer/NGD + slimbus devices ==="
SSH 'dmesg | grep -iE "DBG power_req|slim|ngd|qmi|capability|laddr|logical|reconf|STATUS=|CFG=|INT_STAT=|master"' | tee "$OUT/dmesg-slim.txt" | tee -a "$LOG"
say "--- /sys/bus/slimbus/devices (codec laddr = framer UP) ---"
SSH 'ls -la /sys/bus/slimbus/devices/ 2>/dev/null; echo "--- sound cards ---"; cat /proc/asound/cards 2>/dev/null' | tee "$OUT/slimbus-devices.txt" | tee -a "$LOG"

# verdict
if SSH 'ls /sys/bus/slimbus/devices/ 2>/dev/null' | grep -qE ':'; then
  say "########## RESULT: SLIMBUS DEVICE ENUMERATED — possible FRAMER UP! ##########"
elif SSH 'dmesg' | grep -q 'capability exchange timed-out'; then
  say "########## RESULT: still 'capability exchange timed-out' — framer NOT up ##########"
else
  say "########## RESULT: inconclusive — see $OUT ##########"
fi
say "=== DONE -> $OUT ==="
