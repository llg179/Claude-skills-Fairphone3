#!/bin/bash
# GYORS AKKU-MERÍTÉS a duty-cycle charger-teszthez.
# pmOS-ben NINCS töltés → ott full terheléssel fogyasztjuk az akkut, amíg a TWRP-ben
# mért kapacitás le nem megy a célértékre (alapból 65%).
#
# TERHELÉS: mind a $(nproc) magon `sha256sum /dev/zero` (tiszta CPU-burn; a `yes`-nél
# nehezebb, mert nincs benne I/O-szünet). Torch LED nincs kitéve → ez a fő fogyasztó,
# + max kijelző-fényerő.
#
# THERMAL-MÉRÉS ALAPJÁN (2026-06-29):
#   - A CPU-zónák full 8-mag terhelés alatt ~76°C-on PLATEAU-znak (HW-throttle) → BIZTONSÁGOS.
#   - A `pmi632-thermal` (AKKU-OLDALI szenzor, a valódi tűzkockázat-jelző) VÉGIG 37°C,
#     meg se rezzen a CPU-terheléstől.
#   → ezért a terhelés FOLYAMATOSAN futhat; a guard:
#        primer  = akku-oldal (pmi632-thermal) abort BATT_MAX (45°C) — valódi biztonság
#        backstop= legmelegebb CPU-zóna  abort CPU_MAX (86°C)
#   Ha trippel: STOP + hűlés (akku<BATT_COOL ÉS cpu<CPU_COOL), majd folytat.
#
# usage: discharge.sh [target_cap=65] [burst_min=25] [batt_max=45] [cpu_max=86]
#   háttérben futtasd:  ./discharge.sh 65 25 > discharge.log 2>&1 &
set -uo pipefail
cd "$(dirname "$0")"; source ./fp3-env.sh 2>/dev/null

TARGET="${1:-65}"      # eddig a kapacitásig (%) merítünk
BURST_MIN="${2:-25}"   # egy pmOS-terhelő burst hossza percben (utána TWRP-mérés)
BATT_MAX="${3:-45}"    # °C: akku-oldali (pmi632-thermal) abort — VALÓDI biztonsági küszöb
CPU_MAX="${4:-86}"     # °C: legmelegebb CPU-zóna backstop (plateau ~76, így ritkán trippel)
BATT_COOL=41           # °C: akku-oldal eddig hűljön vissza
CPU_COOL=68            # °C: CPU eddig hűljön vissza
GUARD_S=8              # thermal-ellenőrzés gyakorisága terhelés alatt
LOG=./discharge.log

SSH(){ sshpass -p "$FP3_PW" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
       -o ConnectTimeout=8 "fp3@$FP3_SSH_IP" "$@" 2>/dev/null; }
