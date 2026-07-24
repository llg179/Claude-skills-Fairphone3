#!/bin/bash
# deploy_m5.sh — NON-crashing clock-work ENTRY exfil. Deploy patched fw, ONE SSR
# reload (ADSP boots normally, trampoline aggregates counters into SMEM item-469),
# read SMEM PA 0x86302a70, decode, restore stock, heal. MINIMAL SSR (2 cycles).
# Every ssh has a hard timeout so a stuck SSR can't hang us.

# Config lives in fp3-env.sh; every value there has a documented default.
for _d in "$(dirname "$0")" "$(dirname "$0")/.." "$(dirname "$0")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

set -uo pipefail
cd "$(dirname "$0")"
DEV=fp3@$FP3_DEV_IP; PW="$FP3_PW"
SSHO="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o GlobalKnownHostsFile=/dev/null -o ConnectTimeout=8"
SSH="sshpass -p $PW ssh $SSHO $DEV"
SCP="sshpass -p $PW scp $SSHO"
FWDIR=/lib/firmware/qcom/msm8953/fairphone/fp3
RP=/sys/class/remoteproc/remoteproc2
SIG=adsp-m5-signed.mbn
PA=0x86302a70
r(){ timeout 25 $SSH "echo $PW | sudo -S bash -c \"$1\"" 2>/dev/null; }

decode(){  # decode the 8-word record from the hex dump python prints
python3 - "$1" <<'PY'
import sys,re
h=re.findall(r"[0-9a-fA-F]{2}",sys.argv[1])
if len(h)<32: print("  (short read: %d bytes)"%len(h)); sys.exit()
b=bytes(int(x,16) for x in h[:32])
import struct
w=struct.unpack("<8I",b)
names=["marker","entry_count","handle_null_count","gate_zero_count",
       "first_null_ctx","last_handle","last_gate","last_ctx"]
mk = "  <-- FIRED (0xc0de0050)" if w[0]==0xc0de0050 else "  <-- no marker (stub did not write)"
for n,v in zip(names,w):
    print("  %-18s = 0x%08x  (%d)%s"%(n,v,v, mk if n=="marker" else ""))
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
