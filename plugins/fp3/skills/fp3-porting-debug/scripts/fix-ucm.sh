set +e
D=/usr/share/alsa/ucm2/conf.d/Fairphone_3
cp "$D/Fairphone_3.conf" "$D/Fairphone_3.conf.bak-slimbus-era" 2>/dev/null
cp "$D/Fairphone_3.conf.bak-precall" "$D/Fairphone_3.conf"
echo "restored .bak-precall (HiFi-only)"
echo "=== alsaucm parse test now ==="
alsaucm -c F3 list _verbs 2>&1 | head
echo "=== HiFi.conf (does it reference valid devices?) ==="
sed -n '1,60p' /usr/share/alsa/ucm2/Fairphone/fp3/HiFi.conf 2>/dev/null
