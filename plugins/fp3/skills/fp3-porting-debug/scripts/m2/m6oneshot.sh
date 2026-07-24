#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later

# Config lives in fp3-env.sh; every value there has a documented default.
for _d in "$(dirname "$0")" "$(dirname "$0")/.." "$(dirname "$0")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

PW="$FP3_PW"
SSHO="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o GlobalKnownHostsFile=/dev/null -o ConnectTimeout=4 -o PreferredAuthentications=password -o PubkeyAuthentication=no -o ServerAliveInterval=2 -o ServerAliveCountMax=30"
# the whole experiment in ONE remote script (m6 already on disk as adsp.mbn)
REMOTE='
FW=/lib/firmware/qcom/msm8953/fairphone/fp3
RP=/sys/class/remoteproc/remoteproc2
echo DISK_MD5=$(md5sum $FW/adsp.mbn | cut -d" " -f1)
echo stop > $RP/state; sleep 2; echo start > $RP/state; sleep 6
echo STATE=$(cat $RP/state)
echo SMEM=$(python3 /tmp/smem_peek.py 0x86302a70 32 | tr "\n" "|")
cp $FW/adsp.mbn.stockbak $FW/adsp.mbn
echo stop > $RP/state; sleep 2; echo start > $RP/state; sleep 3
echo HEALED=$(cat $RP/state) HEALMD5=$(md5sum $FW/adsp.mbn | cut -d" " -f1)
'
for k in $(seq 1 60); do
  IF=$(ls /sys/class/net 2>/dev/null | grep -E '^enx' | head -1)
  if [ -n "$IF" ]; then
    echo $PW | sudo -S nmcli dev set "$IF" managed no >/dev/null 2>&1
    ip -4 addr show "$IF" 2>/dev/null | grep -q $FP3_HOST_IP || echo $PW | sudo -S ip addr add $FP3_HOST_IP/24 dev "$IF" 2>/dev/null
    echo $PW | sudo -S ip link set "$IF" up 2>/dev/null
  fi
  # first ensure smem_peek is present (quick probe)
  if timeout 6 sshpass -p $PW ssh $SSHO fp3@$FP3_DEV_IP 'echo ALIVE' 2>/dev/null | grep -q ALIVE; then
    echo "=== GOT WINDOW (iter $k) — pushing smem_peek + running oneshot ==="
    timeout 10 sshpass -p $PW scp $SSHO smem_peek.py fp3@$FP3_DEV_IP:/tmp/ >/dev/null 2>&1
    OUT=$(timeout 40 sshpass -p $PW ssh $SSHO fp3@$FP3_DEV_IP "echo $PW | sudo -S bash -c '$REMOTE'" 2>/dev/null)
    echo "$OUT"
    echo "$OUT" | grep -q HEALED && { echo "=== ONESHOT COMPLETE ==="; exit 0; }
    echo "(oneshot incomplete, retrying)"
  else
    echo "iter $k: no ssh ($(ping -c1 -W1 $FP3_DEV_IP >/dev/null 2>&1 && echo pOK || echo pFAIL)) iface=${IF:-none}"
  fi
  # ☠️ GUARDRAIL (§8): NEVER host-side USB unbind/rebind (or remove/authorized/USBDEVFS_RESET/
  # ip-link cycling) to un-jam the link — it does NOT clear a device-side NCM/gadget jam AND the
  # host /mnt work disk is USB-attached, so a host USB reset can unmount /mnt (data loss, happened
  # 2026-07-11). The device SELF-RECOVERS in minutes; only PASSIVELY poll. (Was: usb unbind/bind.)
  sleep 4
done
echo "NO COMPLETE in window"; exit 1
