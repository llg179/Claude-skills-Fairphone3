#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
#
# ############################################################################
# ##  THIS IS *NOT* HOW YOU SWITCH OS.  Read this before running it.        ##
# ############################################################################
#
# Switching between the two OSes is FREE and involves NO flashing at all:
#
#     scripts/slot.sh set a     # -> Ubuntu Touch   (boot_a = UT Halium boot image)
#     scripts/slot.sh set b     # -> postmarketOS   (boot_b = lk2nd -> pmOS)
#     then reboot
#
# That works because `setup-dualslot.sh` has already been run once (pmOS rootfs
# on `system_b`, UT keeps `userdata`).  Layout + one-time preparation:
#   https://github.com/llg179org/Claude-skills-Fairphone3#installing-the-two-oses
#   ("Both at once: the dual-slot setup")
#
# THIS script REINSTALLS postmarketOS from scratch.  Use it only when the pmOS
# side is actually broken/absent — e.g. lk2nd was overwritten (the classic cause:
# `pmbootstrap flasher flash_kernel`, or having run swap-to-ut.sh, which puts
# TWRP on boot_b), or you want a clean install of a freshly built rootfs.
#
# It flashes the z3ntu dtbo (the proven native-boot blocker fix) to BOTH slots,
# then runs flash-pmos.sh (vbmeta-disable + lk2nd->boot + rootfs).
# System/vendor are left as UT's (pmOS ignores them).
#
# ⚠️ The `set_active a` below and the rootfs->userdata target are the PRE-dual-slot
#    layout (both OSes on slot a, pmOS rooting from userdata).  On the current
#    device pmOS is slot _b and roots from system_b — re-run `setup-dualslot.sh`
#    instead if that is the layout you want back.  Do not infer the disk layout
#    from this file; read the partitions
#    (`dd if=/dev/disk/by-partlabel/boot_a bs=1 count=64 | strings`).
#
# Pair: swap-to-ut.sh (restores the dev-enabled UT backup). Run either from fastboot.
#
# usage: swap-to-pmos.sh
set -uo pipefail
source "$(dirname "$0")/fp3-env.sh"
HERE="$(dirname "$0")"
PMOS_DTBO=$FP3_PMOS/pmos-backup-20260629/dtbo_a.img   # z3ntu/dtbo-fp3 v1.0

[ -f "$PMOS_DTBO" ] || { echo "MISSING pmOS dtbo $PMOS_DTBO"; exit 1; }
have_fastboot || { echo "Put the phone in fastboot first."; exit 1; }

log "set_active a (pmOS lk2nd+rootfs live on slot a; TWRP may have left slot b active)"
fb set_active a 2>&1 | tail -1

log "flash z3ntu dtbo -> dtbo_a + dtbo_b (the native-boot blocker fix)"
fb flash dtbo_a "$PMOS_DTBO" 2>&1 | tail -2
fb flash dtbo_b "$PMOS_DTBO" 2>&1 | tail -2

log "run pmOS flasher (vbmeta-disable + lk2nd + rootfs); reboots at the end"
bash "$HERE/flash-pmos.sh" full
log "DONE -> phone should boot pmOS. SSH fp3@$FP3_SSH_IP (pw $FP3_PW) after boot."
