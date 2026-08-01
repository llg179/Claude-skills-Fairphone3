#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# deployed-provenance.sh — what is actually running on the device, and which
# artifact did each piece come from?
#
# Run it before you trust a measurement and after every deploy. It answers one
# question for the kernel image, the device tree and the module tree: does this
# file match the installed package, or was it put there by hand? Anything
# hand-deployed is not wrong by itself - it is how a one-change experiment is
# meant to work - but it must be *named*: which branch, which artifact. A file
# that nobody can trace back to a branch is the failure mode this exists for.
#
# The case that produced it (2026-08-01): a DTB built in a worktree parked on
# wip/<base>/camera was copied to /boot. That branch carries the base plus the
# camera commits and nothing else, so the deployed tree lost the audio, voice,
# charger, sensor and debug layers at once. The battery read 0% - not flat (it
# was at 91% and charging) but undescribed: no charger@1000 in the tree, so no
# pmi632-battery power supply, so nothing to ask. The file *had* been md5
# verified, against the worktree it came from rather than against the package,
# which is a check that passes and proves nothing.
#
# Usage: ./deployed-provenance.sh [--pkg linux-fp3]
#
# Exit status: 0 = everything traces to the package, 1 = something is
# hand-deployed or missing (listed), 2 = could not measure.
#
# ☠️ All device-side logic is in ONE quoted here-doc piped to `sh -s`, not in
# per-command ssh strings. Nesting $(...) inside ssh inside sudo inside sh -c
# strips a level of quoting per layer, and the way that fails is silent: an
# unexpanded $(uname -r) makes `find` search a path that does not exist, which
# prints nothing, which reads as "no leftovers found". A false OK from the tool
# built to catch false OKs. Measured here on the first run - it reported a clean
# module tree while two .ko.bak files were sitting in it.
set -u
cd "$(dirname "$0")"; source ./fp3-env.sh

PKG=linux-fp3
[ "${1:-}" = "--pkg" ] && PKG="${2:?--pkg needs a package name}"

SSH(){ sshpass -p "$FP3_PW" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=8 \
        "fp3@$FP3_SSH_IP" "$@"; }

if ! SSH true 2>/dev/null; then
  echo "no ssh to $FP3_SSH_IP - is the device up in pmOS?" >&2; exit 2
fi

device_script=$(cat <<'DEVICE'
set -u
drift=0

echo "=== running kernel ==="
uname -a
echo "installed package: $(apk list -I "$PKG" 2>/dev/null | head -1)"

echo
echo "=== device tree ==="
# Read the fdt from extlinux rather than assuming the filename: this has to
# inspect the file that actually boots, not the one that usually does.
fdt=$(sed -n '/^label postmarketOS$/,/^$/p' /boot/extlinux/extlinux.conf 2>/dev/null |
      sed -n 's/^[[:space:]]*fdt[[:space:]]*//p' | head -1)
if [ -z "$fdt" ]; then
	echo "  FAIL: no fdt line in the postmarketOS label of extlinux.conf"
	drift=1
else
	board=$(basename "$fdt")
	pkgdtb=$(apk info -L "$PKG" 2>/dev/null | grep "/$board\$" | head -1)
	echo "  extlinux fdt : $fdt"
	if [ -z "$pkgdtb" ]; then
		echo "  FAIL: $PKG installs no $board - nothing to compare against"
		drift=1
	else
		b=$(md5sum "/boot$fdt" | cut -d' ' -f1)
		p=$(md5sum "/$pkgdtb" | cut -d' ' -f1)
		owner=$(apk info -W "/$pkgdtb" 2>/dev/null | sed 's/.*owned by //')
		echo "  booted       : $b  /boot$fdt  ($(stat -c %s "/boot$fdt") bytes)"
		echo "  package      : $p  /$pkgdtb  ($(stat -c %s "/$pkgdtb") bytes, $owner)"
		if [ "$b" = "$p" ]; then
			echo "  OK: the booted DTB is the one the package shipped"
		else
			echo "  HAND-DEPLOYED: the booted DTB is not $owner's."
			echo "    Name its origin before trusting anything measured on it:"
			echo "    which branch, which artifact. A DTB built from"
			echo "    wip/<base>/<cat> carries that category only - every other"
			echo "    layer is missing from it."
			drift=1
		fi
	fi
fi

echo
echo "=== module tree ==="
# apk audit reports files that differ from what the package installed, which is
# exactly the shape of a hot-swapped .ko.
mods=$(apk audit --system 2>/dev/null | awk '/lib\/modules\/.*\.ko/ {print $2}')
if [ -n "$mods" ]; then
	echo "$mods" | sed 's|^|  HAND-DEPLOYED: /|'
	drift=1
else
	echo "  OK: every module matches the installed package"
fi
strays=$(find "/lib/modules/$(uname -r)" \( -name '*.orig' -o -name '*.bak' \) 2>/dev/null)
if [ -n "$strays" ]; then
	echo "$strays" | sed 's|^|  LEFTOVER: |'
	drift=1
else
	echo "  OK: no .orig/.bak leftovers"
fi

echo
echo "=== live tree: which layers are described ==="
# The md5 above is the invariant; these say *what stopped working*, and they
# still catch a DTB flashed inside a boot.img that never touched /boot.
# Only layers that own a node are listed - SMGR is a QMI/QRTR client with no
# node of its own, and the debug watchdog is a driver change - so this list
# stays honest rather than complete.
DT=/proc/device-tree
t() { if [ "$2" = 0 ]; then echo "  ok      $1"; else echo "  MISSING $1"; return 1; fi; }
[ -d "$DT/soc@0/spmi@200f000/pmic@2/charger@1000" ]
t "charger: charger@1000 under the PMI632" $? || drift=1
grep -qa simple-battery "$DT/battery/compatible" 2>/dev/null
t "charger: battery node" $? || drift=1
[ -d "$DT/soc@0/slim-ngd@c140000/slim@1/codec@1,0" ]
t "audio:   WCD9335 codec on the SLIMbus NGD" $? || drift=1
grep -rlaq imx363 "$DT/" 2>/dev/null
t "camera:  imx363 sensor node" $? || drift=1

echo
echo "__DRIFT=$drift"
DEVICE
)

# Ship the script as base64 rather than on stdin: `sudo -S` takes its password
# from stdin, so a here-doc piped to the same ssh command is eaten by sudo (or
# fed to the shell as if it were the password) and the run dies with no output.
b64=$(printf '%s\n' "$device_script" | base64 -w0)
out=$(SSH "echo '$FP3_PW' | sudo -S sh -c 'echo $b64 | base64 -d >/tmp/dp.sh; PKG=$PKG sh /tmp/dp.sh; rm -f /tmp/dp.sh'" 2>/dev/null)

echo "$out" | grep -v '^__DRIFT='
drift=$(echo "$out" | sed -n 's/^__DRIFT=//p')
[ -n "$drift" ] || { echo "could not measure the device" >&2; exit 2; }

echo
if [ "$drift" = 0 ]; then
	echo "VERDICT: everything on the device traces to $PKG."
else
	echo "VERDICT: something is hand-deployed or missing (above). Hand-deployed"
	echo "         is fine for a one-change experiment and only if you say which"
	echo "         branch and which artifact it came from - otherwise restore"
	echo "         from the package before measuring:"
	echo "           sudo cp /boot/dtbs/qcom/<board>.dtb /boot/<board>.dtb"
	echo "           sudo sync && sudo reboot"
fi
exit "$drift"
