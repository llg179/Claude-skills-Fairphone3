# SPDX-License-Identifier: GPL-2.0-or-later
set +e
echo "=== mixer controls (quinary / speaker / aw8898 routing) ==="
amixer -c F3 scontrols 2>/dev/null | head
echo "--- numid controls matching Quin/QUIN/MultiMedia1/AW ---"
amixer -c F3 controls 2>/dev/null | grep -iE "quin|aw|spk|speaker|multimedia1|mm1" | head -20
echo "=== free the card (stop pipewire/pa briefly) ==="
systemctl --user stop pipewire pipewire-pulse wireplumber 2>/dev/null
pkill -f pipewire 2>/dev/null; pkill -f wireplumber 2>/dev/null; sleep 1
echo "=== try enabling MM1->Quinary route + play 440Hz 2s ==="
# Common qcom q6routing control name pattern: "QUIN_MI2S_RX Audio Mixer MultiMedia1"
amixer -c F3 cset name='QUIN_MI2S_RX Audio Mixer MultiMedia1' 1 2>&1 | tail -1
speaker-test -D plughw:F3,0 -c2 -t sine -f 440 -l1 2>&1 | tail -4 || aplay -D plughw:F3,0 /dev/zero 2>&1 | tail -2
