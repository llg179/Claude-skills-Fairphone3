set +e
echo "=== ucm2 lib includes exist? ==="
ls -l /usr/share/alsa/ucm2/lib/card-init.conf /usr/share/alsa/ucm2/lib/ctl-remap.conf 2>&1
echo "=== ucm2 version / structure ==="
ls /usr/share/alsa/ucm2/ | head; cat /usr/share/alsa/ucm2/version 2>/dev/null
echo "=== how does ucm match? conf.d listing ==="
ls -l /usr/share/alsa/ucm2/conf.d/Fairphone_3/
echo "=== verbose alsaucm (ALSA debug) ==="
ALSA_DEBUG=1 alsaucm -c "Fairphone 3" list _verbs 2>&1 | head
echo "--- try by exact longname ---"
alsaucm -c "Fairphone_3" list _verbs 2>&1 | head -3
echo "=== does pipewire see the alsa DEVICE at all? ==="
pw-cli ls Device 2>/dev/null | grep -iE "alsa|F3|api.alsa|device.name" | head
echo "=== wireplumber alsa errors in journal ==="
journalctl --user -u wireplumber --no-pager 2>/dev/null | grep -iE "ucm|alsa|F3|error|fail" | tail -15
