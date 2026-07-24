#!/usr/bin/env bash
# Faithful, NON-INTERACTIVE re-implementation of Fairphone's flash_fp3_factory.sh
# for FP3-REL-Q-3.A.0136 (Android 10), with TWO deliberate deviations:
#   * RELOCK_BOOTLOADER disabled  (we MUST stay unlocked for UT + pmOS restore)
#   * no auto-reboot, no interactive prompts
# IMEI/EFS SAFE: modemst1/modemst2/fsg/fsc are NEVER touched (same as official).
# Flashes both A/B slots. Wipes userdata (pmOS backed up at $FP3_PMOS/pmos-backup-20260629).

# Config lives in fp3-env.sh; every value there has a documented default.
for _d in "$(dirname "$0")" "$(dirname "$0")/.." "$(dirname "$0")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

set -euo pipefail
DIR=$FP3_ROOT/fairphone.com-FP3-images/a10-extracted/FP3-REL-Q-3.A.0136-.gms-7c69ec7e-user-fastboot-factory
IMG="$DIR/images"
FB="$DIR/bin-linux-x86/fastboot"   # bundled fastboot, matched to these images
SN="${1:-}"   # optional serial; auto if empty

[ -x "$FB" ] || { echo "no bundled fastboot at $FB"; exit 1; }
fb(){ if [ -n "$SN" ]; then "$FB" -s "$SN" "$@"; else "$FB" "$@"; fi; }

echo "=== integrity check (SHA256SUMS) ==="
( cd "$DIR" && sha256sum --status --check SHA256SUMS ) && echo "CHECKSUMS OK" || { echo "CHECKSUM FAIL"; exit 1; }

echo "=== device in fastboot? ==="
"$FB" devices
prod=$("$FB" ${SN:+-s $SN} getvar product 2>&1 | grep -i product || true)
echo "product: $prod"
case "$prod" in *FP3*) ;; *) echo "NOT an FP3 in fastboot — abort"; exit 1;; esac

flash_ab(){ # <partition-base> <image>
  echo ">>> flash ${1}_a"; fb flash "${1}_a" "$IMG/$2"
  echo ">>> flash ${1}_b"; fb flash "${1}_b" "$IMG/$2"
}
flash_one(){ echo ">>> flash ${1}"; fb flash "$1" "$IMG/$2"; }

echo "=== userdata wipe (flash A10 userdata.img) ==="
flash_one userdata userdata.img
echo "=== erase config (FRP) ==="
fb erase config || true

# firmware + bootloader chain (both slots) — IMEI/EFS untouched
flash_ab modem    NON-HLOS.bin
flash_ab sbl1     sbl1.mbn
flash_ab rpm      rpm.mbn
flash_ab tz       tz.mbn
flash_ab devcfg   devcfg.mbn
flash_ab dsp      adspso.bin
flash_one splash  splash.img
flash_ab aboot    emmc_appsboot.mbn
flash_ab dtbo     dtbo.img
flash_ab vbmeta   vbmeta.img
flash_ab boot     boot.img
flash_ab system   system.img
flash_ab vendor   vendor.img
flash_ab mdtp     mdtp.img
flash_ab lksecapp lksecapp.mbn
flash_ab cmnlib   cmnlib_30.mbn
flash_ab cmnlib64 cmnlib64_30.mbn
flash_ab keymaster km4.mbn
flash_ab product  product.img

echo "=== set active slot a ==="
fb --set-active=a

echo "=== DONE flashing A10 (bootloader NOT relocked). Reboot manually when ready. ==="
fb getvar current-slot 2>&1 | grep -i current-slot || true
