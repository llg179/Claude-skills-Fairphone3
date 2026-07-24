#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# IDLE → TWRP TÖLTÉS.  A mainline pmOS kernelben NINCS FP3/PMI632 charger+fuelgauge
# driver (csak qcom,pmi632-typec látszik, CURRENT_NOW=0) → pmOS-ben az akku NEM tölt.
# A downstream TWRP (4.9 kernel, qpnp-smb5+qpnp-qg) rendesen tölt. Ezért: ha nem
# használod a telefont, ezzel TWRP-be váltasz (boot_b), ahol töltődik.
#
# Mechanizmus: TWRP a boot_b-re (boot_a/lk2nd/pmOS ÉRINTETLEN) + set_active b + reboot.
# Vissza pmOS-re:  ./to-pmos.sh
#
# usage: to-twrp.sh        (pmOS-ből vagy fastbootból is indítható)
set -uo pipefail
source "$(dirname "$0")/fp3-env.sh"
[ -f "$TWRP_IMG" ] || { echo "nincs TWRP image: $TWRP_IMG"; exit 1; }

ssh_pmos(){ sshpass -p "$FP3_PW" ssh -o StrictHostKeyChecking=no \
  -o UserKnownHostsFile=/dev/null -o ConnectTimeout=6 "fp3@$FP3_SSH_IP" "$@" 2>/dev/null; }

# 1+2) Fastbootba jutás — pmOS→fastboot FLAKY (lk2nd néha visszabootol pmOS-be), ezért
#       TÖBB PRÓBA: reboot bootloader → 90s várás fastbootra; ha pmOS jött vissza, újra.
get_fastboot(){
  local attempt
  for attempt in 1 2 3 4; do
    have_fastboot && return 0
    if ping -c1 -W2 "$FP3_SSH_IP" >/dev/null 2>&1; then
      log "to-twrp: pmOS fut → reboot bootloader (SSH, próba $attempt)"
      ssh_pmos "echo $FP3_PW | sudo -S reboot bootloader" || true
    elif have_recovery; then
      log "to-twrp: TWRP/recovery → reboot bootloader (adb, próba $attempt)"
      adbr reboot bootloader 2>&1 | tail -1
    fi
    # 90s ablak fastbootra (lk2nd-fastboot is jó)
    wait_state fastboot 90 && return 0
    log "to-twrp: próba $attempt nem ért fastbootot; ha pmOS visszajött, újrapróba"
    # ha pmOS visszabootolt, várjuk hogy elérhető legyen az újabb SSH-rebootig
    local i; for i in $(seq 1 30); do ping -c1 -W2 "$FP3_SSH_IP" >/dev/null 2>&1 && break; sleep 2; done
  done
  return 1
}
if ! get_fastboot; then
  echo "NEM sikerült fastbootot elérni 4 próbából. Kézzel: bootloader mód, majd futtasd újra."
  exit 1
fi

# 3) TWRP → boot_b (frissen flashelve a slot bootable lesz), aktiválás, reboot
log "to-twrp: flash TWRP→boot_b ; set_active b ; reboot"
fb flash boot_b "$TWRP_IMG" 2>&1 | tail -3
fb set_active b   2>&1 | tail -1
fb reboot         2>&1 | tail -1
echo
echo "✅ TWRP indul a boot_b-ről → az akku ott TÖLT (downstream charger)."
echo "   Vissza pmOS-re:  ./to-pmos.sh   (vagy: fastbootban set_active a + reboot)"
