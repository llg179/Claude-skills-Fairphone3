#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later

# Config lives in fp3-env.sh; every value there has a documented default.
# Resolve symlinks first: these scripts are commonly installed as symlinks in
# /usr/local/bin, where a bare $0 would look for fp3-env.sh next to the symlink.
_self="$(readlink -f "$0")"
for _d in "$(dirname "$_self")" "$(dirname "$_self")/.." "$(dirname "$_self")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

set -o pipefail
LOG=$FP3_ROOT/charger-port/build-fuelgauge.log
echo "=== fuel-gauge build $(date) ===" | tee "$LOG"
cd $FP3_PMOS
./pmb build --src $FP3_PMOS/linux-fp3 linux-postmarketos-qcom-msm8953 2>&1 | tee -a "$LOG"
echo "BUILD rc=${PIPESTATUS[0]}" | tee -a "$LOG"
