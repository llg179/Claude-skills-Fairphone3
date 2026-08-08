#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# fp3-kbuild.sh — incremental cross-builds of the FP3 kernel, without the
# thirty-minute package round trip.
#
# The package build starts from a fresh source tarball on every _commit bump,
# so nothing survives between builds and a six-file change costs as much as a
# clean tree: measured on this machine, 16 to 33 minutes. pmbootstrap's
# envkernel wraps `make` so it cross-compiles inside the chroot but keeps the
# objects out of tree in $TREE/.output, which does survive — so the second and
# every later build compiles only what changed.
#
# Usage, from anywhere:
#   fp3-kbuild.sh setup [tree]        # one time per tree: prepare .output/.config
#   fp3-kbuild.sh <make args...>      # e.g. drivers/media/platform/qcom/camss/
#   fp3-kbuild.sh modules             # everything loadable, incrementally
#   fp3-kbuild.sh ko <module-name>    # print the path of a freshly built .ko
#
# The tree defaults to the branch the package pins (debug-int), because that is
# what the phone runs; override with FP3_KTREE.
#
# ☠️ envkernel forces CCACHE_DISABLE=1, so the *first* full build here is not
# faster than the package one. The point is every build after it.

set -u

PMOS="${FP3_PMOS:-/mnt/1TB/pmos}"
TREE="${FP3_KTREE:-$PMOS/fp3-sensors-wt}"     # debug-int/<base>: what the phone runs
CONFIG="${FP3_KCONFIG:-$PMOS/pmaports/device/testing/linux-fp3/config-fp3.aarch64}"
ENVKERNEL="$PMOS/pmbootstrap/helpers/envkernel.sh"

die() { echo "fp3-kbuild: $*" >&2; exit 1; }

[ -r "$ENVKERNEL" ] || die "no envkernel helper at $ENVKERNEL (set FP3_PMOS)"
[ -d "$TREE" ] || die "no kernel tree at $TREE (set FP3_KTREE)"

# envkernel re-runs `pmbootstrap init` and dies if it cannot find the config
# where pmbootstrap looks for it, which is not where this project keeps it.
CFG="${XDG_CONFIG_HOME:-$HOME/.config}/pmbootstrap_v3.cfg"
[ -e "$CFG" ] || die "symlink $PMOS/pmbootstrap_v3.cfg to $CFG first"

cd "$TREE" || die "cannot enter $TREE"

# With O=.output the config belongs in .output and a stray one in the source
# tree makes the outputmakefile target fail.
[ -e .config ] && die "remove the stray .config in $TREE — with O=.output it lives in .output"

case "${1:-}" in
setup)
    [ -r "$CONFIG" ] || die "no config at $CONFIG (set FP3_KCONFIG)"
    mkdir -p .output
    # .output is owned by the chroot user, so the config has to be placed from
    # inside the chroot rather than copied in from the host - a host-side cp
    # fails with EPERM and olddefconfig then silently falls back to the
    # arch defconfig, which builds a kernel for a different phone.
    cp "$CONFIG" ./fp3-kbuild.config || die "cannot stage the config in the tree"
    ( . "$ENVKERNEL" >/dev/null 2>&1
      pmbootstrap -q chroot --user -- cp /mnt/linux/fp3-kbuild.config \
                                         /mnt/linux/.output/.config ) \
        || die "could not place the config into .output through the chroot"
    rm -f ./fp3-kbuild.config
    ( . "$ENVKERNEL" >/dev/null 2>&1; make olddefconfig ) \
        || die "olddefconfig failed"
    echo "fp3-kbuild: $TREE is set up; .output/.config from $(basename "$CONFIG")"
    ;;
ko)
    [ $# -ge 2 ] || die "usage: fp3-kbuild.sh ko <module-name>"
    find .output -name "$2.ko" -print -quit
    ;;
"")
    die "usage: fp3-kbuild.sh setup | <make args> | ko <module>"
    ;;
*)
    [ -r .output/.config ] || die "run 'fp3-kbuild.sh setup' first"
    # shellcheck disable=SC1090
    . "$ENVKERNEL" >/dev/null 2>&1 || die "could not source envkernel"
    exec make "$@"
    ;;
esac
