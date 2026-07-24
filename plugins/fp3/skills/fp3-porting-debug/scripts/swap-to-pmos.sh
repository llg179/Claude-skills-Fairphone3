#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Installer-free, hands-free swap BACK to postmarketOS from the UT backup state.
# Flashes the z3ntu dtbo (the proven native-boot blocker fix) to both slots, then
# runs the normal pmOS flasher (vbmeta-disable + lk2nd->boot + the freshly-built
# rootfs->userdata). System/vendor are left as UT's (pmOS ignores them).
#
# Pair: swap-to-ut.sh (restores the dev-enabled UT). Run either from fastboot.
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
