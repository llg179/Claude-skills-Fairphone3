#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# UT ADSP SSR-recovery differenciál-trace (plan: lovely-dazzling-rain).
# A BIZONYÍTOTTAN működő UT-n (slot_a, halium-10.0 4.9.218) az ADSP-t SSR-rel
# leállítjuk+újraindítjuk; a friss ADSP framer-recovery szekvenciája a pmOS
# cold-boot működő mása. Amit a recovery bekapcsol a QMI-n túl (clk-diff,
# smp2p/smem, HAL-ioctl), az a pmOS-en hiányzó trigger jelöltje.
#
# Futtatás HOSTRÓL, UT-ba bootolt telefonnal, ÉLŐ adb-vel (adb get-state==device).
# SOHA `sudo adb`! (elrontja a UT adbkulcsot) — sima adb + on-device sudo.
# usage: ut-ssr-trace.sh [outdir]
#   env: UT_PW=<sudo jelszó>  SSR_NODE=<trigger node override>  SSR_CMD=<restart|crash>

# Config lives in fp3-env.sh; every value there has a documented default.
for _d in "$(dirname "$0")" "$(dirname "$0")/.." "$(dirname "$0")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

set -uo pipefail
OUT=${1:-$FP3_PMOS/ut-ssr-$(date +%Y%m%d-%H%M)}
mkdir -p "$OUT"
echo "OUT=$OUT"

# ---------- [0] adb + sudo-jelszó autodetekt ----------
adb wait-for-device
PW=""
for p in "${UT_PW:-}" phablet "$FP3_PW"; do
  [ -n "$p" ] || continue
  if adb shell "echo $p | sudo -S whoami" 2>/dev/null | grep -q root; then PW=$p; break; fi
done
[ -n "$PW" ] || { echo "ERROR: sem 'phablet' sem '"$FP3_PW"' sudo-jelszó nem működik (UT_PW env-vel add meg)"; exit 1; }
S(){ adb shell "echo $PW | sudo -S sh -c '$1'" 2>/dev/null; }
S 'uname -r; date' | tee "$OUT/meta.txt"

# ---------- [0b] SSR-trigger felderítés (NEM találgatunk) ----------
echo "=== [0b] SSR-trigger node felderítés ==="
S 'ls -d /sys/kernel/debug/msm_subsys 2>/dev/null && ls /sys/kernel/debug/msm_subsys/;
   ls -d /sys/bus/msm_subsys/devices/*/ 2>/dev/null;
   for d in /sys/bus/msm_subsys/devices/*/; do echo -n "$d name="; cat $d/name 2>/dev/null | tr -d "\n"; echo -n " restart_level="; cat $d/restart_level 2>/dev/null; done;
   ls /sys/kernel/boot_adsp/ 2>/dev/null; ls -d /sys/kernel/debug/subsys* 2>/dev/null' | tee "$OUT/ssr-inventory.txt"

NODE="${SSR_NODE:-}"
if [ -z "$NODE" ] && S 'test -e /sys/kernel/debug/msm_subsys/adsp && echo YES' | grep -q YES; then
  NODE=/sys/kernel/debug/msm_subsys/adsp
fi
if [ -z "$NODE" ] && S 'test -e /sys/kernel/boot_adsp/boot && echo YES' | grep -q YES; then
  # adsp-loader (qdsp6v2): echo 0 = subsystem_put (graceful shutdown), echo 1 = subsystem_get (powerup)
  NODE=/sys/kernel/boot_adsp/boot
fi
if [ -z "$NODE" ]; then
  echo "ERROR: nincs ismert SSR-trigger node. Nézd meg $OUT/ssr-inventory.txt-t és add meg SSR_NODE env-ben."
  exit 3
fi
echo "SSR trigger: $NODE  (cmd: ${SSR_CMD:-restart})" | tee "$OUT/trigger.txt"

