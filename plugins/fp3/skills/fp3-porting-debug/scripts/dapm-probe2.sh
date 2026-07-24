#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-or-later
# DAPM probe v2 -- fixes: (1) card name "Fairphone 3" has a SPACE, so iterate
# find output space-safely with `while read -r`; (2) keep a CONTINUOUS tone
# playing while we sample state; (3) capture aplay stderr (catch Resource busy).

# Config lives in fp3-env.sh; every value there has a documented default.
for _d in "$(dirname "$0")" "$(dirname "$0")/.." "$(dirname "$0")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

export XDG_RUNTIME_DIR=/run/user/$(id -u)
UH=$HOME
ASOC=/sys/kernel/debug/asoc

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

echo "=== debugfs asoc structure (top level) ==="
ls -1 "$ASOC" 2>/dev/null

echo "=== start CONTINUOUS tone ==="
rm -f /tmp/aplay.err; touch /tmp/play.on
( while [ -f /tmp/play.on ]; do
	aplay -D plughw:0,0 $UH/tone8k.wav 2>>/tmp/aplay.err
  done ) &
PLPID=$!
sleep 2
echo "--- aplay stderr so far (empty = playing OK) ---"
cat /tmp/aplay.err 2>/dev/null | sort -u | head

echo "--- MultiMedia1 DPCM state WHILE playing ---"
cat "$ASOC/Fairphone 3/MultiMedia1/state" 2>/dev/null

echo "--- ALL powered-ON DAPM widgets (space-safe) ---"
find "$ASOC" -type f 2>/dev/null | while read -r f; do
	L=$(head -1 "$f" 2>/dev/null)
	case "$L" in *": On"*) echo "$L" ;; esac
done | sort -u

echo "--- KEY widgets state (On/Off) ---"
find "$ASOC" -type f 2>/dev/null | while read -r f; do
	b=$(basename "$f")
	case "$b" in
		EAR*|RX1*|RX2*|RDAC*|DAC*|*MI2S*|*PDM*|HPH*|SpkrMono*|ADC*|DEC*)
			echo "$(head -1 "$f" 2>/dev/null)" ;;
	esac
done | sort -u

echo "--- active LPASS clocks (enable_cnt>0) ---"
awk 'NR>2 && $2+0>0 {print $1" en="$2" rate="$5}' /sys/kernel/debug/clk/clk_summary 2>/dev/null

rm -f /tmp/play.on
sleep 1; kill $PLPID 2>/dev/null
set_ctl 'PRI_MI2S_RX Audio Mixer MultiMedia1' 0
set_ctl 'EAR_S' 0
echo "=== done ==="
