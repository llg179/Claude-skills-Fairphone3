# SPDX-License-Identifier: GPL-2.0-or-later

# Config lives in fp3-env.sh; every value there has a documented default.
# Resolve symlinks first: these scripts are commonly installed as symlinks in
# /usr/local/bin, where a bare $0 would look for fp3-env.sh next to the symlink.
_self="$(readlink -f "$0")"
for _d in "$(dirname "$_self")" "$(dirname "$_self")/.." "$(dirname "$_self")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

set +e
for i in $(seq 1 45); do
  sleep 5
  sshpass -p "$FP3_PW" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 fp3@$FP3_DEV_IP 'uptime' >/dev/null 2>&1 && { echo "=== up ~$((i*5))s ==="; break; }
done
sleep 12  # let phosh + pipewire settle
echo "=== card ==="; sshpass -p "$FP3_PW" ssh -o StrictHostKeyChecking=no fp3@$FP3_DEV_IP 'cat /proc/asound/cards' 2>/dev/null
echo "=== UCM verbs (correct name) ==="; sshpass -p "$FP3_PW" ssh -o StrictHostKeyChecking=no fp3@$FP3_DEV_IP 'alsaucm -c "Fairphone 3" list _verbs 2>&1 | head -3' 2>/dev/null
echo "=== phosh-session pipewire sinks (via the seat session env) ==="
sshpass -p "$FP3_PW" ssh -o StrictHostKeyChecking=no fp3@$FP3_DEV_IP 'for u in /run/user/*/; do uid=$(basename $u); XDG_RUNTIME_DIR=$u sudo -u "#$uid" wpctl status 2>/dev/null | sed -n "/Sinks:/,/Sources:/p" | head -8; done' 2>/dev/null | grep -v "Password:"
