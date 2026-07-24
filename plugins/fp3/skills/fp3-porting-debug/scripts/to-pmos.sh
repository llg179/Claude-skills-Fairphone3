#!/bin/bash
# TWRP → vissza pmOS-re.  set_active a → lk2nd(boot_a) → pmOS bootol.
# (pmOS qbootctl-openrc mark_boot_successful → slot a retry-count visszaáll.)
# usage: to-pmos.sh       (TWRP-ből/recovery-ből vagy fastbootból is)
set -uo pipefail
source "$(dirname "$0")/fp3-env.sh"

# Ha már pmOS fut, nincs teendő
if ping -c1 -W2 "$FP3_SSH_IP" >/dev/null 2>&1; then
  echo "pmOS már fut (ping OK)."; exit 0
fi

# TWRP/recovery → bootloader
if have_recovery; then
  log "to-pmos: TWRP → reboot bootloader (adb)"
  adbr reboot bootloader 2>&1 | tail -1
fi

if ! have_fastboot; then
  echo "fastbootra várok (max 60s)…"
  wait_state fastboot 60 || { echo "NEM jött fastboot. Kézzel: bootloader mód."; exit 1; }
fi

log "to-pmos: set_active a ; reboot"
fb set_active a 2>&1 | tail -1
fb reboot       2>&1 | tail -1
echo
echo "✅ lk2nd(boot_a) → pmOS indul. (~60-90s, USB-net $FP3_DEV_IP)"
echo "   Megj.: pmOS-ben az akku NEM tölt (nincs mainline charger driver)."
