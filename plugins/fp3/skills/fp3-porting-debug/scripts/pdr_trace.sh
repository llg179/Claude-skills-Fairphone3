#!/bin/bash
set +e
C=/sys/kernel/debug/dynamic_debug/control
for x in 'module pdr_interface +p' 'module qcom_pd_mapper +p' 'module slim_qcom_ngd_ctrl +p' 'file qcom_pd_mapper.c +p' 'file pdr_interface.c +p'; do echo "$x" > $C 2>/dev/null; done
dmesg -C
echo "--- restarting adsp (remoteproc2) ---"
echo stop  > /sys/class/remoteproc/remoteproc2/state; sleep 2
echo start > /sys/class/remoteproc/remoteproc2/state; sleep 6
echo "=== dmesg after adsp restart ==="
dmesg | grep -iE 'pdr|pdm|servreg|audio_pd|avs/audio|slim|ngd|laddr|capabil|framer|domain|notif|locator|adsp|remoteproc2'
