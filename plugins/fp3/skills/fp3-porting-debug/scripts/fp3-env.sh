#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# FP3 bring-up — shared environment. Source this from the other scripts.
#
# Every setting below is `${VAR:-default}`: export the variable before running
# anything and your value wins; otherwise the documented default applies.
# Put your own overrides in fp3-env.local.sh next to this file (git-ignored).

export FP3_SCRIPTS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"  # where these scripts live
export GEN="${GEN:-$FP3_SCRIPTS/generated}"; mkdir -p "$GEN" 2>/dev/null || true

# --- device access ----------------------------------------------------------
# Password of the pmOS user. NO DEFAULT ON PURPOSE: it is whatever you set when
# you installed pmOS. Set it in fp3-env.local.sh or export it before running.
export FP3_PW="${FP3_PW:-}"
export FP3_USER="${FP3_USER:-fp3}"          # default: the pmOS username
export FP3_DEV_IP="${FP3_DEV_IP:-172.16.42.1}"   # default: pmOS USB-net device address
export FP3_HOST_IP="${FP3_HOST_IP:-172.16.42.2}" # default: matching host-side address
export FP3_IFACE="${FP3_IFACE:-fp3}"        # default: host NIC name for the USB link
export FP3_SERIAL="${FP3_SERIAL:-}"         # NO DEFAULT: your device's fastboot/adb serial

# Kept for older scripts that still use the previous name.
export FP3_SSH_IP="$FP3_DEV_IP"

# --- host paths -------------------------------------------------------------
export FP3_ROOT="${FP3_ROOT:-$HOME/fp3}"            # default: project data root (images, dumps, journal)
export FP3_PMOS="${FP3_PMOS:-$HOME/pmos}"           # default: parent of the pmbootstrap + kernel trees
export PMB="${PMB:-$FP3_PMOS/pmb}"                  # default: $FP3_PMOS/pmb
export PMOS_WORK="${PMOS_WORK:-$FP3_PMOS/work}"     # default: pmbootstrap work dir
export ROOTFS_CHROOT="${ROOTFS_CHROOT:-$PMOS_WORK/chroot_rootfs_fairphone-fp3}"
export TWRP_IMG="${TWRP_IMG:-$FP3_ROOT/twrp-fp3.img}"
export LOG="${LOG:-$GEN/pmos-attempts.log}"

# --- eMMC partitions (TWRP by-name) — see references/hw-facts.md -------------
export P_BOOT_A="${P_BOOT_A:-/dev/block/bootdevice/by-name/boot_a}"      # mmcblk0p27
export P_BOOT_B="${P_BOOT_B:-/dev/block/bootdevice/by-name/boot_b}"      # mmcblk0p28
export P_USERDATA="${P_USERDATA:-/dev/block/bootdevice/by-name/userdata}" # mmcblk0p62
export P_VBMETA="${P_VBMETA:-/dev/block/bootdevice/by-name/vbmeta}"

# --- local overrides (not tracked) ------------------------------------------
[ -r "$FP3_SCRIPTS/fp3-env.local.sh" ] && . "$FP3_SCRIPTS/fp3-env.local.sh"

fb(){ sudo fastboot "$@"; }
adbr(){ sudo adb "$@"; }
log(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }
have_fastboot(){ sudo fastboot devices 2>/dev/null | grep -q fastboot; }
have_recovery(){ sudo adb get-state 2>/dev/null | grep -q recovery; }
wait_state(){ # wait_state fastboot|recovery [secs]
  local want=$1 secs=${2:-60} i
  for i in $(seq 1 $((secs/2))); do
    case $want in
      fastboot) have_fastboot && return 0;;
      recovery) have_recovery && return 0;;
    esac
    sleep 2
  done
  return 1
}
