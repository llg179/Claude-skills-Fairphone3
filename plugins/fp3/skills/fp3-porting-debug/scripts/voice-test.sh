#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-or-later
# Live in-call audio test harness for FP3 q6voice.
#   $1 = earpiece | speaker   $2 = duration seconds
# Frees the ALSA card from PulseAudio, sets the Voice Call routing, then holds
# the VoiceMMode1 PCM open (both dirs) in the foreground so the CS-voice DSP
# session stays up for the call.

# Config lives in fp3-env.sh; every value there has a documented default.
# Resolve symlinks first: these scripts are commonly installed as symlinks in
# /usr/local/bin, where a bare $0 would look for fp3-env.sh next to the symlink.
_self="$(readlink -f "$0")"
for _d in "$(dirname "$_self")" "$(dirname "$_self")/.." "$(dirname "$_self")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

export XDG_RUNTIME_DIR=/run/user/$(id -u)
DEV="${1:-earpiece}"
DUR="${2:-120}"

# stop callaudiod (it would re-switch PA to the Voice Call profile) and kill PA
# (autospawn=no in client.conf keeps it dead) so nothing grabs the voice PCM
pkill -9 callaudiod 2>/dev/null
pulseaudio -k 2>/dev/null
pkill -9 pulseaudio 2>/dev/null
sleep 1

if [ "$DEV" = "speaker" ]; then
	alsaucm -c Fairphone_3 set _verb "Voice Call" set _enadev Speaker set _enadev Mic >/dev/null 2>&1
else
	alsaucm -c Fairphone_3 set _verb "Voice Call" set _enadev Earpiece set _enadev Mic >/dev/null 2>&1
fi

EAR=$(amixer -c0 cget name=EAR_S | grep -m1 ': values' | sed 's/.*=//')
PRV=$(amixer -c0 cget name='PRI_MI2S_RX Voice Mixer VoiceMMode1' | grep -m1 ': values' | sed 's/.*=//')
QSV=$(amixer -c0 cget name='QUIN_MI2S_RX Voice Mixer VoiceMMode1' | grep -m1 ': values' | sed 's/.*=//')
echo "ROUTING=$DEV EAR_S=$EAR PRI_voice=$PRV QUIN_voice=$QSV"

exec timeout "$DUR" python3 $HOME/voicehold.py hw:0,4
