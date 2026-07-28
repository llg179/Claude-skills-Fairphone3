# SPDX-License-Identifier: GPL-2.0-or-later

# Config lives in fp3-env.sh; every value there has a documented default.
# Resolve symlinks first: these scripts are commonly installed as symlinks in
# /usr/local/bin, where a bare $0 would look for fp3-env.sh next to the symlink.
_self="$(readlink -f "$0")"
for _d in "$(dirname "$_self")" "$(dirname "$_self")/.." "$(dirname "$_self")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

set +e
for i in $(seq 1 40); do
  sleep 5
  if sshpass -p "$FP3_PW" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 fp3@$FP3_DEV_IP 'uptime' >/dev/null 2>&1; then
    echo "=== SSH up after ~$((i*5))s ==="
    break
  fi
done
# give drivers time to run the slim sequence
sleep 8
sshpass -p "$FP3_PW" ssh -o StrictHostKeyChecking=no fp3@$FP3_DEV_IP 'echo "$FP3_PW" | sudo -S dmesg' 2>/dev/null | grep -iE "DBG|slim|ngd|capability|logical addr|wcd9335|TX timed" | tail -60
