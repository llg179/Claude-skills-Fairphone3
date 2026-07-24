#!/bin/sh
# Call-independent earpiece OUTPUT test with VERIFIED mixer state + MI2S clock check.
# Routes MultiMedia1 -> PRI_MI2S_RX -> PM8953 WCD earpiece, plays a tone, and
# inspects whether the PRI_MI2S bit-clock actually runs. No inline-over-SSH
# quoting: this file is scp'd and run locally on the device.

# Config lives in fp3-env.sh; every value there has a documented default.
for _d in "$(dirname "$0")" "$(dirname "$0")/.." "$(dirname "$0")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

export XDG_RUNTIME_DIR=/run/user/$(id -u)

echo "=== free the card from PulseAudio ==="
pkill -9 -f voicehold.py 2>/dev/null
pulseaudio -k 2>/dev/null
pkill -9 pulseaudio 2>/dev/null
sleep 1

set_ctl() {
	amixer -c0 cset name="$1" "$2" >/dev/null 2>&1
}
get_ctl() {
	# print just the numeric/enum value(s), robust to local exec (no SSH quoting)
	amixer -c0 cget name="$1" | awk -F= '/: values/{print $2; exit}'
}

echo "=== apply earpiece routing ==="
set_ctl 'PRI_MI2S_RX Audio Mixer MultiMedia1' 1
set_ctl 'RX1 MIX1 INP1' 'RX1'
set_ctl 'RDAC2 MUX' 'RX1'
set_ctl 'RX1 Digital Volume' 84
set_ctl 'EAR PA Gain' 'POS_6_DB'
set_ctl 'EAR_S' 1

echo "--- readback (VERIFIED) ---"
echo "PRI_MI2S_RX Audio Mixer MultiMedia1 = $(get_ctl 'PRI_MI2S_RX Audio Mixer MultiMedia1')"
echo "RX1 MIX1 INP1                       = $(get_ctl 'RX1 MIX1 INP1')"
echo "RDAC2 MUX                           = $(get_ctl 'RDAC2 MUX')"
echo "RX1 Digital Volume                  = $(get_ctl 'RX1 Digital Volume')"
echo "EAR_S                               = $(get_ctl 'EAR_S')"

echo "=== MI2S clock BEFORE play (clk_summary | grep -i mi2s) ==="
grep -i 'mi2s\|pri_mi2s\|lpass' /sys/kernel/debug/clk/clk_summary 2>/dev/null | head -40 || echo "(clk_summary not accessible)"

echo "=== play 4s tone to plughw:0,0 (PRI_MI2S_RX) ==="
( aplay -D plughw:0,0 $HOME/tone8k.wav 2>&1 & APID=$!
  sleep 1.5
  echo "--- MI2S clock DURING play ---"
  grep -i 'mi2s\|pri_mi2s\|lpass' /sys/kernel/debug/clk/clk_summary 2>/dev/null | head -40 || echo "(clk_summary not accessible)"
  wait $APID
  echo "aplay rc=$?" )

echo "=== dmesg tail (afe/q6/wcd/asoc) ==="
dmesg 2>/dev/null | tail -25 | grep -iE 'afe|q6|wcd|asoc|mi2s|cdc|codec' || dmesg 2>/dev/null | tail -8

set_ctl 'PRI_MI2S_RX Audio Mixer MultiMedia1' 0
set_ctl 'EAR_S' 0
echo "=== done ==="
