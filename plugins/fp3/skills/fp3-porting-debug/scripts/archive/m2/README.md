# M2 — ADSP firmware trace injection pipeline (FP3 SLIMbus framer-clock debug)

Recovered from the (persisted) session scratchpad on 2026-07-04. This directory is
the **durable** home of the ADSP-firmware instrumentation pipeline used to read
values from *inside* the running ADSP under mainline pmOS PAS-boot — the only place
the SLIMbus-core-clock failure is visible (AP-side is exhausted, see journal).

## Goal (the one open question)

FRM_CFG@0xc140400 is **byte-identical** UT↔pmOS (`0x000D0C83`, framer configured
ACTIVE). Only FRM_STAT@0xc140404 differs: UT `0x060D1901` (framer running) vs pmOS
`0x0` (framer **not clocked**). The 24.576 MHz SLIMbus root clock never starts on
mainline. That clock is **ADSP-owned** (LPASS_CC, no AP handle: no lpasscc-msm8953,
no slim-clk in gcc-8953, no LPASS-GDSC). So the AP cannot see *why* the ADSP's
clock-enable fails. **Only a trace from inside the ADSP firmware answers it.**

Downstream framer-start (golden-framer-regs.txt): `clk_prepare_enable(rclk 24.576MHz)
+ writel(1, FRM_WAKEUP@0x41c) + FRM_CFG=0x000D0C83`. On pmOS FRM_CFG *is* written →
the framer-enable code runs → so the missing step is `clk_prepare_enable(rclk)`
(the ADSP clock_manager rclk enable) either not called or returning an error.
**Next trace target: the clock_manager SLIMbus-core-clock (rclk) enable call + its rc.**

## Pipeline (proven working)

1. `build_m2.sh` — assemble `m2trace.s` (llvm-mc hexagonv60) → splice into a fresh
   copy of stock `adsp.mbn` at VA `0xf04c36e0` → re-sign with `qtestsign/qtestsign.py
   adsp -v3` (FP3 secure-boot is OFF → test-key sig loads). Output `adsp-m2-signed.mbn`.
2. `deploy_m2b.sh` — **SAFE crashing-capture**: coredump=enabled, cp patched fw, SSR
   (stop/start remoteproc2), poll devcoredump, **restore stock FIRST** (breaks the
   crash-reload loop), pull `/tmp/adsp-m2.coredump`, heal (SSR clean). Reversible.

Stock provenance: `adsp.mbn` here = device stock, **md5 3ed6924d** (`3ed6924da0017c...`).
Signed size 10999580; unsigned 9962764.

## Injection site facts (from disasm, f04c36e0.bin / slim_region.disasm)

`0xf04c36e0` = SLIMbus **framer-mode-decision+init** fn. At entry **r0 = ctx** (SLIMbus
HW context). Proven to execute under mainline PAS (the earlier 4-patch test: election
runs; only the downstream HW-enable tail fails). Prologue packets:

```
f04c36e0: { call 0xffb57094 ; allocframe(#16) }   <- 8 bytes, PC-RELATIVE call
f04c36e8: { r16 = r0 }                             <- r16 = ctx (r0 preserved across call)
f04c36ec: { r2 = memw(r16+#3632/0xe30); if (!cmp.eq(r2.new,#0)) jump ... }
...
```
ctx offsets: `+0x5c`=regbase ptr, `+0x74`=sat_hw_owner, `+0x78`=framer-mode flag,
`+0x60`=secondary. regbase offsets: `+0x404`=FRM_STAT, `+0x804`=STATUS2.

## Crashing vs NON-crashing (☠️ guardrail)

`m2trace.s` (current) is the **CRASHING** variant: reads regs → stores to in-image bss
`0xf0ca0000` (= carveout PA 0x8e1a0000, AP-unreadable → needs coredump) → NULL-store
fault → devcoredump. It **worked** (answer came from AP-dmesg without the dump), but:

**☠️ RULE: never leave a crashing ADSP-fw under recovery=enabled — crash-loop →
rootfs corruption → physical recovery.** `deploy_m2b.sh` mitigates by restoring stock
the instant the devcd appears, but the committed forward path is **non-crashing SMEM
exfil** (read via `/dev/mem` at SMEM PA 0x86300000, no carveout, no crash).

