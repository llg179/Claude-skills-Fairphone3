#!/bin/sh
# Call-independent earpiece OUTPUT test: route MultiMedia1 -> PRI_MI2S_RX ->
# PM8953 WCD earpiece and play a local tone. Proves codec earpiece + MI2S
# clocking independent of the modem/q6voice path.

# Config lives in fp3-env.sh; every value there has a documented default.
for _d in "$(dirname "$0")" "$(dirname "$0")/.." "$(dirname "$0")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

export XDG_RUNTIME_DIR=/run/user/$(id -u)
pkill -9 -f voicehold.py 2>/dev/null
pulseaudio -k 2>/dev/null
pkill -9 pulseaudio 2>/dev/null
sleep 1

amixer -c0 cset name='PRI_MI2S_RX Audio Mixer MultiMedia1' 1 >/dev/null 2>&1
amixer -c0 cset name='RX1 MIX1 INP1' 'RX1'   >/dev/null 2>&1
amixer -c0 cset name='RDAC2 MUX'    'RX1'     >/dev/null 2>&1
amixer -c0 cset name='RX1 Digital Volume' 84  >/dev/null 2>&1
amixer -c0 cset name='EAR_S' 1                >/dev/null 2>&1
echo "routing: PRImix=$(amixer -c0 cget name='PRI_MI2S_RX Audio Mixer MultiMedia1'|grep -m1 ': values'|sed 's/.*=//') EAR_S=$(amixer -c0 cget name='EAR_S'|grep -m1 ': values'|sed 's/.*=//')"
echo ">>> playing 3s tone to EARPIECE (plughw:0,0) <<<"
aplay -D plughw:0,0 $HOME/tone8k.wav 2>&1
RC=$?
echo "aplay rc=$RC"
amixer -c0 cset name='PRI_MI2S_RX Audio Mixer MultiMedia1' 0 >/dev/null 2>&1
amixer -c0 cset name='EAR_S' 0 >/dev/null 2>&1
echo done
