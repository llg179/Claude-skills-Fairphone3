#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-or-later
# Bisection: does the WCD ANALOG codec produce ANY sound? Route MM1 -> PRI_MI2S
# -> WCD and drive the HEADPHONE (HPHL/HPHR PA) instead of EAR. ~15s tone so the
# user can listen on plugged-in headphones. If HPH sounds but EAR didn't ->
# analog DAC works, earpiece pin is the fault. If HPH also silent -> whole WCD
# analog output path is dead.

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
systemctl --user stop wireplumber pipewire-pulse.socket pipewire.socket pipewire.service 2>/dev/null
pkill -9 callaudiod wireplumber pipewire-pulse pipewire 2>/dev/null
pulseaudio -k 2>/dev/null; pkill -9 pulseaudio 2>/dev/null
sleep 2

set_ctl() { amixer -c0 cset name="$1" "$2" >/dev/null 2>&1; }
get_ctl() { amixer -c0 cget name="$1" | awk -F= '/: values/{print $2; exit}'; }

echo "=== reset stray routes, set HEADPHONE routing ==="
# clear earpiece + speaker leftovers to isolate the HPH path
set_ctl 'EAR_S' 0
set_ctl 'QUIN_MI2S_RX Audio Mixer MultiMedia1' 0
# headphone path on WCD analog
set_ctl 'PRI_MI2S_RX Audio Mixer MultiMedia1' 1
set_ctl 'RX1 MIX1 INP1' 'RX1'
set_ctl 'RX2 MIX1 INP1' 'RX2'
set_ctl 'RX1 Digital Volume' 84
set_ctl 'RX2 Digital Volume' 84
echo "PRImix=$(get_ctl 'PRI_MI2S_RX Audio Mixer MultiMedia1') RX1in=$(get_ctl 'RX1 MIX1 INP1') RX2in=$(get_ctl 'RX2 MIX1 INP1') RX1vol=$(get_ctl 'RX1 Digital Volume') RX2vol=$(get_ctl 'RX2 Digital Volume')"

echo "=== start ~16s tone ==="
rm -f /tmp/aplay.err; touch /tmp/play.on
( n=0; while [ -f /tmp/play.on ] && [ $n -lt 4 ]; do
	aplay -D plughw:0,0 $UH/tone8k.wav 2>>/tmp/aplay.err; n=$((n+1))
  done ) &
PLPID=$!
sleep 2
echo "--- aplay stderr (empty=OK) ---"; sort -u /tmp/aplay.err 2>/dev/null | head
echo "--- HPH widgets during play ---"
find "$ASOC" -type f 2>/dev/null | while read -r f; do
	b=$(basename "$f")
	case "$b" in HPH*|RX1*|RX2*|RDAC*|EAR_S|DAC_REF|RX_BIAS) echo "$(head -1 "$f" 2>/dev/null)" ;; esac
done | grep -iE 'HPHL PA|HPHR PA|HPHL DAC|HPHR DAC|HPHL:|HPHR:|RX1 INT|RX2 INT|RDAC2 MUX|RX_BIAS|DAC_REF|EAR_S' | sort -u
wait $PLPID
echo "aplay done"
echo "=== leave routing set ~10s more for listening ==="
aplay -D plughw:0,0 $UH/tone8k.wav 2>/dev/null
aplay -D plughw:0,0 $UH/tone8k.wav 2>/dev/null
set_ctl 'PRI_MI2S_RX Audio Mixer MultiMedia1' 0
echo "=== done ==="
