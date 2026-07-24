set +e
echo "=== uptime/kernel ==="
uname -r; cat /proc/uptime
echo "=== remoteproc (adsp/lpass) state ==="
for r in /sys/class/remoteproc/remoteproc*; do echo "$r: name=$(cat $r/name 2>/dev/null) state=$(cat $r/state 2>/dev/null) fw=$(cat $r/firmware 2>/dev/null)"; done
echo "=== dmesg: remoteproc/adsp/lpass/pil ==="
dmesg | grep -iE "remoteproc|adsp|lpass|q6v5|pas|pil|mdt|firmware" | tail -40
echo "=== dmesg: qrtr/qmi/servreg/pdr/pd-mapper ==="
dmesg | grep -iE "qrtr|qmi|servreg|pdr|pd.?mapper|sysmon|domain" | tail -40
echo "=== dmesg: slim/ngd/bam/dma ==="
dmesg | grep -iE "slim|ngd|bam|dma" | tail -50
echo "=== slimbus devices ==="
ls -l /sys/bus/slimbus/devices/ 2>/dev/null
echo "=== dma channels (bam) ==="
ls /sys/class/dma/ 2>/dev/null
echo "=== qrtr services (if tool) ==="
cat /sys/kernel/debug/qrtr/* 2>/dev/null | head -40