## Non-crashing detour design (TO BUILD)

Two RE prerequisites, both host-side + then one careful on-device shot:

1. **Clean detour (return instead of fault). ★ SOLVED (constants pinned):**
   Overwrite the 8-byte packet1 at f04c36e0 with `{ jump ##CAVE }` (immext+jump = 8
   bytes, exact fit). In the code cave:
   - trace: r0 is still ctx (jump is first insn); read target regs/clock state into
     r1..r9 (do NOT touch r0 or the stack); store to SMEM (see #2).
   - execute the **displaced** packet1 — `call 0xffb57094` is PC-relative; re-emit as
     `{ call ##0xf001a774 ; allocframe(#16) }` (absolute target = f04c36e0 +
     signed(0xffb57094) = **0xf001a774**, confirmed in a file-backed PT_LOAD).
   - `{ jump ##0xf04c36e8 }` back to packet2 (`r16 = r0`).
   - **CAVE = `0xf064e098`** (3952 zero bytes) — same R+X segment as the site
     (VA 0xf015f000, flags 0x8000005), so the jump stays in-range + executable.
     (38 caves ≥96B found; 0xf064e098 and 0xf065725c are the roomiest.)

2. **SMEM write VA (NOT yet pinned).** The crashing variant wrote in-image; a
   non-crashing read needs a location the AP reads *without* coredump = a SMEM item at
   PA 0x86300000. Pin the ADSP-side VA of a SMEM item (smem_alloc return-path / a
   global holding the version-item ptr; journal folyt.3 write-primitive hint
   `memw(##0xf0913630+id*4)` — unverified). `smem_ver_scan.py` locates the version
   string + its TOC item at the AP side; find the matching ADSP-VA global in the disasm,
   write the trace value into that item's padding, read back with `smem_peek.py`.

## Device-return checklist (pmOS slot_b)

Device is currently OFFLINE (adb/fastboot/ssh all empty). When pmOS is back:
- `sshpass -p $FP3_PW ssh fp3@$FP3_DEV_IP` reachable; `remoteproc2/state`=running;
  `md5sum .../adsp.mbn` == stock 3ed6924d (else restore from `.stockbak`).
- **Zero-risk first:** read the SLIMbus-core-clock **CBCR** (branch-control reg, in the
  always-clocked LPASS_CC config domain) via `smem_peek.py`-style `/dev/mem` mmap to
  check CLK_OFF/ENABLE directly — pin the msm8953 LPASS_CC rclk CBCR address first.
- **Then Option 2:** build non-crashing trampoline (prereqs #1+#2 above) → `build_m2.sh`
  → deploy via a **non-crashing** deploy (SSR-reload, no coredump) → `smem_peek.py`.
- Recovery from boot-loop (proven): power-cycle → `fastboot set_active a`→UT →
  `losetup -fP /dev/mmcblk0p31`→loop1p2 → `e2fsck -fy` + debugfs 1.47 restore →
  `set_active b`→pmOS.

## Files

- `m2trace.s` — trampoline asm (CRASHING variant; edit for new trace target / non-crash).
- `build_m2.sh` / `deploy_m2.sh` / `deploy_m2b.sh` — build + deploy (b = safe capture).
- `qtestsign/` — the re-signer (`qtestsign.py adsp <in> -v3 -o <out>`).
- `adsp.mbn` — stock unsigned ELF32 (md5 3ed6924d).
- `smem_peek.py` / `smem_ver_scan.py` / `smem_dump.py` / `smemprobe.py` — SMEM /dev/mem exfil.
- `make_elf.py` / `elfmap.py` — ELF phdr VA↔offset tooling.
- `frm_read.py` / `frm_wake.py` — AP-side /dev/mem framer-reg read / wake.
- `golden-framer-regs.txt` — UT(up)↔pmOS(dead) register truth table.
- `slim_region.disasm` — disasm of the SLIMbus code region (f04b–f04e).
- `f04c36e0.bin` — 80 bytes of the injection-site prologue.
