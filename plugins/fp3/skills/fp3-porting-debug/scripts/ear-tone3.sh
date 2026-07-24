#!/bin/sh
# Earpiece OUTPUT test v3 -- GUARANTEE the ALSA card is free first.
# Previous run failed with "Resource busy": PA auto-respawned / PipeWire held
# hw:0,0 before aplay could open it. Here we set autospawn=no, stop ALL user
# audio services, kill leftovers, then prove (fuser) the PCM is free before play.

# Config lives in fp3-env.sh; every value there has a documented default.
for _d in "$(dirname "$0")" "$(dirname "$0")/.." "$(dirname "$0")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

export XDG_RUNTIME_DIR=/run/user/$(id -u)
UH=$HOME

echo "=== disable PA autospawn ==="
mkdir -p $UH/.config/pulse
printf 'autospawn=no\ndaemon-binary=/bin/true\n' > $UH/.config/pulse/client.conf

echo "=== stop user audio services ==="
systemctl --user stop wireplumber pipewire-pulse.socket pipewire-pulse.service \
	pipewire.socket pipewire.service pulseaudio.socket pulseaudio.service 2>/dev/null
pkill -9 callaudiod 2>/dev/null
pkill -9 wireplumber 2>/dev/null
pkill -9 pipewire-pulse 2>/dev/null
pkill -9 pipewire 2>/dev/null
pulseaudio -k 2>/dev/null
pkill -9 pulseaudio 2>/dev/null
sleep 2

echo "=== who holds the playback PCM now? ==="
fuser -v /dev/snd/pcmC0D0p 2>&1 || echo "(fuser: nobody holds pcmC0D0p -- good)"
echo "--- audio procs still alive ---"
ps -eo pid,comm 2>/dev/null | grep -iE 'pulse|pipewire|wireplumber|callaudio' || echo "(none)"

set_ctl() { amixer -c0 cset name="$1" "$2" >/dev/null 2>&1; }
get_ctl() { amixer -c0 cget name="$1" | awk -F= '/: values/{print $2; exit}'; }

echo "=== apply earpiece routing ==="
set_ctl 'PRI_MI2S_RX Audio Mixer MultiMedia1' 1
set_ctl 'RX1 MIX1 INP1' 'RX1'
set_ctl 'RDAC2 MUX' 'RX1'
set_ctl 'RX1 Digital Volume' 84
set_ctl 'EAR PA Gain' 'POS_6_DB'
set_ctl 'EAR_S' 1
echo "PRImix=$(get_ctl 'PRI_MI2S_RX Audio Mixer MultiMedia1') INP1=$(get_ctl 'RX1 MIX1 INP1') RDAC2=$(get_ctl 'RDAC2 MUX') vol=$(get_ctl 'RX1 Digital Volume') EAR_S=$(get_ctl 'EAR_S')"

echo "=== play 4s tone to plughw:0,0 ==="
( aplay -D plughw:0,0 $UH/tone8k.wav 2>&1 & APID=$!
  sleep 1.5
  echo "--- ACTIVE clocks during play (enable_cnt>0) ---"
  awk 'NR>2 && $2+0>0 {print $1, "en="$2, "rate="$5}' /sys/kernel/debug/clk/clk_summary 2>/dev/null | grep -iE 'lpass|mi2s|mclk|codec' | head -30
  wait $APID
  echo "aplay rc=$?" )

echo "=== dmesg tail ==="
dmesg 2>/dev/null | tail -30 | grep -iE 'afe|q6|wcd|asoc|mi2s|cdc|codec|pcm' || echo "(no matching dmesg lines)"

set_ctl 'PRI_MI2S_RX Audio Mixer MultiMedia1' 0
set_ctl 'EAR_S' 0
echo "=== done (restore PA autospawn separately) ==="
