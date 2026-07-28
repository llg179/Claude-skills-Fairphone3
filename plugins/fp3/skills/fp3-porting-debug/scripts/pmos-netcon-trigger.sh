#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# pmos-netcon-trigger.sh HOST_MAC  — run on pmOS as root.
# Bring up netconsole over the RNDIS link (device $FP3_DEV_IP -> host
# $FP3_HOST_IP:6666), then modprobe the patched rpmsg_char which binds the ADSP
# DIAG_CNTL channel and crashes. The kernel oops/panic streams to the host via
# netconsole before the reset, so we capture the real fault signature.

# Config lives in fp3-env.sh; every value there has a documented default.
# Resolve symlinks first: these scripts are commonly installed as symlinks in
# /usr/local/bin, where a bare $0 would look for fp3-env.sh next to the symlink.
_self="$(readlink -f "$0")"
for _d in "$(dirname "$_self")" "$(dirname "$_self")/.." "$(dirname "$_self")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

set -u
HMAC="${1:?need host RNDIS MAC}"
echo "== load netconsole (tgt mac=$HMAC) =="
modprobe netconsole netconsole="6665@$FP3_DEV_IP/usb0,6666@$FP3_HOST_IP/$HMAC" 2>&1
sleep 1
dmesg | tail -4
echo "== netconsole test line (should reach host) =="
echo "FP3-NETCON-TEST-$(date +%s)" > /dev/kmsg
sleep 1
echo "== triggering rpmsg_char DIAG_CNTL bind (expect crash) =="
sync; sync
modprobe rpmsg_char
echo "== SURVIVED (unexpected — no crash) =="
