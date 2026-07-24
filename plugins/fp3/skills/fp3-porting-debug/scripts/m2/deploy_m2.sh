#!/bin/bash
# deploy_m2.sh — deploy the M2 trampoline image, force ONE ADSP crash, capture the
# devcoredump, extract the trace, then RESTORE stock and heal the ADSP.
# Runs from the laptop; drives the FP3 over SSH. Reversible; single controlled crash.

# Config lives in fp3-env.sh; every value there has a documented default.
for _d in "$(dirname "$0")" "$(dirname "$0")/.." "$(dirname "$0")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

set -uo pipefail
cd "$(dirname "$0")"

DEV=fp3@$FP3_DEV_IP
PW="$FP3_PW"
SSH="sshpass -p $PW ssh -o StrictHostKeyChecking=no -o ConnectTimeout=8 $DEV"
SCP="sshpass -p $PW scp -o StrictHostKeyChecking=no"
FWDIR=/lib/firmware/qcom/msm8953/fairphone/fp3
SIG=adsp-m2-signed.mbn
RP=/sys/class/remoteproc/remoteproc2
DRP=/sys/kernel/debug/remoteproc/remoteproc2
sudo_() { $SSH "echo $PW | sudo -S bash -c '$1'" 2>/dev/null; }

[ -f "$SIG" ] || { echo "ERROR: $SIG missing — run build_m2.sh first"; exit 1; }

echo "== 0. sanity =="; $SSH 'uname -r; cat '"$RP"'/name '"$RP"'/state' || { echo "device unreachable"; exit 1; }

echo "== 1. one-time stock backup =="
sudo_ "test -f $FWDIR/adsp.mbn.stockbak || cp $FWDIR/adsp.mbn $FWDIR/adsp.mbn.stockbak; ls -l $FWDIR/adsp.mbn.stockbak"

echo "== 2. arm capture: coredump=enabled, recovery=disabled (one crash, no reboot-loop) =="
sudo_ "echo enabled > $RP/coredump 2>/dev/null || echo enabled > $DRP/coredump; echo disabled > $DRP/recovery 2>/dev/null; \
       echo -n 'coredump='; cat $RP/coredump 2>/dev/null || cat $DRP/coredump; echo -n ' recovery='; cat $DRP/recovery 2>/dev/null"

echo "== 3. deploy patched image =="
$SCP "$SIG" "$DEV:/tmp/$SIG"
sudo_ "cp /tmp/$SIG $FWDIR/adsp.mbn; md5sum $FWDIR/adsp.mbn"

echo "== 4. load patched fw (SSR): expect the trampoline to crash the ADSP once =="
sudo_ "echo stop > $RP/state; sleep 1; echo start > $RP/state" || true
sleep 5

echo "== 5. look for the devcoredump =="
CD=$(sudo_ "ls -d /sys/class/devcoredump/devcd* 2>/dev/null | head -1")
echo "devcoredump node: ${CD:-<none>}"
if [ -n "${CD:-}" ]; then
  sudo_ "cat $CD/data > /tmp/adsp-m2.coredump 2>/dev/null; chmod 644 /tmp/adsp-m2.coredump; ls -l /tmp/adsp-m2.coredump"
  $SCP "$DEV:/tmp/adsp-m2.coredump" ./adsp-m2.coredump
  sudo_ "echo 1 > $CD/data 2>/dev/null || true"   # free the devcd buffer
else
  echo "!! no devcoredump — crash-during-boot may not have produced one."
  echo "   check: dmesg for 'remoteproc2: ... crash' / 'fatal'"
  sudo_ "dmesg | tail -25"
fi

echo "== 6. RESTORE stock + heal ADSP =="
sudo_ "cp $FWDIR/adsp.mbn.stockbak $FWDIR/adsp.mbn; echo default > $RP/coredump 2>/dev/null || echo default > $DRP/coredump; \
       echo enabled > $DRP/recovery 2>/dev/null; echo stop > $RP/state 2>/dev/null; sleep 1; echo start > $RP/state 2>/dev/null; sleep 3; \
       echo -n 'restored state='; cat $RP/state; md5sum $FWDIR/adsp.mbn"

echo "== 7. extract the trace from the local dump =="
if [ -f ./adsp-m2.coredump ]; then
  python3 - ./adsp-m2.coredump <<'PY'
import sys, struct, re
d = open(sys.argv[1], "rb").read()
print("dump size: %d bytes" % len(d))
mk = b"\xef\xbe\xde\xc0"                 # 0xC0DEBEEF little-endian
labels = ["marker","regbase","FRM_STAT(+0x404)","STATUS2(+0x804)",
          "framer_mode(+0x78)","sat_hw_owner(+0x74)","ctx+0x60","ctx_ptr"]
hits = [m.start() for m in re.finditer(re.escape(mk), d)]
print("marker hits: %d" % len(hits))
for off in hits:
    if off + 32 > len(d): continue
    words = struct.unpack_from("<8I", d, off)
    print("  @0x%08x:" % off)
    for lab, w in zip(labels, words):
        print("      %-20s = 0x%08x" % (lab, w))
    # interpretation of FRM_STAT: UT running = 0x060D1901, pmOS gated = 0x0
    fs = words[2]
    print("    -> FRM_STAT %s" % ("!=0 (framer core clock RUNNING)" if fs else "== 0 (framer core clock GATED — confirms LPASS-clock wall from ADSP side)"))
if not hits:
    print("marker not found — scratch VA 0xf0ca0000 may be outside the dumped segments;")
    print("retry with a filesz-backed scratch, or list PT_LOADs to pick a captured VA.")
PY
else
  echo "no local dump to parse."
fi
echo "DONE."
