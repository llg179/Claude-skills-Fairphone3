#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# ut-ssh — reach the FP3 while it is booted into Ubuntu Touch (the oracle slot)
# without unlocking the screen and without replugging the cable.
#
# Three ways in, tried in order:
#   1. USB rndis  ($FP3_UT_USB_IP)                  — key auth
#   2. WiFi       ($FP3_UT_WIFI_IP, if configured)  — key auth, cable-independent
#   3. rescue     ($FP3_UT_USB_IP:$FP3_UT_RESCUE_PORT) — UT's own usb-moded sshd,
#      which permits a login even for a passwordless account
#
# A stale neighbour entry (the gadget picks a fresh MAC every boot) is flushed
# between rounds, which is what used to look like "the link is dead, replug it".
#
# Prerequisites are documented step by step under "Unattended access" in the
# repository README; ut-ssh only works once that setup has been done.
#
#   ut-ssh                  # interactive shell
#   ut-ssh 'uname -a'       # run a command; the remote exit status is passed through

# Resolve symlinks first: these scripts are commonly installed as symlinks in
# /usr/local/bin, where a bare $0 would look for fp3-env.sh next to the symlink.
_self="$(readlink -f "$0")"
for _d in "$(dirname "$_self")" "$(dirname "$_self")/.." "$(dirname "$_self")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

set -u
TRIES="${UT_SSH_TRIES:-12}"
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR
      -o ConnectTimeout=8 -o ServerAliveInterval=15 -o IdentitiesOnly=yes -i $FP3_SSH_KEY"

targets() {
    echo "$FP3_UT_USER@$FP3_UT_USB_IP 22"
    [ -n "${FP3_UT_WIFI_IP:-}" ] && echo "$FP3_UT_USER@$FP3_UT_WIFI_IP 22"
    echo "$FP3_UT_USER@$FP3_UT_USB_IP $FP3_UT_RESCUE_PORT"
}

i=1
while [ "$i" -le "$TRIES" ]; do
    while read -r dest port; do
        [ -n "$dest" ] || continue
        if [ "$#" -eq 0 ]; then
            ssh $OPTS -p "$port" "$dest" && exit 0
            continue
        fi
        ssh $OPTS -p "$port" "$dest" "$@"
        rc=$?
        [ "$rc" -eq 0 ] && exit 0
        # 255 is ssh's own transport failure; any other status came from the
        # remote command itself and is a real answer, so stop and report it.
        [ "$rc" -ne 255 ] && exit "$rc"
    done <<< "$(targets)"

    ip neigh flush dev "$FP3_UT_IFACE" 2>/dev/null || true
    echo "ut-ssh: no answer on any path (attempt $i/$TRIES), retrying" >&2
    sleep 5
    i=$((i + 1))
done

echo "ut-ssh: giving up after $TRIES attempts" >&2
exit 255
