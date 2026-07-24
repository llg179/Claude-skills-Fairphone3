#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# pmos-diag-capture.sh — run on pmOS as root (echo PW | sudo -S bash THISFILE).
# Bind the ADSP DIAG (data) + DIAG_CNTL (gated to c200000), push the F3 mask,
# and capture the ADSP's debug log — first on the running ADSP (validate the
# mask mechanism), then across a remoteproc restart (framer bring-up).

# Config lives in fp3-env.sh; every value there has a documented default.
for _d in "$(dirname "$0")" "$(dirname "$0")/.." "$(dirname "$0")/../.." ; do
    [ -r "$_d/fp3-env.sh" ] && . "$_d/fp3-env.sh" && break
done

set -u
TS=$(date +%s)
RDR=$HOME/pmos-rpmsg-diag.py

# find the /dev/rpmsg node for a given ADSP (c200000) channel: DIAG or DIAG_CNTL
find_ch() {  # $1 = DIAG | DIAG_CNTL
    for c in /sys/class/rpmsg/rpmsg*; do
        [ -e "$c/device" ] || continue
        p=$(readlink -f "$c/device")
        case "$p" in *c200000.remoteproc*) : ;; *) continue;; esac
        b=$(basename "$p")   # remoteprocN:smd-edge.<CH>.-1.-1
        case "$b" in
            *".$1.-1.-1") echo "/dev/$(basename "$c")"; return;;
        esac
    done
}

modprobe rpmsg_char 2>/dev/null
sleep 0.3
echo "== bound rpmsg_chrdev devices =="
ls /sys/bus/rpmsg/drivers/rpmsg_chrdev/ | grep smd-edge

DATA=$(find_ch DIAG); CNTL=$(find_ch DIAG_CNTL)
echo "ADSP DIAG(data)=$DATA  DIAG_CNTL=$CNTL"
[ -n "$DATA" ] || { echo "no adsp DIAG data node"; exit 1; }

# ---- Phase A: validate mask on the RUNNING adsp ----
echo "== Phase A: F3 mask on running ADSP (6s) =="
A=$HOME/adsp_A_$TS.txt
if [ -n "$CNTL" ]; then
    python3 "$RDR" 6 "$A" "data:$DATA" "cntl:$CNTL" 2>&1
else
    echo "(no CNTL node — reading data only)"; python3 "$RDR" 6 "$A" "data:$DATA" 2>&1
fi
echo "  Phase A frames=$(grep -c '^\[' "$A" 2>/dev/null)"
grep 'STR:' "$A" 2>/dev/null | sort -u | head -20

# ---- Phase B: restart adsp, capture framer bring-up with mask ----
echo "== Phase B: remoteproc restart + framer capture =="
RP=""
for r in /sys/class/remoteproc/remoteproc*; do
    [ "$(cat $r/name 2>/dev/null)" = "adsp" ] && RP="$r"
done
echo "  adsp remoteproc=$RP state=$(cat $RP/state)"
dmesg -C 2>/dev/null
echo stop  > "$RP/state"; sleep 2
echo start > "$RP/state"
# wait for channels to reappear, then blast mask + read through framer window
DATA=""; CNTL=""
for i in $(seq 1 60); do
    DATA=$(find_ch DIAG); CNTL=$(find_ch DIAG_CNTL)
    [ -n "$DATA" ] && [ -n "$CNTL" ] && break
    sleep 0.1
done
echo "  post-restart DATA=$DATA CNTL=$CNTL (after $((i*100))ms)"
B=$HOME/adsp_B_$TS.txt
python3 "$RDR" 12 "$B" "data:$DATA" "cntl:$CNTL" 2>&1
echo "  Phase B frames=$(grep -c '^\[' "$B" 2>/dev/null)"
echo "--- framer/slim hits ---"
grep -iE "slim|framer|afe|wcd|laddr|logical|capab|reconf|master|intf|SB|fail|err|assert" "$B" 2>/dev/null | head -50
echo "--- unique STR ---"
grep 'STR:' "$B" 2>/dev/null | sort -u | head -40
echo "=== files: A=$A B=$B ==="
echo "=== dmesg this cycle ==="
dmesg | grep -iE "slim-ngd|logical addr|capability|remoteproc|adsp" | tail -14
