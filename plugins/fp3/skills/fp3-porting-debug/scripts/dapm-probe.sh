#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-or-later
# Why is the earpiece silent despite aplay rc=0 + verified mixers?
# Hypothesis: the DAPM path MultiMedia1 -> PRI_MI2S_RX BE -> internal codec ->
# analog EAR does not complete, so the BE never powers and no audio leaves the
# codec. Dump every POWERED-ON DAPM widget while a tone plays -> see where the
# chain breaks (which codec/BE widget stays Off).

# Config lives in fp3-env.sh; every value there has a documented default.
# Resolve symlinks first: these scripts are commonly installed as symlinks in
# /usr/local/bin, where a bare $0 would look for fp3-env.sh next to the symlink.
_self="$(readlink -f "$0")"
for _d in "$(dirname "$_self")" "$(dirname "$_self")/.." "$(dirname "$_self")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

export XDG_RUNTIME_DIR=/run/user/$(id -u)
UH=$HOME

echo "=== free the card ==="
mkdir -p $UH/.config/pulse
printf 'autospawn=no\ndaemon-binary=/bin/true\n' > $UH/.config/pulse/client.conf
systemctl --user stop wireplumber pipewire-pulse.socket pipewire-pulse.service \
	pipewire.socket pipewire.service 2>/dev/null
pkill -9 callaudiod wireplumber pipewire-pulse pipewire 2>/dev/null
pulseaudio -k 2>/dev/null; pkill -9 pulseaudio 2>/dev/null
sleep 2

set_ctl() { amixer -c0 cset name="$1" "$2" >/dev/null 2>&1; }
echo "=== apply earpiece routing ==="
set_ctl 'PRI_MI2S_RX Audio Mixer MultiMedia1' 1
set_ctl 'RX1 MIX1 INP1' 'RX1'
set_ctl 'RDAC2 MUX' 'RX1'
set_ctl 'RX1 Digital Volume' 84
set_ctl 'EAR PA Gain' 'POS_6_DB'
set_ctl 'EAR_S' 1

echo "=== play 8s tone, dump DAPM mid-play ==="
( aplay -D plughw:0,0 $UH/tone8k.wav 2>/dev/null
  aplay -D plughw:0,0 $UH/tone8k.wav 2>/dev/null ) &
APID=$!
sleep 2

echo "--- ALL powered-ON DAPM widgets (path that is actually live) ---"
for f in $(find /sys/kernel/debug/asoc -type f 2>/dev/null); do
	L=$(head -1 "$f" 2>/dev/null)
	case "$L" in
		*": On"*) echo "$L" ;;
	esac
done | sort -u

echo "--- KEY codec/earpiece widgets (On or Off) ---"
for f in $(find /sys/kernel/debug/asoc -type f 2>/dev/null); do
	b=$(basename "$f")
	case "$b" in
		EAR*|RX1*|RDAC*|DAC*|*MI2S*|*PDM*|SpkrMono*|HPHL*|HPHR*)
			echo "$(head -1 "$f" 2>/dev/null)" ;;
	esac
done | sort -u

echo "--- DPCM / BE state files ---"
find /sys/kernel/debug/asoc -name 'state' 2>/dev/null | while read s; do
	echo "$s -> $(cat "$s" 2>/dev/null)"
done | grep -iE 'mi2s|state' | head -20

wait $APID
echo "=== done ==="
