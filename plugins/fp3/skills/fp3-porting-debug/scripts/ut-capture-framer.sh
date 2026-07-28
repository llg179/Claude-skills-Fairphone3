#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Enhanced WORKING-framer capture on Ubuntu Touch (downstream 4.9 kernel) for the
# on-device A/B vs mainline pmOS. The KEY additions over ut-trace.sh:
#   1. /d/ipc_logging/  — the slim-msm driver logs its QMI power_req + capability +
#      "Rcvd master capability" + SPS/BAM pipe-connect to a Qualcomm IPC log buffer,
#      NOT dmesg. This is the exact working framer-bring-up sequence we need to diff.
#   2. Raw NGD + BAM register dump (busybox has no devmem applet → python3 mmap).
#   3. msm_subsys / PIL state + slim debugfs.
# Run from HOST with the phone booted into UT and adb up. usage: ut-capture-framer.sh [outdir]

# Config lives in fp3-env.sh; every value there has a documented default.
# Resolve symlinks first: these scripts are commonly installed as symlinks in
# /usr/local/bin, where a bare $0 would look for fp3-env.sh next to the symlink.
_self="$(readlink -f "$0")"
for _d in "$(dirname "$_self")" "$(dirname "$_self")/.." "$(dirname "$_self")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

set -uo pipefail
OUT=${1:-$FP3_PMOS/pmos-backup-20260629/ut-framer-$(date +%H%M)}
mkdir -p "$OUT"
PW="${UT_PW:-phablet}"
S(){ adb shell "echo $PW | sudo -S sh -c '$1'" 2>/dev/null; }

echo "=== adb up? ==="; adb wait-for-device; S 'whoami; uname -r' | tee "$OUT/meta.txt"

echo "=== [1] ALL IPC log buffers (find slim/ngd/qmi ones) ==="
S 'ls /sys/kernel/debug/ipc_logging/ 2>/dev/null' | tee "$OUT/ipc_logging-list.txt"
# dump every ipc log whose name hints slim/ngd/qmi/sps/bam; also dump all as fallback
S 'for d in /sys/kernel/debug/ipc_logging/*/; do n=$(basename $d); case "$n" in
     *slim*|*ngd*|*qmi*|*sps*|*bam*|*lpass*|*adsp*|*pdr*|*servreg*)
       echo "########## $n ##########"; cat "$d/log" 2>/dev/null ;; esac; done' > "$OUT/ipc-slim.txt"
wc -l "$OUT/ipc-slim.txt"; echo "--- preview ---"; head -60 "$OUT/ipc-slim.txt"

# [1b] THE DECISIVE diff target (added 2026-06-30): the ADSP control plane that
# precedes the framer broadcasting capability. The framer-init trigger (req (4))
# is NOT an AP clock/power vote (proven: bb_clk1 force-vote changed nothing) -> it
# must be a message the downstream sends to the ADSP that mainline does not. These
# channels carry exactly that: apr (q6afe/adm/asm/core audio cmds), the q6 ipc
# router, SMD, and SMEM/SMSM/SMP2P (board-config + handshakes). Capture the WHOLE
# of each, time-correlate against the slim "Rcvd master capability" line.
echo "=== [1b] APR / q6-router / SMD / SMEM / SMSM / SMP2P + c104000 BAM pipes (ADSP control plane) ==="
S 'for n in apr ipc_rtr_q6_ipcrtr ipc_rtr_smd_ipcrtr smd smd_pkt smem smsm smp2p \
     sps_bam_0x000000000c104000_0 sps_bam_0x000000000c104000_1 sps_bam_0x000000000c104000_2 \
     sps_bam_0x000000000c104000_3 sps_bam_0x000000000c104000_4; do
       d=/sys/kernel/debug/ipc_logging/$n;
       [ -e "$d/log" ] && { echo "########## $n ##########"; cat "$d/log" 2>/dev/null; }; done' > "$OUT/ipc-adsp-ctrl.txt"
wc -l "$OUT/ipc-adsp-ctrl.txt"; echo "--- apr preview (what the ADSP is told) ---"; grep -iA2 -m20 'apr\|afe\|adm\|q6' "$OUT/ipc-adsp-ctrl.txt" | head -40

echo "=== [2] NGD (0xc140000) + BAM (0xc104000) register dump via python mmap ==="
adb push /dev/stdin /data/local/tmp/regdump.py >/dev/null 2>&1 <<'PY' || true
import mmap,os,struct,sys
def dump(base,off_list,label):
    fd=os.open("/dev/mem",os.O_RDONLY|os.O_SYNC)
    pg=0x1000; pa=base & ~(pg-1); delta=base-pa
    m=mmap.mmap(fd,pg,mmap.MAP_SHARED,mmap.PROT_READ,offset=pa)
    print("==",label,hex(base),"==")
    for o in off_list:
        try:
            v=struct.unpack("<I",m[delta+o:delta+o+4])[0]; print("  +0x%04x = 0x%08x"%(o,v))
        except Exception as e: print("  +0x%04x err %s"%(o,e))
    m.close(); os.close(fd)
# NGD core (base) + NGD1 block (base+0x1000): CFG/STATUS/INT_EN/INT_STAT/RX_MSGQ_CFG
dump(0xc140000,[0x0,0x4,0x800,0x804,0x810,0x814,0x818,0x820,0x1000,0x1004,0x1010,0x1014,0x1018,0x1020,0x1024],"NGD")
PY
S 'python3 /data/local/tmp/regdump.py 2>&1 || python /data/local/tmp/regdump.py 2>&1' | tee "$OUT/ngd-regs.txt"

echo "=== [3] subsys / PIL state + slim debugfs + clk + slimbus devices ==="
S 'for s in /sys/bus/msm_subsys/devices/*/; do echo -n "$s "; cat $s/name 2>/dev/null|tr -d "\n"; echo -n " state="; cat $s/state 2>/dev/null; done' | tee "$OUT/subsys.txt"
S 'cat /sys/kernel/debug/clk/clk_summary 2>/dev/null' > "$OUT/clk_summary.txt"; wc -l "$OUT/clk_summary.txt"
S 'grep -iE "slim|lpass|bb_clk|cxo|audio|mclk|q6" /sys/kernel/debug/clk/clk_summary 2>/dev/null' | tee "$OUT/clk-slim.txt"
S 'ls -l /sys/bus/slimbus/devices/ 2>/dev/null' | tee "$OUT/slimbus-devices.txt"
S 'dmesg | grep -iE "slim|ngd|laddr|capability|framer|tasha|wcd|sps:BAM|Power/Clock|subsys-pil|adsp"' > "$OUT/dmesg-slim.txt"; wc -l "$OUT/dmesg-slim.txt"
echo "=== DONE -> $OUT ==="
