#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Per-zóna thermal-mintázás sha256sum-load alatt: melyik szenzor megbízható?
cd $(dirname "$0"); source ./fp3-env.sh 2>/dev/null
SSH(){ sshpass -p "$FP3_PW" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=6 "fp3@$FP3_SSH_IP" "$@" 2>/dev/null; }
SSH 'pkill -x yes 2>/dev/null; pkill -x sha256sum 2>/dev/null'
echo "zónák sorrendje:"; SSH 'for z in /sys/class/thermal/thermal_zone*; do printf "%s " "$(cat $z/type)"; done; echo'
echo "--- idle baseline 2 minta ---"
for n in 1 2; do echo "idle: $(SSH 'for z in /sys/class/thermal/thermal_zone*; do printf "%d " $(( $(cat $z/temp)/1000 )); done')"; sleep 5; done
echo "--- sha256sum load mind a magon ---"
sshpass -p "$FP3_PW" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=15 "fp3@$FP3_SSH_IP" 'for i in $(seq 1 $(nproc)); do sha256sum /dev/zero & done; wait' >/dev/null 2>&1 &
LPID=$!
for n in $(seq 1 12); do
  echo "load+$((n*6))s: $(SSH 'for z in /sys/class/thermal/thermal_zone*; do printf "%d " $(( $(cat $z/temp)/1000 )); done') | load=$(SSH 'cut -d" " -f1 /proc/loadavg') sha=$(SSH 'pgrep -x sha256sum|wc -l')"
  sleep 6
done
kill $LPID 2>/dev/null; SSH 'pkill -x sha256sum 2>/dev/null'
echo "--- load OFF, hűlés-minták (valódi szilícium lassan hűl, zajos szenzor gyorsan esik) ---"
for n in 1 2 3 4 5 6; do echo "off+$((n*5))s: $(SSH 'for z in /sys/class/thermal/thermal_zone*; do printf "%d " $(( $(cat $z/temp)/1000 )); done')"; sleep 5; done
echo "KÉSZ"
