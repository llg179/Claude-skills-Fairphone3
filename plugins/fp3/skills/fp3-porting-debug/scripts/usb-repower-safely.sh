#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# usb-repower-safely — power-cycle a USB port without corrupting a work disk
# that is itself USB-attached.
#
# Read this first, because it may not be needed at all: check which bus the work
# disk is on versus the phone. If they are on different buses (they were here --
# disk on bus 2, phone on bus 1), a targeted cycle of the phone's port cannot
# touch the disk and none of this is necessary.
#
#     findmnt -no SOURCE /mnt/work            # -> /dev/sdb2
#     readlink -f /sys/block/sdb              # -> .../usb2/2-1/...  (bus 2)
#     readlink -f /sys/bus/usb/devices/1-5    # -> the phone         (bus 1)
#
# Also note what a repower can and cannot fix: a host-side port cycle only helps
# if it actually removes VBUS. Root hubs commonly report "No power switching"
# (check with `lsusb -v -d 1d6b:0002 | grep -i "power switching"`), in which case
# an external hub with per-port power switching is required -- and a gadget that
# is parked in the wrong mode by the *device* cannot be fixed from the host at
# all. See "Unattended access" in the repository README.
#
#   usb-repower-safely --unmount-only
#   usb-repower-safely <hub> <port>       # e.g. usb-repower-safely 1-4 2
set -eu

MOUNT="${FP3_WORK_MOUNT:-/mnt/1TB}"

[ "$(id -u)" = 0 ] || { echo "run me as root" >&2; exit 1; }

UUID=$(findmnt -no UUID "$MOUNT" 2>/dev/null || true)
[ -n "$UUID" ] || { echo "$MOUNT is not mounted, or has no UUID" >&2; exit 1; }

quiesce() {
    echo "== processes holding $MOUNT =="
    fuser -Mvm "$MOUNT" 2>&1 || true
    echo
    echo "Move every shell and build out of $MOUNT first; an open file or a cwd"
    echo "under it will block the unmount."
    printf 'Press Enter to unmount, Ctrl-C to abort: '
    read -r _
}

take_down() {
    sync
    umount "$MOUNT"
    echo "unmounted $MOUNT"
    part=$(blkid -U "$UUID" 2>/dev/null || true)
    if [ -n "$part" ]; then
        disk=$(lsblk -no PKNAME "$part" 2>/dev/null || true)
        if [ -n "$disk" ] && [ -e "/sys/block/$disk/device/delete" ]; then
            # Clean SCSI removal. Without it the kernel is left with a device
            # that vanished mid-flight, which produces I/O errors and stale
            # handles rather than a tidy re-enumeration.
            echo 1 > "/sys/block/$disk/device/delete"
            echo "removed /dev/$disk cleanly"
        fi
    fi
}

bring_up() {
    echo "waiting for the disk to re-enumerate"
    i=0
    while [ "$i" -lt 30 ]; do
        if blkid -U "$UUID" >/dev/null 2>&1; then
            # Mount by UUID: after a repower the kernel may hand out a
            # different letter (sdb -> sdc).
            mount UUID="$UUID" "$MOUNT"
            echo "mounted UUID=$UUID at $MOUNT"
            return 0
        fi
        sleep 2
        i=$((i + 1))
    done
    echo "disk did not return; rescan with:" >&2
    echo "  echo '- - -' > /sys/class/scsi_host/hostN/scan" >&2
    return 1
}

if [ "${1:-}" = "--unmount-only" ]; then
    quiesce; take_down; exit 0
fi

[ $# -eq 2 ] || { echo "usage: $0 <hub> <port> | --unmount-only" >&2; exit 2; }

command -v uhubctl >/dev/null || { echo "uhubctl is not installed" >&2; exit 1; }

quiesce
take_down
echo "cycling power on hub $1 port $2"
uhubctl -l "$1" -p "$2" -a cycle
bring_up