# restart_level=RELATED biztosítása az adsp subsys-en (SYSTEM = az EGÉSZ telefon újraindulna!)
ADSPDIR=$(S 'for d in /sys/bus/msm_subsys/devices/*/; do [ "$(cat $d/name 2>/dev/null)" = adsp ] && echo $d; done' | tr -d '\r' | head -1)
if [ -n "$ADSPDIR" ]; then
  LVL=$(S "cat ${ADSPDIR}restart_level" | tr -d '\r')
  echo "adsp restart_level=$LVL ($ADSPDIR)" | tee -a "$OUT/trigger.txt"
  case "$LVL" in
    *RELATED*) : ;;
    *) echo "  -> RELATED-re állítom (SSR, nem teljes reboot)"; S "echo RELATED > ${ADSPDIR}restart_level"; S "cat ${ADSPDIR}restart_level" | tee -a "$OUT/trigger.txt";;
  esac
fi

# ---------- [1] T0 baseline (framer UP) ----------
echo "=== [1] T0 baseline ==="
S 'cat /sys/kernel/debug/clk/clk_summary' > "$OUT/clk_T0.txt"; wc -l "$OUT/clk_T0.txt"
S 'ls /sys/bus/slimbus/devices/' | tr -d '\r' > "$OUT/slim-devices-T0.txt"; cat "$OUT/slim-devices-T0.txt"
S 'cat /sys/kernel/debug/regulator/regulator_summary 2>/dev/null' > "$OUT/regulator_T0.txt"
S 'ps -A 2>/dev/null || ps' > "$OUT/ps-T0.txt"
# ipc_logging DRAIN: a "log" olvasása kiüríti a puffert -> a T1-olvasat = tiszta recovery-delta
echo "--- ipc_logging drain (T0, elmentve pre-ként) ---"
S 'for d in /sys/kernel/debug/ipc_logging/*/; do n=$(basename $d); case "$n" in
     *slim*|*ngd*|*qmi*|*sps*|*bam*|*lpass*|*adsp*|*pdr*|*servreg*|*apr*|*smd*|*smem*|*smsm*|*smp2p*|*ipc_rtr*)
       echo "########## $n ##########"; timeout 5 cat "$d/log" 2>/dev/null ;; esac; done' > "$OUT/ipc-pre-drain.txt"
wc -l "$OUT/ipc-pre-drain.txt"
S 'echo "===== SSR-TRACE T0 marker =====" > /dev/kmsg'

# ---------- [1b] opcionális strace az audio-stacken (userspace-út felderítése) ----------
if S 'command -v strace' | grep -q strace; then
  APIDS=$(S 'ps -A 2>/dev/null | grep -iE "audio|pulse|hal" | grep -v grep' | awk '{print $2}' | tr '\n' ' ')
  echo "strace célpontok: $APIDS" | tee "$OUT/strace-pids.txt"
  for pid in $APIDS; do
    adb shell "echo $PW | sudo -S strace -f -tt -e trace=ioctl,openat,open,write -p $pid" > "$OUT/strace-$pid.txt" 2>&1 &
  done
  STRACE_BG=$(jobs -p)
else
  echo "(strace nincs a UT-n — kihagyva; ipc_logging+dmesg fedi a kernel-oldalt)"
  STRACE_BG=""
fi

# ---------- [2] SSR kiváltása ----------
if [ "$NODE" = "/sys/kernel/boot_adsp/boot" ]; then
  # kétfázisú graceful ciklus: 0 (shutdown) -> state OFFLINE -> 1 (powerup)
  echo "=== [2] ADSP graceful down->up: echo 0 > boot; várd OFFLINE; echo 1 > boot ==="
  S "echo 0 > $NODE"
  DOWN=0
  for i in $(seq 1 15); do
    st=$(S "cat ${ADSPDIR:-/sys/bus/msm_subsys/devices/subsys2/}state" | tr -d '\r')
    echo "  adsp state=$st"
    [ "$st" = OFFLINE ] && { DOWN=1; break; }
    sleep 2
  done
  if [ "$DOWN" != 1 ]; then
    echo "WARN: adsp nem ment OFFLINE-ba 30s alatt (kliens-refkount tarthatja) — visszakapcsolom (echo 1) és kilépek."
    S "echo 1 > $NODE"; exit 5
  fi
  S "echo 1 > $NODE"
else
  echo "=== [2] ADSP SSR trigger: ${SSR_CMD:-restart} > $NODE ==="
  S "echo ${SSR_CMD:-restart} > $NODE" || { echo "ERROR: trigger írása nem sikerült"; exit 4; }