say(){ printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

pmos_up(){ ping -c1 -W2 "$FP3_SSH_IP" >/dev/null 2>&1 && SSH 'echo ok' 2>/dev/null | grep -q ok; }

ensure_pmos(){
  pmos_up && return 0
  say "pmOS nincs fent → to-pmos.sh"
  ./to-pmos.sh >>"$LOG" 2>&1 || true
  local i; for i in $(seq 1 50); do pmos_up && { say "pmOS fent"; return 0; }; sleep 4; done
  say "pmOS NEM jött fel"; return 1
}

# °C egész: akku-oldali (pmi632-thermal) és legmelegebb CPU-zóna
batt_c(){ local m; m=$(SSH 'for z in /sys/class/thermal/thermal_zone*; do [ "$(cat $z/type)" = pmi632-thermal ] && cat $z/temp; done' 2>/dev/null); echo $(( ${m:-0}/1000 )); }
cpu_c(){  local m; m=$(SSH 'cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | sort -rn | head -1'); echo $(( ${m:-0}/1000 )); }

LOAD_PID=""
start_load(){
  say "terhelés indul: sha256sum minden magon + max kijelző"
  # PERSISTENT host-oldali SSH: a remote 'wait' tartja életben a processeket, amíg ez él.
  sshpass -p "$FP3_PW" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    -o ServerAliveInterval=15 -o ConnectTimeout=8 "fp3@$FP3_SSH_IP" \
    'for i in $(seq 1 $(nproc)); do sha256sum /dev/zero & done; wait' >/dev/null 2>&1 &
  LOAD_PID=$!
  SSH 'mb=$(cat /sys/class/backlight/1a94000.dsi.0/max_brightness 2>/dev/null); \
       echo '"$FP3_PW"' | sudo -S sh -c "echo ${mb:-255} > /sys/class/backlight/1a94000.dsi.0/brightness" 2>/dev/null' || true
}
stop_load(){ [ -n "$LOAD_PID" ] && kill "$LOAD_PID" 2>/dev/null; LOAD_PID=""
             SSH 'pkill -x sha256sum 2>/dev/null; pkill -x yes 2>/dev/null' >/dev/null 2>&1; }

run_burst(){
  start_load
  local end=$(( $(date +%s) + BURST_MIN*60 )) bt ct last_log=0 now
  while now=$(date +%s); [ "$now" -lt "$end" ]; do
    bt=$(batt_c); ct=$(cpu_c)
    if [ $((now-last_log)) -ge 30 ]; then
      say "  terhelés: akku=${bt}°C cpu=${ct}°C  (cél ${TARGET}%, hátra $(( (end-now)/60 ))min)"; last_log=$now
    fi
    if [ "$bt" -ge "$BATT_MAX" ] || [ "$ct" -ge "$CPU_MAX" ]; then
      say "  ⚠️ abort: akku=${bt}°C(max ${BATT_MAX}) cpu=${ct}°C(max ${CPU_MAX}) → STOP+hűlés"
      stop_load
      while :; do sleep 10; bt=$(batt_c); ct=$(cpu_c); say "    hűlés: akku=${bt}°C cpu=${ct}°C"
        [ "$bt" -le "$BATT_COOL" ] && [ "$ct" -le "$CPU_COOL" ] && break; done
      start_load; last_log=0
    fi
    sleep "$GUARD_S"
  done
  stop_load
}

twrp_cap(){
  ./to-twrp.sh >>"$LOG" 2>&1 || true
  local i; for i in $(seq 1 40); do adb get-state 2>/dev/null | grep -q recovery && break; sleep 3; done
  local cap temp st
  cap=$(adb shell 'cat /sys/class/power_supply/battery/capacity' 2>/dev/null | tr -d '\r')
  temp=$(adb shell 'cat /sys/class/power_supply/battery/temp' 2>/dev/null | tr -d '\r')
  st=$(adb shell 'cat /sys/class/power_supply/battery/status' 2>/dev/null | tr -d '\r')
  echo "${cap:-?}|${temp:-?}|${st:-?}"
}

say "=== DISCHARGE start: target=${TARGET}% burst=${BURST_MIN}min battMax=${BATT_MAX}°C cpuMax=${CPU_MAX}°C ==="
cyc=0
while :; do
  cyc=$((cyc+1))
  ensure_pmos || { say "pmOS hiba, megállok (telefon vélhetően fastboot/TWRP)"; exit 1; }
  say "--- burst $cyc (${BURST_MIN}min terhelés) ---"
  run_burst
  IFS='|' read -r cap temp st < <(twrp_cap)
  say "--- mérés burst $cyc után: cap=${cap}% temp=$( [ "$temp" != "?" ] && echo "$((temp/10))°C" || echo "?") status=$st ---"
  if [ "$cap" != "?" ] && [ "$cap" -le "$TARGET" ] 2>/dev/null; then
    say "✅ CÉL ELÉRVE: ${cap}% ≤ ${TARGET}% — telefon TWRP-ben (tölt/hűl). Mehet a charger-teszt."
    exit 0
  fi
  say "még megy: ${cap}% > ${TARGET}% → újabb burst (pmOS-be vissza)"
done
