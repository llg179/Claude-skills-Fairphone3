#!/bin/bash
# fp3-link — host-side NCM link helper for the FP3 dev device (pmOS).
#
# Encodes the hard-won operational lessons (memory: project_fp3_audio_codec):
#   * The USB-NCM gadget uses a RANDOM MAC each boot. A systemd .link
#     (/etc/systemd/network/10-fp3.link) renames it to a stable "fp3", and an
#     NM profile "fp3" pins $FP3_HOST_IP/16. Until the next device reboot the
#     live iface may still be enx<mac>; this script handles both.
#   * On a cold-boot JAM (transmit-queue-timeout: ICMP may be OK but TCP dead)
#     the device SELF-RECOVERS in minutes. Only PASSIVELY poll.
#   ☠️ NEVER restart/reset USB on the HOST: no `echo 1 > .../usb/.../remove`,
#     no `authorized` toggle, no USBDEVFS_RESET ioctl, no cdc_ncm/port unbind-rebind,
#     and no `ip link down/up` / nmcli link cycling. It does NOT clear a device-side
#     gadget jam, AND the host's /mnt work disk is itself USB-attached — a host USB
#     reset can disconnect /mnt. Recovery is patience or a DEVICE reboot, never a
#     host-side USB/link restart.
#
# Usage: fp3-link {status|up|wait [secs]|ip}

# Config lives in fp3-env.sh; every value there has a documented default.
for _d in "$(dirname "$0")" "$(dirname "$0")/.." "$(dirname "$0")/../.." ; do
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
case "${1:-status}" in
    status) cmd_status ;;
    ip|up)  cmd_ip ;;
    wait)   cmd_wait "${2:-600}" ;;
    *) echo "usage: fp3-link {status|up|wait [secs]|ip}"; exit 1 ;;
esac