fi

# ---------- [3] recovery megvárása (framer újra fel) ----------
echo "=== [3] recovery várakozás (max 120s) ==="
UP=0
for i in $(seq 1 60); do
  sleep 2
  DM=$(S 'dmesg | sed -n "/SSR-TRACE T0 marker/,\$p"')
  if echo "$DM" | grep -qiE "Rcvd master capability|adsp.*(is now up|powerup)"; then
    if echo "$DM" | grep -qi "Rcvd master capability"; then UP=1; break; fi
  fi
done
S 'dmesg | sed -n "/SSR-TRACE T0 marker/,$p"' > "$OUT/dmesg-recovery.txt"
wc -l "$OUT/dmesg-recovery.txt"
[ "$UP" = 1 ] && echo "FRAMER RECOVERY OK (Rcvd master capability)" || echo "WARN: framer-recovery jelzés nem jött 120s alatt — nézd $OUT/dmesg-recovery.txt"

# strace-ek leállítása
[ -n "$STRACE_BG" ] && kill $STRACE_BG 2>/dev/null

# ---------- [4] T1 capture ----------
echo "=== [4] T1 capture ==="
S 'cat /sys/kernel/debug/clk/clk_summary' > "$OUT/clk_T1.txt"
S 'ls /sys/bus/slimbus/devices/' | tr -d '\r' > "$OUT/slim-devices-T1.txt"; cat "$OUT/slim-devices-T1.txt"
S 'cat /sys/kernel/debug/regulator/regulator_summary 2>/dev/null' > "$OUT/regulator_T1.txt"
# ipc_logging: a T0-drain után ez a TISZTA recovery-szekvencia
S 'for d in /sys/kernel/debug/ipc_logging/*/; do n=$(basename $d); case "$n" in
     *slim*|*ngd*|*qmi*|*sps*|*bam*|*lpass*|*adsp*|*pdr*|*servreg*|*apr*|*smd*|*smem*|*smsm*|*smp2p*|*ipc_rtr*)
       echo "########## $n ##########"; timeout 5 cat "$d/log" 2>/dev/null ;; esac; done' > "$OUT/ipc-recovery.txt"
wc -l "$OUT/ipc-recovery.txt"

# ---------- [5] golden NGD regdump (0xc141000 — guardrail szerint BIZTONSÁGOS) ----------
echo "=== [5] golden NGD regdump (framer-up állapot) ==="
adb push /dev/stdin /data/local/tmp/ngddump.py >/dev/null 2>&1 <<'PY' || true
import mmap,os,struct
fd=os.open("/dev/mem",os.O_RDONLY|os.O_SYNC)
base=0xc141000
m=mmap.mmap(fd,0x1000,mmap.MAP_SHARED,mmap.PROT_READ,offset=base)
for name,o in [("CFG",0x0),("STATUS",0x4),("RX_MSGQ_CFG",0x10),("INT_EN",0x10),("INT_STAT",0x14),("INT_CLR",0x18)]:
    v=struct.unpack("<I",m[o:o+4])[0]; print("NGD1 +0x%04x %-12s = 0x%08x"%(o,name,v))
m.close(); os.close(fd)
PY
S 'python3 /data/local/tmp/ngddump.py 2>&1 || python /data/local/tmp/ngddump.py 2>&1' | tee "$OUT/ngd-golden-regs.txt"

# ---------- [6] diffek ----------
echo "=== [6] clk_summary T0<->T1 diff (mi kapcsolt a recovery alatt) ==="
diff -u "$OUT/clk_T0.txt" "$OUT/clk_T1.txt" > "$OUT/clk-diff.txt" || true
wc -l "$OUT/clk-diff.txt"; grep -E "^[+-]" "$OUT/clk-diff.txt" | grep -viE "^[+-]{3}" | head -60
echo "=== slim-devices T0<->T1 ==="
diff -u "$OUT/slim-devices-T0.txt" "$OUT/slim-devices-T1.txt" || echo "(azonos — codec újra-enumerálva)"
echo "=== DONE -> $OUT ==="
