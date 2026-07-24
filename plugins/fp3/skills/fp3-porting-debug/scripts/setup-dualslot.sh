#!/bin/bash
# ONE-TIME dual-slot install: pmOS -> slot _b (rootfs on system_b), UT stays on _a.
# After this, OS-swap is a single `fastboot set_active a|b` + reboot (no flashing,
# no installer, no userdata conflict — FP3 has ONE shared userdata, so pmOS roots
# from its 2-subpartition image on system_b instead of userdata).
#
# Why system_b: the pmOS initramfs mount_subpartitions (init_functions.sh) scans
# userdata -> system* for a partition holding EXACTLY 2 subpartitions (boot+root)
# and losetup-mounts it. UT's plain-ext4 system_a/userdata have 0 subparts and are
# skipped, so system_b is auto-detected with no cmdline change. 2.1G rootfs < 3G part.
#
# PREREQ: a fresh rootfs image is already built (pmbootstrap install just ran with
# the new kernel). Phone in fastboot. UT backup already taken (ut-backup-20260630).
#
# usage: setup-dualslot.sh
set -uo pipefail
source "$(dirname "$0")/fp3-env.sh"
PMOS_DTBO=$FP3_PMOS/pmos-backup-20260629/dtbo_a.img   # z3ntu/dtbo-fp3 v1.0 (native-boot blocker fix)

[ -f "$PMOS_DTBO" ] || { echo "MISSING pmOS dtbo $PMOS_DTBO"; exit 1; }
have_fastboot || { echo "Put the phone in fastboot first."; exit 1; }

log "=== dual-slot install: pmOS -> slot _b (system_b rootfs) ==="

# 1) make slot b active so bare-name flashes (vbmeta, lk2nd->boot) land on _b
log "set_active b"
fb set_active b 2>&1 | tail -1

# 2) z3ntu dtbo -> dtbo_b (the proven native-boot blocker fix)
log "flash z3ntu dtbo -> dtbo_b"
fb flash dtbo_b "$PMOS_DTBO" 2>&1 | tail -2

# 3) vbmeta(disable) -> vbmeta_b, lk2nd -> boot_b  (bare names follow active slot)
log "flash_vbmeta (AVB OFF) -> vbmeta_b"
yes '' | $PMB flasher flash_vbmeta 2>&1 | tail -8
log "flash_lk2nd -> boot_b"
yes '' | $PMB flasher flash_lk2nd 2>&1 | tail -8

# 4) rootfs -> system_b (EXPLICIT partition; literal name, not slot-relative)
log "flash_rootfs -> system_b (2-subpartition pmOS image)"
yes '' | $PMB flasher flash_rootfs --partition system_b 2>&1 | tail -12

# 5) boot pmOS from slot b
log "set_active b + reboot -> pmOS from system_b"
fb set_active b 2>&1 | tail -1
fb reboot 2>&1 | tail -1
log "DONE -> pmOS boots from slot b. UT untouched on slot a."
log "From now on: swap with  fastboot set_active a  (UT)  /  set_active b  (pmOS) + reboot."
