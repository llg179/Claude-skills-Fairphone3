#!/bin/bash

# Config lives in fp3-env.sh; every value there has a documented default.
for _d in "$(dirname "$0")" "$(dirname "$0")/.." "$(dirname "$0")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

set -o pipefail
LOG=$FP3_ROOT/charger-port/build-fuelgauge.log
echo "=== fuel-gauge build $(date) ===" | tee "$LOG"
cd $FP3_PMOS
./pmb build --src $FP3_PMOS/linux-fp3 linux-postmarketos-qcom-msm8953 2>&1 | tee -a "$LOG"
echo "BUILD rc=${PIPESTATUS[0]}" | tee -a "$LOG"
