set +e
S=alsa_output.platform-c051000.sound-card.HiFi__Speaker__sink
pactl set-default-sink "$S" 2>&1
pactl set-sink-mute "$S" 0 2>&1
pactl set-sink-volume "$S" 70% 2>&1
echo "=== sink state ==="
pactl list sinks 2>/dev/null | grep -A3 "Name: $S" | head
pactl get-sink-volume "$S" 2>/dev/null; pactl get-sink-mute "$S" 2>/dev/null
echo "=== quick tone via the sink (paplay) ==="
which paplay speaker-test 2>/dev/null
# generate a short tone into the default sink
( command -v speaker-test >/dev/null && timeout 3 speaker-test -D pulse -c2 -t sine -f 660 -l1 2>&1 | tail -2 )
