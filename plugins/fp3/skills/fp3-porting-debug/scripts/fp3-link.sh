#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# fp3-link — host-side NCM link helper for the FP3 dev device (pmOS).
#
# Encodes the hard-won operational lessons (memory: project_fp3_audio_codec):
#   * The USB-NCM gadget uses a RANDOM MAC each boot. A systemd .link
#     (/etc/systemd/network/10-fp3.link) renames it to a stable "fp3", and an
#     NM profile "fp3" pins $FP3_HOST_IP/16. Until the next device reboot the
#     live iface may still be enx<mac>; this script handles both.
#   * On a cold-boot JAM (transmit-queue-timeout: ICMP may be OK but TCP dead)
#     the device SELF-RECOVERS in minutes. Only PASSIVELY poll.
#   ☠️ NEVER restart/reset USB at the HOST-CONTROLLER level: no xhci_hcd unbind,
#     no usbcore reload, no root-hub `authorized` toggle, no `ip link down/up` /
#     nmcli link cycling of a live capture. The host's work disk may itself be
#     USB-attached, and a controller-level reset takes it down with everything else.
#   ☠️ And know what a host-side reset CANNOT do, which was measured rather than
#     assumed (2026-07-28): a *leaf-port* `authorized` 0->1 and a `usb` driver
#     unbind/bind on the phone's own port are harmless if you have checked the
#     topology first (`findmnt -no SOURCE <workmount>` -> `readlink -f /sys/block/<dev>`
#     gives the disk's bus; compare with the phone's) — but they are also USELESS:
#     the device number never changed and the gadget mode never moved, because
#     none of them drops VBUS, so the phone never sees a disconnect and never
#     re-evaluates its USB mode. Cutting VBUS is not available either unless an
#     external hub with per-port power switching is in the path (root hubs report
#     "No power switching"). The only real lever is DEVICE-side: re-bind the UDC
#     (`echo "" > /sys/kernel/config/usb_gadget/g1/UDC`, then write it back), which
#     is what fp3-usbnet-watchdog does on pmOS. See "Unattended access" in the
#     repository README.
#
# Usage: fp3-link {status|up|wait [secs]|ip|heal|install-key}

# Config lives in fp3-env.sh; every value there has a documented default.
# Resolve symlinks first: these scripts are commonly installed as symlinks in
# /usr/local/bin, where a bare $0 would look for fp3-env.sh next to the symlink.
_self="$(readlink -f "$0")"
for _d in "$(dirname "$_self")" "$(dirname "$_self")/.." "$(dirname "$_self")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

set -u
DEV_IP=$FP3_DEV_IP
HOST_CIDR=$FP3_HOST_IP/16
PORT=22

_iface() {  # prefer stable name, fall back to any enx*
    if [ -e /sys/class/net/fp3 ]; then echo fp3; return; fi
    ls /sys/class/net 2>/dev/null | grep -E '^enx' | head -1
}
_has_ip()  { ip -4 addr show "$1" 2>/dev/null | grep -q 'inet 172\.16\.42\.'; }
_carrier() { [ "$(cat /sys/class/net/$1/carrier 2>/dev/null)" = 1 ] && echo up || echo down; }
_tcp()     { timeout 3 bash -c "exec 3<>/dev/tcp/$DEV_IP/$PORT" 2>/dev/null && echo open || echo dead; }

cmd_ip() {   # ensure the host IP is present on the current iface (idempotent)
    local IF; IF=$(_iface)
    [ -z "$IF" ] && { echo "no iface"; return 1; }
    if _has_ip "$IF"; then echo "$IF already has IP"; else
        sudo ip addr add "$HOST_CIDR" dev "$IF" 2>/dev/null && echo "added $HOST_CIDR to $IF"
    fi
    sudo ip link set "$IF" up 2>/dev/null
}
cmd_status() {
    local IF; IF=$(_iface)
    if [ -z "$IF" ]; then echo "iface   : NONE (device not enumerated)"; return; fi
    echo "iface   : $IF"
    echo "carrier : $(_carrier "$IF")"
    echo "host-ip : $(ip -4 addr show "$IF" | grep -oE 'inet 172\.16\.42\.[0-9]+' | head -1 || echo none)"
    echo "ping    : $(timeout 3 ping -c1 -W1 $DEV_IP >/dev/null 2>&1 && echo ok || echo fail)"
    echo "tcp:22  : $(_tcp)"
}
cmd_wait() {  # passively poll until TCP:22 answers; NO usb-layer poking
    local max=${1:-600} t=0
    echo "waiting up to ${max}s for TCP:$PORT (passive — device self-recovers)..."
    while [ $t -lt "$max" ]; do
        local IF; IF=$(_iface)
        if [ -n "$IF" ]; then _has_ip "$IF" || cmd_ip >/dev/null; fi
        if [ "$(_tcp)" = open ]; then echo "[${t}s] TCP up on ${IF:-?}"; return 0; fi
        sleep 5; t=$((t+5))
        [ $((t%30)) -eq 0 ] && echo "  ...${t}s iface=${IF:-none} tcp=$(_tcp)"
    done
    echo "TIMEOUT after ${max}s"; return 1
}
cmd_heal() {  # host-side repair only; never touches the USB layer
    local IF; IF=$(_iface)
    [ -z "$IF" ] && { echo "no iface to heal"; return 1; }
    # The gadget picks a fresh random MAC every boot, so the host can be left
    # with a neighbour entry for the previous one; until it ages out, every
    # connection fails with "No route to host" and looks like a dead cable.
    echo "flushing neighbours on $IF"
    sudo ip neigh flush dev "$IF" 2>/dev/null || true
    if nmcli -t -f NAME connection show 2>/dev/null | grep -qx "$IF"; then
        echo "bouncing the NetworkManager profile $IF"
        sudo nmcli connection down "$IF" >/dev/null 2>&1 || true
        sudo nmcli connection up   "$IF" >/dev/null 2>&1 || true
        sleep 2
    fi
    cmd_status
}

cmd_install_key() {  # one-off: password login -> key login
    [ -r "$FP3_SSH_KEY.pub" ] || { echo "no public key at $FP3_SSH_KEY.pub"; return 1; }
    [ -n "$FP3_PW" ] || { echo "set FP3_PW (fp3-env.local.sh) for this one call"; return 1; }
    local pub; pub=$(cat "$FP3_SSH_KEY.pub")
    sshpass -p "$FP3_PW" ssh -o StrictHostKeyChecking=no -o PreferredAuthentications=password \
        -o PubkeyAuthentication=no "$FP3_USER@$DEV_IP" \
        "mkdir -p ~/.ssh && chmod 700 ~/.ssh && touch ~/.ssh/authorized_keys && \
         grep -qF '$pub' ~/.ssh/authorized_keys || echo '$pub' >> ~/.ssh/authorized_keys; \
         chmod 600 ~/.ssh/authorized_keys" &&
        echo "key installed; fp3-ssh will use it from now on"
}

case "${1:-status}" in
    status) cmd_status ;;
    ip|up)  cmd_ip ;;
    wait)   cmd_wait "${2:-600}" ;;
    heal)   cmd_heal ;;
    install-key) cmd_install_key ;;
    *) echo "usage: fp3-link {status|up|wait [secs]|ip|heal|install-key}"; exit 1 ;;
esac
