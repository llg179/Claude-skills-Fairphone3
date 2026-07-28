#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# fp3-ssh — SSH/scp to the FP3 dev device (pmOS) over the stable NCM link.
#
# Prefers key authentication ($FP3_SSH_KEY, installed once with
# `fp3-link install-key`), which removes the password and sshpass from every
# call and makes post-reboot reconnects instant. Falls back to the password if
# no key is installed yet.
#
# On ssh's own transport failure it flushes the stale neighbour entry and
# retries: the gadget picks a fresh random MAC on every boot, so the host is
# otherwise left talking to the previous MAC and reports "No route to host" for
# a link that is in fact fine. That was the usual reason for reaching for the
# cable; see "Unattended access" in the repository README.
#
# NEVER pokes the USB layer.
#
#   fp3-ssh                       # interactive shell
#   fp3-ssh 'md5sum ...'          # run a command (remote exit status passed through)
#   fp3-ssh --scp SRC DEST        # scp SRC to fp3:DEST

# Config lives in fp3-env.sh; every value there has a documented default.
# Resolve symlinks first: these scripts are commonly installed as symlinks in
# /usr/local/bin, where a bare $0 would look for fp3-env.sh next to the symlink.
_self="$(readlink -f "$0")"
for _d in "$(dirname "$_self")" "$(dirname "$_self")/.." "$(dirname "$_self")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

set -u
IP=$FP3_DEV_IP; USER=$FP3_USER; PW="$FP3_PW"
TRIES="${FP3_SSH_TRIES:-12}"
COMMON="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR
        -o ConnectTimeout=8 -o ServerAliveInterval=15"

if [ -r "$FP3_SSH_KEY" ]; then
    OPTS="$COMMON -o IdentitiesOnly=yes -i $FP3_SSH_KEY"
    SSH() { ssh $OPTS "$@"; }
    SCP() { scp $OPTS "$@"; }
else
    OPTS="$COMMON -o PreferredAuthentications=password -o PubkeyAuthentication=no"
    SSH() { sshpass -p "$PW" ssh $OPTS "$@"; }
    SCP() { sshpass -p "$PW" scp $OPTS "$@"; }
fi

# make sure host side has an address (idempotent)
fp3-link ip >/dev/null 2>&1 || true

if [ "${1:-}" = "--scp" ]; then
    shift; SRC="$1"; DEST="$2"
    SCP "$SRC" "$USER@$IP:$DEST"; exit $?
fi

if [ "$#" -eq 0 ]; then SSH "$USER@$IP"; exit $?; fi

i=1
while [ "$i" -le "$TRIES" ]; do
    SSH "$USER@$IP" "$@"
    rc=$?
    [ "$rc" -eq 0 ] && exit 0
    # 255 is ssh's own transport failure; anything else came from the remote
    # command and must be reported rather than retried.
    [ "$rc" -ne 255 ] && exit "$rc"
    ip neigh flush dev "$FP3_IFACE" 2>/dev/null || true
    echo "fp3-ssh: link not ready (attempt $i/$TRIES), retrying" >&2
    sleep 5
    i=$((i + 1))
done

echo "fp3-ssh: giving up after $TRIES attempts" >&2
exit 255
