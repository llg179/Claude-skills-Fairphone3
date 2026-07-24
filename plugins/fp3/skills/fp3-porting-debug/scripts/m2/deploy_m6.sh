#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# deploy_m6.sh — NON-crashing clock-work ENTRY decision-capture. One SSR reload,
# read SMEM PA 0x86302a70, decode (FIXED: parse only the hex data column, not the
# address), restore stock, heal. Minimal SSR (2 cycles).

# Config lives in fp3-env.sh; every value there has a documented default.
for _d in "$(dirname "$0")" "$(dirname "$0")/.." "$(dirname "$0")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

set -uo pipefail
cd "$(dirname "$0")"
DEV=fp3@$FP3_DEV_IP; PW="$FP3_PW"
SSHO="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o GlobalKnownHostsFile=/dev/null -o ConnectTimeout=8 -o PreferredAuthentications=password -o PubkeyAuthentication=no"
SSH="sshpass -p $PW ssh $SSHO $DEV"
SCP="sshpass -p $PW scp $SSHO"
FWDIR=/lib/firmware/qcom/msm8953/fairphone/fp3
RP=/sys/class/remoteproc/remoteproc2
SIG=adsp-m6-signed.mbn
PA=0x86302a70
r(){ timeout 25 $SSH "echo $PW | sudo -S bash -c \"$1\"" 2>/dev/null; }

decode(){  # $1 = full smem_peek dump ("0xADDR  <hex>" lines); parse only col 2
python3 - "$1" <<'PY'
import sys,re,struct
txt=sys.argv[1]
hexstr=""
for ln in txt.splitlines():
    m=re.match(r'\s*0x[0-9a-fA-F]+\s+([0-9a-fA-F]+)\s*$', ln)
    if m: hexstr+=m.group(1)
b=bytes.fromhex(hexstr)[:32]
if len(b)<32: print("  (short: %d bytes) raw=%s"%(len(b),hexstr)); sys.exit()
w=struct.unpack("<8I",b)
names=["marker","entry_count","param(r1)","flag(0xdec)","state(0x88)","r17target","handle(0xe18)","gate(0x74)"]
for n,v in zip(names,w): print("  %-14s = 0x%08x  (%d)"%(n,v,v))
if w[0]==0xc0de0051:
    st,tg=w[4],w[5]
    print("  --> marker FIRED. state==r17target ? %s"%("YES -> early-exit @f04bfb5c (NO DAL enable; SSR insufficient, need COLD boot)" if st==tg else "NO -> proceeds to enable/disable (r17target==0xA=%s)"%("ENABLE path"%() if tg==0xa else "gear=0x%x"%tg)))
else:
    print("  --> NO marker (stub did not write; fn not entered this run)")
PY
}

echo "== baseline SMEM @ $PA (stock, before) =="
$SCP smem_peek.py "$DEV:/tmp/" >/dev/null 2>&1
r "python3 /tmp/smem_peek.py $PA 32"

echo "== deploy patched (non-crashing) =="
$SCP "$SIG" "$DEV:/tmp/$SIG" >/dev/null 2>&1
r "cp /tmp/$SIG $FWDIR/adsp.mbn; md5sum $FWDIR/adsp.mbn"

echo "== SSR reload =="
r "echo stop > $RP/state"; sleep 1; r "echo start > $RP/state"; sleep 6
r "echo -n state=; cat $RP/state"

echo "== read SMEM @ $PA =="
DUMP=$(r "python3 /tmp/smem_peek.py $PA 32")
echo "$DUMP"
echo "-- decoded --"
decode "$DUMP"

echo "== restore stock + heal =="
r "cp $FWDIR/adsp.mbn.stockbak $FWDIR/adsp.mbn"
r "echo stop > $RP/state"; sleep 1; r "echo start > $RP/state"; sleep 3
r "echo -n healed=; cat $RP/state; md5sum $FWDIR/adsp.mbn"
