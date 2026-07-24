#!/bin/bash
# Reboot + kimenet-detektálás: USB-net (=bootolt pmOS) VAGY vissza-fastboot (=bukott).
# A LOGFÁJL markerét figyeli (nincs pgrep self-match). Háttérben futtatandó (run_in_background).
# usage: boot-watch.sh [from_fastboot|from_recovery] [watch_secs]
set -uo pipefail
source "$(dirname "$0")/fp3-env.sh"
FROM=${1:-from_fastboot}
SECS=${2:-120}
BLOG=$FP3_ROOT/pmos-boot.log
BASE="lo enp4s0"   # host alap-interfészek; minden más = pmOS gadget
printf '\n--- boot-watch %s (%s) ---\n' "$(date -Is)" "$FROM" >> "$BLOG"
case "$FROM" in
  from_fastboot) have_fastboot && { echo "reboot from fastboot @ $(date +%H:%M:%S)" >>"$BLOG"; fb reboot >>"$BLOG" 2>&1; };;
  from_recovery) have_recovery && { echo "reboot from recovery @ $(date +%H:%M:%S)" >>"$BLOG"; adbr reboot >>"$BLOG" 2>&1; };;
esac
for i in $(seq 1 $((SECS/5))); do
  NOW=$(ip -br link | awk '{print $1}' | paste -sd' ')
  NEW=""; for x in $NOW; do echo "$BASE" | grep -qw "$x" || NEW="$NEW $x"; done
  if [ -n "$NEW" ]; then echo "OUTCOME=BOOTED_USBNET iface=$NEW t=$(date +%H:%M:%S)" >>"$BLOG"; break; fi
  if have_fastboot; then
    echo "OUTCOME=BACK_IN_FASTBOOT t=$(date +%H:%M:%S) after=${i}x5s" >>"$BLOG"
    printf 'retry-count:a ' >>"$BLOG"; fb getvar slot-retry-count:a 2>&1|head -1 >>"$BLOG"
    break
  fi
  if have_recovery; then echo "OUTCOME=RECOVERY(TWRP) t=$(date +%H:%M:%S)" >>"$BLOG"; break; fi
  sleep 5
done
echo "WATCH_DONE=$(date -Is)" >>"$BLOG"
grep -E "OUTCOME=|retry-count:a|WATCH_DONE" "$BLOG" | tail -4
