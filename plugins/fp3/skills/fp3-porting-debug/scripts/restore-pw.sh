set +e
echo "=== Amp Mode + headphone/speaker volume sane defaults ==="
amixer -c F3 cget name='Amp Mode' 2>/dev/null | tail -2
# restart pipewire stack for the user session
systemctl --user start pipewire pipewire-pulse wireplumber 2>/dev/null
sleep 2
echo "=== pipewire sinks ==="
( wpctl status 2>/dev/null | head -25 ) || ( pactl list short sinks 2>/dev/null )
