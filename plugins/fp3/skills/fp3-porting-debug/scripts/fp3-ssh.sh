#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# fp3-ssh — SSH/scp to the FP3 dev device (pmOS) over the stable NCM link.
# Ensures the host IP is present first (handles the pre-reboot enx* phase and
# the post-reboot stable "fp3" iface identically). NEVER pokes the USB layer.
#
#   fp3-ssh                       # interactive shell
#   fp3-ssh 'md5sum ...'          # run a command
#   fp3-ssh --scp SRC DEST        # scp SRC to fp3:DEST

# Config lives in fp3-env.sh; every value there has a documented default.
for _d in "$(dirname "$0")" "$(dirname "$0")/.." "$(dirname "$0")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

set -u
IP=$FP3_DEV_IP; USER=fp3; PW="$FP3_PW"
OPTS="-o PreferredAuthentications=password -o PubkeyAuthentication=no -o StrictHostKeyChecking=no -o ConnectTimeout=8"
# make sure host side has an address (idempotent)
fp3-link ip >/dev/null 2>&1 || true
if [ "${1:-}" = "--scp" ]; then
    shift; SRC="$1"; DEST="$2"
    exec sshpass -p "$PW" scp $OPTS "$SRC" "$USER@$IP:$DEST"
fi
exec sshpass -p "$PW" ssh $OPTS "$USER@$IP" "$@"
