# SPDX-License-Identifier: GPL-2.0-or-later

# Config lives in fp3-env.sh; every value there has a documented default.
for _d in "$(dirname "$0")" "$(dirname "$0")/.." "$(dirname "$0")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

set +e
for i in $(seq 1 40); do
  sleep 5
  if sshpass -p "$FP3_PW" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 fp3@$FP3_DEV_IP 'uptime' >/dev/null 2>&1; then
    echo "=== SSH up after ~$((i*5))s ==="; break
  fi
done
sleep 6
echo "=== SOUND CARDS ==="
sshpass -p "$FP3_PW" ssh -o StrictHostKeyChecking=no fp3@$FP3_DEV_IP 'cat /proc/asound/cards 2>&1; echo "--- aplay -l ---"; aplay -l 2>&1' 2>/dev/null
echo "=== slim/deferred noise? ==="
sshpass -p "$FP3_PW" ssh -o StrictHostKeyChecking=no fp3@$FP3_DEV_IP 'echo "$FP3_PW" | sudo -S dmesg 2>/dev/null | grep -iE "slim|codec dai not found|sound-card|Fairphone" | tail -15' 2>/dev/null | grep -v "Password:"
