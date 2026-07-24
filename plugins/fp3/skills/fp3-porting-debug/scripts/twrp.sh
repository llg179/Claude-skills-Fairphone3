#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# TWRP indítás. Mivel `fastboot boot twrp.img` az FP3 abooton FAILED ('unknown reason'),
# két megbízható út van:
#   1) flash a boot_b slotra + set_active b + reboot  (boot_a-n maradhat lk2nd!)  -> twrp.sh flash-b
#   2) flash a boot_a-ra (felülírja lk2nd-t) + reboot                            -> twrp.sh flash-a
# Visszakapcsolás pmOS-re: slot.sh set a  (ha lk2nd a boot_a-n van).
set -uo pipefail
source "$(dirname "$0")/fp3-env.sh"
cmd=${1:-help}
[ -f "$TWRP_IMG" ] || { echo "nincs TWRP image: $TWRP_IMG"; exit 1; }
case "$cmd" in
  flash-b)
    have_fastboot || { echo "fastboot mód kell"; exit 1; }
    log "flash twrp -> boot_b ; set_active b ; reboot"
    fb flash boot_b "$TWRP_IMG" 2>&1 | tail -3
    fb set_active b 2>&1 | tail -1
    fb reboot 2>&1 | tail -1
    ;;
  flash-a)
    have_fastboot || { echo "fastboot mód kell"; exit 1; }
    log "flash twrp -> boot_a (FELÜLÍRJA lk2nd-t) ; reboot"
    fb flash boot_a "$TWRP_IMG" 2>&1 | tail -3
    fb reboot 2>&1 | tail -1
    ;;
  *) echo "usage: $0 flash-b | flash-a   (boot_b ajánlott: megőrzi az lk2nd-t a boot_a-n)";;
esac
