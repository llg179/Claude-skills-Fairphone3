#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# DUTY-CYCLE töltés-teszt harness (user-protokoll: rövid pmOS burst → TWRP hő-ellenőrzés).
# Cél: kísérleti charger-kód TERMIKUSAN biztonságos tesztelése felügyelet nélkül.
#   - pmOS-ben fut a (kísérleti) charger; csak rövid ideig (PMOS_DWELL).
#   - TWRP-ben (downstream, megbízható) olvassuk a HŐMÉRSÉKLETET + kapacitást + feszültséget.
#   - Ha temp ≥ ABORT_DECI (°C×10) → LEÁLL, telefon TWRP-ben marad (ott biztonságos + tölt).
# A pmOS-nek NINCS battery node (nincs mainline charger), ezért a delta-mérés TWRP↔TWRP között megy:
#   cap/V a pmOS-dwell ELŐTT és UTÁN (TWRP-ben) → tölt(+) vagy merül(−).
#
# usage: charge-test.sh [cycles] [pmos_dwell_s] [abort_decicelsius]
#   pl. charge-test.sh 6 30 430   = 6 ciklus, 30s pmOS-dwell, abort 43.0°C-nál
set -uo pipefail
cd "$(dirname "$0")"; source ./fp3-env.sh
CYCLES=${1:-6}; PMOS_DWELL=${2:-30}; ABORT=${3:-430}
CL=$FP3_ROOT/charger-port/charge-test.log
mkdir -p "$FP3_ROOT/charger-port"
say(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$CL"; }

twrp_batt(){ # echo: cap temp_deci Vnow Inow status
  sudo adb shell 'd=/sys/class/power_supply/battery; echo "$(cat $d/capacity) $(cat $d/temp) $(cat $d/voltage_now) $(cat $d/current_now) $(cat $d/status)"' 2>/dev/null
}
in_twrp(){ sudo adb get-state 2>/dev/null | grep -q recovery; }
in_pmos(){ ping -c1 -W2 "$FP3_SSH_IP" >/dev/null 2>&1; }

say "=== CHARGE-TEST start: cycles=$CYCLES pmos_dwell=${PMOS_DWELL}s abort=${ABORT}d°C ==="
# Biztos kiindulás: TWRP
if ! in_twrp; then say "TWRP-be váltás (kiindulás)…"; ./to-twrp.sh >>"$CL" 2>&1
  for i in $(seq 1 45); do in_twrp && break; sleep 2; done; fi

for c in $(seq 1 "$CYCLES"); do
  read -r cap0 t0 v0 i0 st0 < <(twrp_batt)
  say "ciklus $c/$CYCLES  T0(TWRP): cap=${cap0}% temp=$((t0/10)).$((t0%10))°C V=${v0} I=${i0} st=${st0}"
  # HŐ-ABORT ellenőrzés
  if [ "${t0:-0}" -ge "$ABORT" ]; then
    say "!!! ABORT: temp ${t0} ≥ ${ABORT} → TWRP-ben maradunk, teszt leáll."; break; fi

  # pmOS burst
  say "  → pmOS boot + ${PMOS_DWELL}s dwell (kísérleti charger itt futna)"
  ./to-pmos.sh >>"$CL" 2>&1
  booted=0; for i in $(seq 1 60); do in_pmos && { booted=1; break; }; sleep 2; done
  if [ "$booted" = 1 ]; then
    say "  pmOS fel; dwell ${PMOS_DWELL}s…"; sleep "$PMOS_DWELL"
    # ha lesz charger node, itt logoljuk:
    sshpass -p "$FP3_PW" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
      -o ConnectTimeout=6 "fp3@$FP3_SSH_IP" \
      'for d in /sys/class/power_supply/*; do n=$(basename $d); echo "  [pmOS:$n] st=$(cat $d/status 2>/dev/null) I=$(cat $d/current_now 2>/dev/null) V=$(cat $d/voltage_now 2>/dev/null)"; done' 2>/dev/null | tee -a "$CL"
  else
    say "  pmOS NEM jött fel ${PMOS_DWELL}s alatt — visszaváltás TWRP-be."
  fi

  # vissza TWRP-be hő-ellenőrzésre
  say "  → TWRP (hő-ellenőrzés)"; ./to-twrp.sh >>"$CL" 2>&1
  for i in $(seq 1 45); do in_twrp && break; sleep 2; done
  read -r cap1 t1 v1 i1 st1 < <(twrp_batt)
  dv=$(( ${v1:-0} - ${v0:-0} )); dc=$(( ${cap1:-0} - ${cap0:-0} ))
  say "  T1(TWRP): cap=${cap1}% temp=$((t1/10)).$((t1%10))°C V=${v1} I=${i1} st=${st1}  Δcap=${dc}% ΔV=${dv}µV"
  if [ "${t1:-0}" -ge "$ABORT" ]; then
    say "!!! ABORT a dwell UTÁN: temp ${t1} ≥ ${ABORT} → leállás, TWRP-ben maradunk."; break; fi
done
say "=== CHARGE-TEST vége. Telefon TWRP-ben (biztonságos + tölt). Log: $CL ==="
