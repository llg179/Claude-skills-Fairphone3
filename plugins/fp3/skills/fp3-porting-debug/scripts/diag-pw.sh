set +e
echo "=== Amp Mode enum items ==="
amixer -c F3 cget numid=$(amixer -c F3 controls | grep -i "'Amp Mode'" | sed 's/numid=//;s/,.*//') 2>/dev/null
echo "=== Headphone/Mic Jack switches ==="
amixer -c F3 sget 'Headphone Jack' 2>/dev/null | tail -2
echo "=== UCM present for this card? ==="
ls -l /usr/share/alsa/ucm2/ 2>/dev/null | grep -iE "fairphone|fp3|msm8953|qcom|sdm" 
find /usr/share/alsa/ucm2 -iname "*fairphone*" -o -iname "*fp3*" 2>/dev/null | head
echo "=== card longname (what UCM must match) ==="
cat /proc/asound/card0/id 2>/dev/null; cat /sys/class/sound/card0/id 2>/dev/null
echo "--- wireplumber alsa: why no node? journal ---"
journalctl --user -u wireplumber --no-pager 2>/dev/null | tail -15
echo "--- pw-cli list nodes (alsa) ---"
pw-cli ls Node 2>/dev/null | grep -iE "alsa|F3|node.name" | head
