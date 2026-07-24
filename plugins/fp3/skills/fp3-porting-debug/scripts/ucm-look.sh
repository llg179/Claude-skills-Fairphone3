set +e
D=/usr/share/alsa/ucm2/conf.d/Fairphone_3
echo "############ CURRENT Fairphone_3.conf ############"
cat "$D/Fairphone_3.conf" 2>/dev/null
echo ""; echo "############ .bak-precall ############"
cat "$D/Fairphone_3.conf.bak-precall" 2>/dev/null
echo ""; echo "############ diff (current vs bak) ############"
diff "$D/Fairphone_3.conf.bak-precall" "$D/Fairphone_3.conf" 2>/dev/null
echo ""; echo "############ /usr/share/alsa/ucm2/Fairphone/fp3 contents ############"
ls -l /usr/share/alsa/ucm2/Fairphone/fp3 2>/dev/null
echo "=== alsaucm parse test ==="
alsaucm -c F3 list _verbs 2>&1 | head
