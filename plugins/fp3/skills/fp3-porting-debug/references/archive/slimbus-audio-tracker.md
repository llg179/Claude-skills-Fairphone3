# FP3 SLIMbus framer — RUNTIME-TRIGGER investigation (LIVE tracker)

> **★★★★★ MEGOLDVA (folyt.196, 2026-07-23) — EZ A TRACKER TÖRTÉNELMI.** A framer-fal gyökere
> **NEM** a „fizikai óra-realizáció / ADSP-belső PLL" (ahogy lentebb áll), hanem a **QDSP6SS `0x0c20002c`
> bit3**, amit a mainline PAS set-ben hagy (downstream PIL törli). Törölve a framer felframel, a WCD9335
> enumerál. Lásd `slimbus-audio-context.md` legelső ★★★★★ szakaszát. A lenti runtime-trigger terv és a
> „PHYSICAL clock realization" konklúzió SUPERSEDED — az egyes mérések igazak, a keret téves volt.
> **↑ FRISSÍTÉS (folyt.208, 2026-07-24): a TELJES audio megoldva — HALLHATÓ tiszta zene a fülhallgatón.**
> A framer után a második (utolsó) darab: a codec-MCLK `func1` pinmux sose alkalmazódott
> (`gpio-gate-clock` `pinctrl-names="active","sleep"` → kell `"default"`). Lásd `slimbus-audio-context.md`
> legfelső ★★★★★★ bannerét. Ez a tracker teljesen történelmi.

**Purpose:** power-outage-resilient live plan+progress. Updated continuously. On resume: read this FIRST,
then `FP3-audio-context-all-in-one-summary.md` + `FP3-tierA-results-2026-Jul-10.md` (HWL/snapVA sections) + the two fp3 skills.

Last updated: 2026-07-11 (session cont.); SUPERSEDED 2026-07-23 (folyt.196, bit3 root cause)

---

## THE GOAL (user's idea, 2026-07-11)
On UT the slimbus framer clock starts at BOOT (hard to debug). Make UT boot **without** that init (audio dead,
like pmOS), then **trigger the clock start from a running process**. Benefits: (1) SMEM is up at runtime → the
firmware leaf-cave captures cleanly (boot-time it can't — see below); (2) only the slimbus clock starts at that
moment = isolated signal; (3) UT-clock-dead == pmOS-state → direct diff of the TRIGGER path finds the difference.

## WHY (context, established)
- adsp.mbn byte-identical UT(works)↔pmOS(dead). Config-group SW inputs identical (snapT3). Diff is in the PHYSICAL
  clock realization (HalHwIo register-poke / LPAPLL1 lock), which the fw delegates and doesn't examine.
- HalHwIo leaf-trace (HWL) at splice f019abb0: **empty on BOTH sides** — the leaf runs in EARLY boot before the
  ADSP SMEM pointer `*(0xf090fcd4)` is set → guarded cave skips. NOT a differential (UT positive control proved it).
- **SMEM base constant captured: `*(0xf090fcd4)=0xe1302470`** → PA 0x86300000 ↔ ADSP-VA 0xe1300000; stash VA 0xe1302ab0.
  A fixed-VA early cave (`r14=##0xe1302ab0`) would write in early boot, but boot fires many clocks (isolation problem).
  → runtime-trigger is the better route.

## HARD SAFETY (never violate)
- ☠️ NEVER host-side USB restart (authorized/USBDEVFS/unbind/remove/ip-link-cycle) — disconnects the USB-mounted /mnt disk.
  NCM flap self-recovers; use per-MAC `ip neigh flush dev fp3 && ip addr replace $FP3_HOST_IP/16 dev fp3` + spaced ssh.
- ☠️ NEVER `sudo adb`. NEVER cave-issued MMIO read (posted-write≠safe-read → ADSP hang). SMEM stash ≤ ~0x50B.
- UT reboots flaky: Halium container race → File-Stor/"Charging Only", ~~needs user login+replug (device-side)~~
  — handled automatically since 2026-07-28 ([Unattended access](../../../../../README.md#unattended-access-no-on-device-login-no-usb-replug)).
- Flash gates self-decidable (overnight autonomy) w/ brick-safety; kernel commits LOCAL never push; daily-driver = separate FP3.

## DEVICE STATE (keep current!)
- Both slots CLEAN stock on disk: UT p1 adsp.mdt `bab175ed`; pmOS adsp.mbn `3ed6924d`.
- Currently (2026-07-11 after A): **slot_a/UT, STOCK restored, framer ALIVE** (tasha snd-card + pgd/ifd/sb-1 enumerated).
  pmOS slot_b disk=stock. Both slots clean.
- Backups: `ut-p1-stock.img` (full UT p1, md5 e5de6864), pmOS `adsp.mbn.stockbak` on device.
- v4 UT artefacts kept: `ut-p1-hwl4.img`, `ut-hwl4-split/`, `scripts/deploy_snapHWL4_ut.sh`, `hwl4-ut-test.log`.

## PLAN (REVISED after S1 — the runtime trigger already exists via NGD runtime-PM)
The framer-clock trigger = NGD runtime-PM resume → POWER_REQ(ACTIVE). Suspend → POWER_REQ(INACTIVE) drops it.
Exposed via sysfs `power/control`. So NO boot modification needed — just cycle runtime-PM at RUNTIME (SMEM ready).
- [x] **S1. Trace the trigger** — DONE. = SLIMBUS_QMI_POWER_REQ (0x21); NGD runtime-PM suspend(INACTIVE)/resume(ACTIVE).
- [ ] **S2. Verify on-device runtime-PM handle** for `c140000.slim-ngd` (sysfs `power/control`, `power/runtime_status`);
      confirm suspend→resume re-issues POWER_REQ (dmesg "DBG power_up" breadcrumb already in the code). Both slots.
- [ ] **S3. Runtime clock-start capture (DEAD side, pmOS — autonomous):** deploy v3 HWL cave (already built/signed,
      `adsp-snapHWL3-signed.mbn`), cold boot, then at RUNTIME: force ngd suspend (`echo auto`+idle or unbind) then
      resume (`echo on > power/control`) → framer-clock-enable leaf runs with SMEM ready → read v3 cave stash.
      Expect: leaf now WRITES (unlike boot-time). Capture base/offset/value/pollmask on the failing side.
- [ ] **S4. Same on UT (golden):** runtime suspend→resume, read cave. Diff UT(clock starts) vs pmOS(fails).
      Also AP-side: ftrace the resume path + NGD_STATUS/regdump during the runtime trigger, both sides.
- [ ] **S5. Localize:** the leaf's differential (or the ADSP's divergent handling of POWER_REQ(ACTIVE) at runtime)
      = where the slimbus-clock-start differs UT vs pmOS.
NOTE: on resume, if the framer is already up the ADSP may no-op → must force SUSPEND first (POWER_REQ INACTIVE,
ADSP drops clock) THEN resume, to get a clean clock-ENABLE event through the leaf.

## KEY SOURCE FINDINGS (mainline linux-fp3, branch f0-clean-baseline, drivers/slimbus/qcom-ngd-ctrl.c)
- **The framer-clock TRIGGER = `SLIMBUS_QMI_POWER_REQ_V01` (msg-id 0x0021)**, AP→ADSP QMI on SvcId 0x301.
  Sent in `qcom_slim_ngd_power_up()` (~line 1219) via `qcom_slim_qmi_power_request(ctrl, true)` (~1236), called
  from the runtime-PM/enable path (`qcom_slim_ngd_enable`/`_runtime_resume`, ~1386-1425). After POWER_REQ it reads
  `NGD_STATUS`; if `NGD_LADDR` set → already framed (setup+return), else proceeds to capability exchange.
- ☠️ **DEAD END (already tried 2026-06-30, do NOT redo):** `qcom_slim_qmi_check_framer_request` (CHECK_FRAMER 0x22)
  is DEFINED but `__maybe_unused`/never called. In-code NOTE: downstream UT 4.9.218 (ut-framer-1003/ipc-slim.txt)
  sends ONLY 0x20+0x21 on 301 (never 0x22); adding the poll returned rc=0 but bus stayed silent → speculative, removed.
  → the mainline 301 QMI sequence now EXACTLY matches downstream, yet framer silent ⇒ diff is NOT the AP QMI seq.
- **Consequence:** the same POWER_REQ starts the framer on UT, not on pmOS ⇒ diff is the ADSP's *response* to POWER_REQ
  (physical realization), consistent with all prior findings. The runtime-trigger = re-issue POWER_REQ at runtime and
  instrument the ADSP's handling (leaf-cave now captures since SMEM ready). Checking if POWER_REQ supports power-DOWN
  (→ clean tear-down + re-trigger without an ADSP SSR).

## ON-DEVICE (pmOS) NGD state — 2026-07-11
- Device `c140000.slim-ngd` (platform `qcom,slim-ngd.1`), driver `qcom,slim-ngd-ctrl`. `power/control=auto`,
  **`power/runtime_status=unsupported`** → sysfs power/control WON'T drive resume. Use **unbind/rebind** instead:
  `echo c140000.slim-ngd > /sys/bus/platform/drivers/qcom,slim-ngd-ctrl/{unbind,bind}` (poll2.py-style).
- Boot dmesg (the failure, verbatim): `power_up enter state=2` → `QMI power request OK` → `ver=0x105 ngd_status=0x40c`
  (0x40c = no NGD_LADDR → framer NOT framed) → `NGD setup done, waiting for capability` → `capability exchange
  timed-out STATUS=0x40c CFG=0x0 INT_STAT=0x0`. So POWER_REQ is ACKed but the ADSP never physically frames.

## ⇒ PIVOTAL GO/NO-GO TEST (running on pmOS, autonomous)
Deploy v3 HWL cave (`adsp-snapHWL3-signed.mbn`), cold boot, then RUNTIME unbind/rebind the NGD → does the ADSP
re-run its clock-enable leaf (f019aaf8) on the re-issued POWER_REQ? Read v3 cave stash:
- **magic PRESENT** ⇒ the clock-enable runs at RUNTIME (SMEM ready) ⇒ user's runtime-trigger WORKS; capture
  base/offset/value/pollmask on the failing side, then repeat on UT for the differential.
- **magic ABSENT** ⇒ POWER_REQ does NOT re-run the physical clock enable (it's ADSP-boot-only) ⇒ need ADSP SSR
  or a different trigger; the clock realization is purely at ADSP boot.

## PROGRESS LOG (append; newest last)
- 2026-07-11: tracker created. SMEM constant 0xe1302470 in hand. Device slot_b/pmOS, both slots clean.
- 2026-07-11: S1 — traced trigger to SLIMBUS_QMI_POWER_REQ (0x21). check-framer(0x22) confirmed already-refuted dead end.
- 2026-07-11: S2 — NGD runtime-PM = unsupported; use unbind/rebind. Boot dmesg = POWER_REQ OK but ngd_status=0x40c
  (framer not framed), capability timeout. Set up S3 go/no-go: v3 cave + runtime unbind/rebind → does leaf re-run?
- 2026-07-11: ★ RUNTIME TRIGGER CONFIRMED (AP level): unbind/rebind of c140000.slim-ngd re-runs the FULL power_up→
  POWER_REQ→capability sequence at RUNTIME (dmesg @1462s uptime vs 18s boot), same failure (ngd_status=0x40c). So the
  framer bring-up is a repeatable runtime event. Trigger cmd (both slots):
  `echo c140000.slim-ngd > /sys/bus/platform/drivers/qcom,slim-ngd-ctrl/unbind` then `.../bind`.
  NEXT: deploy v3 cave + do runtime rebind → read cave (does ADSP re-run clock-enable leaf at runtime?).
- 2026-07-11: ★ GO/NO-GO RESULT = **NO-GO for POWER_REQ**. v3 cave on pmOS: ABSENT at boot (SMEM null, expected) AND
  ABSENT after runtime unbind/rebind. The AP re-runs power_up/POWER_REQ at runtime, but the ADSP does NOT re-run its
  HalHwIo clock-enable leaf (f019aaf8) on POWER_REQ → the physical clock realization is ADSP-BOOT-ONLY, not
  runtime-re-triggerable via POWER_REQ. (unbind/rebind only redoes the AP capability exchange, same 0x40c failure.)
- ⇒ **PIVOT: fixed-VA cave (v4)** — capture the BOOT-time clock-enable directly, using hardcoded stash VA 0xe1302ab0
  (= SMEM base 0xe1302470 + 0x640), bypassing the null *(0xf090fcd4). This solves the original SMEM-timing wall
  without needing a runtime trigger. Isolation (many clocks at boot) handled by v3's pollmask!=0 filter + UT↔pmOS diff.
  Build v4 = v3 with `r14=##0xe1302ab0` replacing the pointer-deref+null-guard. Deploy both slots at boot, diff.
- 2026-07-11: ★ v4 FIXED-VA cave ALSO ABSENT on pmOS boot. Since snapVA PROVED 0xe1302ab0 is writable+readable,
  absent = splice f019abb0 NEVER EXECUTED at boot → NOT a SMEM-timing issue (kills that theory). ⇒ the CGC-enable
  leaf f019aaf8 (via return abb0) is NOT on the pmOS boot path; config-group completes rc=0 without it. Caveats:
  (1) function has a 2nd exit path abb8 (`r1=0; jump abc0`) my splice misses; (2) f019aaf8 may not be the framer
  clock enabler at all (static-RE candidate, unconfirmed). remoteproc=running (fixed-VA write didn't fault ADSP).
  ⇒ NEED: (a) confirm the ACTUAL framer-clock-enable function via more static RE, OR (b) v4 on UT (positive control):
  if abb0 IS reached on UT(working) but not pmOS → the differential; if absent on UT too → wrong target function.
  v4 UT test needs a UT reboot (degrade-risk → user-present preferable). Device: pmOS slot_b, restoring stock.

- 2026-07-11: ★★★ **A EXECUTED — v4 POSITIVE CONTROL ON UT = CONFIRMS f019aaf8/abb0 REFUTED.** Built ut-p1-hwl4.img
  (deterministic split of adsp-snapHWL4-signed.mbn: only adsp.mdt/b01/b04 differ from v3; rule bNN=signed[p_off:+p_fsz],
  compact mdt=seg00+seg01, verified against v3 split). Deployed via block-dev dd on UT slot_a, cold boot. RESULT:
  **v4 fw loaded (mdt md5 e7ae4f84 on partition, b04 8ddcaf78), framer ALIVE** (tasha-slim-pgd/ifd + sb-1 enumerated,
  snd-card present) — the working UT booted the patched ADSP and framed the bus — **yet HWL cave magic ABSENT.**
  ⇒ f019abb0 does NOT execute at boot on the WORKING side either, despite framer coming up ⇒ the HalHwIo CGC-enable
  leaf f019aaf8/abb0 is NOT on the framer bring-up path on either OS. Refutation now CONFIRMED (was PLAUSIBLE) via a
  clean positive control (framer verified alive on the patched fw). The HWL leaf-trace line is CLOSED.
- ☠️ **CORRECTION: `ctx+0xe14 = 0x3 vs 0x13` is NOT a live lead** — folyt.93 (tierA-results 498-502) already refuted it
  as an invocation artifact (per-invocation clock-handle, last-write-wins; the config-group splice fires for many clocks,
  so 0x3/0x13 just reflects which one the stash caught last). ALL reliably-captured config-group software fields are
  IDENTICAL UT↔pmOS (gate 0xf0913658=0 both, rc=0 both, sat_hw_owner=1). Nothing to verify there.
- ⇒ **STATE after A: every firmware-internal software-input lead (config-group inputs + HWL leaf) AND every AP-side lead
  (RPM-vote/SCM/clock/power/SMMU) is now EXHAUSTED.** Both the config-group inputs and the HWL leaf are identical/absent
  on the working and dead sides, yet UT frames and pmOS doesn't. The one never-measured layer that remains: the
  **pre-ADSP LPASS hardware state that PIL/TZ sets before the ADSP runs and PAS skips** (context §7b logical constraint;
  tierA "F1 UT-side" SCM/clock-ordering). That is an AP-side SCM/register trace of the UT PIL boot vs pmOS PAS boot,
  NOT another firmware cave. Device: UT slot_a on v4-hwl fw (framer alive, benign); restore stock next.

- 2026-07-11: ★★★ **F1 UT-SIDE = HARD CLOSURE of the AP/PIL side.** No safe UT ADSP-SSR trigger (msm_subsys debugfs
  absent; wouldn't gamble a crash-reboot on the oracle) → used steady-state + live DT. (1) UT `enabled_clocks` (framer
  alive): ZERO lpass/slim/audio/ADSP-q6 clock enabled (only bb_clk1 red herring + modem-q6). (2) PIL live DT proxy list
  (hard ground truth): proxy-clocks = {xo, scm_core/iface/bus/core_src} = crypto-auth clocks; proxy-reg = {vdd_cx}; NO
  LPASS/framer/audio clock at all. ⇒ PIL does ONLY xo+cx+crypto-auth for the ADSP; the framer clock is 100% ADSP-internal;
  mainline PAS gives the equivalent (cx@max, xo, auth succeeds). **The framer difference is NOT any AP (PIL or PAS) action.**
  Residual: TZ-secure auth_and_reset (same SCM/fw — AP-opaque; tzdbg = only CPU power-collapse stats, unproductive) OR
  ADSP-internal PLL-lock depending on some LPASS HW state. Recorded: FP3-tierA-results F1-UT block, ut-enabled-clocks.txt.
- ⇒ **CONSOLIDATED FRONTIER: every AP-visible layer (PIL proxy set, PAS resources, steady-state clocks/regulators,
  RPM votes, SCM sequence, QMI) is now exhausted with hard evidence; every firmware software input is identical.** The
  divergence is below AP visibility: TZ-secure or ADSP-internal PLL realization. Candidate next probes (all lower-confidence):
  (i) tzdbg log diff UT↔pmOS (long shot, log read hangs); (ii) T1 fw execution-identity (deep, never hard-measured);
  (iii) a firmware cave on the ADSP-internal PLL-program/HwdMmpm leaf (needs the runtime-trigger isolation, still unsolved).

## OPEN DECISION (for when user returns / power stable) — A DONE + F1-UT DONE (see log above)
Two viable continuations, both need care:
- **A. v4 on UT (positive control)** — decisive but needs a UT reboot (~~may degrade → user login+replug~~;
  a UT reboot is hands-off now, [Unattended access](../../../../../README.md#unattended-access-no-on-device-login-no-usb-replug)). If abb0
  reached on UT only → pmOS skips the CGC enable = root-cause-adjacent.
- **B. More static RE** — find the TRUE framer/SLIMbus core-clock enable site in adsp.mbn (f019aaf8 unconfirmed);
  check the abb8 exit path + trace which fn the config-group actually calls for realization. Offline, no device risk.
- **C. Runtime AP-side instrumentation** (the one clearly-useful thing the runtime trigger unlocked): ftrace the
  unbind/rebind capability-exchange on UT vs pmOS at RUNTIME (no reboots) — diff NGD reg writes / QMI / BAM.
Recommend B first (offline, safe), then A (with user present).

## folyt.96 (2026-07-11) — ★★ RUNTIME FRAMER LEVER FOUND ON UT (POWER_REQ cycle works at runtime)
Executed folyt.95 step (2). RESULT overturns the "framer bring-up is ADSP-BOOT-ONLY" prior (that prior came from
pmOS, where the framer never comes up regardless — a bad reference).

**Mechanism = NGD runtime-PM on `/sys/devices/platform/soc/c140000.slim/power/{control,runtime_status}`** (runtime-PM
IS supported on this node; the tasha codec children show `unsupported`, but the NGD controller c140000.slim cycles).
On UT the SLIMbus/NGD block runtime-SUSPENDS at idle → its 0x0c14xxxx MMIO gates and reads a **constant junk 0x40/0x50
every word** (NOT a hang, NOT 0 — this block returns a small constant when its AHB clock is gated; safe to read, empirically
confirmed both gated and active). This is why an idle `/dev/mem` read now shows 0x40, while the docs' golden 0x060d1901 was
captured right after boot before autosuspend.

**Full reversible cycle proven on UT (reboot-free, at will):**
| state | how | FRM_STAT@0c140404 | FRM_CFG@0c140400 | NGD_CFG@0c141000 | NGD_STAT@0c141004 |
|-------|-----|-------------------|------------------|------------------|-------------------|
| SUSPENDED (gated) | `echo auto > control` + idle | 0x40 / 0x50 | 0x40/0x50 | 0x40/0x50 | 0x40/0x50 |
| ACTIVE (re-framed)| `echo on > control`         | **0x060d1901** | 0x000d0c83 | 0x00000007 | 0x000d040e |

⇒ **The framer physically TEARS DOWN and RE-FRAMES at runtime on UT via POWER_REQ(ACTIVE), triggered by NGD runtime-PM
resume.** `echo on` = pm_runtime_forbid→resume→POWER_REQ(ACTIVE); `echo auto`+idle = autosuspend→POWER_REQ(INACTIVE).
runtime_status flips suspended↔active in lockstep with the register cycle. Oracle returned to natural suspended state
(healthy, no reboot).

**Why this matters (the folyt.95 payoff, achieved WITHOUT ADSP-SSR):**
- The framer bring-up is now a **discrete, instrumentable, reboot-free RUNTIME event on the WORKING side.** Boot-time it
  was too early/noisy for clean ftrace; now I can ftrace/register-watch/fw-cave the exact suspend→resume transition.
- Reconciles with S3 NO-GO (folyt earlier): S3 used **unbind/rebind on pmOS** (framer never up) and found the HalHwIo leaf
  didn't re-run. That was pmOS + a different mechanism + the refuted leaf (f019aaf8/abb0, later killed in folyt.94). It did
  NOT test the UT runtime-PM resume. The two are not in conflict: **UT re-frames on runtime-PM resume; the leaf that does it
  is still unidentified (f019aaf8 refuted).**
- Gives the clean two-sided differential harness: SAME knob (`echo on > .../slim/power/control`) on pmOS → does the framer
  re-frame? Expected NO (boot showed POWER_REQ ACKed, FRM_STAT stays 0), but now testable at RUNTIME, reboot-free.

**NEXT (ranked):**
  (a) **ftrace the UT resume NOW** (clk/regmap/scm/rpm_smd/qcom_smd + slimbus events) across one suspend→resume cycle —
      first clean capture of the working framer bring-up as a runtime event. Cheap, no reboot, on the working side.
  (b) **pmOS side of the SAME cycle:** find c140000.slim (mainline name) runtime-PM node, `echo on`, read FRM_STAT →
      two-sided runtime differential with the validated mechanism (needs slot switch to pmOS).
  (c) **fw-cave during a UT runtime resume** — once the real framer-program leaf is located (still needs static RE);
      resume genuinely re-frames on UT so the leaf MUST run during resume → captures the working-side programming values.

### folyt.96b — AP-side ftrace + SMEM_LOG of the working UT runtime resume (both exhausted)
Instrumented one clean suspend→resume cycle on UT (NGD runtime-PM), events: clock_enable/disable/set_rate, scm_call,
rpm_smd (active+sleep), regmap. Idle-only 4s control run for attribution.
- **clock_enable during resume:** ONLY display (dsi/mdss/pclk), GPU (oxili/gfx3d/bimc_gfx), SDCC(eMMC), IPA — background
  subsystems. **ZERO LPASS/audio/slimbus/q6/adsp clock.** regmap writes = 0.
- **rpm_smd:** dominated by rsc_type 'bslv' (0x766c7362) votes — but these are DENSE in the idle window too (before the
  resume marker) ⇒ background bandwidth/QoS voting, NOT a framer signal. (Initial excitement retracted — measurement
  integrity: idle window already full of them.)
- **scm_call (5, all in resume window; idle-only control = ZERO scm):** 2× 0x42000c02 from QSGRenderThread/kgsl_worker =
  GPU/display compositing (greeter drew a frame); 2× 0x42000d0d + 1× 0x42000d07 from kworker/u16 = unattributed, but the
  QMI POWER_REQ path is TZ-free so these are unlikely to be slimbus (probably a concurrent workqueue task). Not pursued —
  a QMI-only resume shouldn't make AP SCM calls.
- **SMEM_LOG (item79) across resume:** write-ptr advanced 77 records, but ALL were sensor/IPC-router envelope (svc 0xbb,
  "SNS_"/"IPCS"). No SLIMbus svc-0x301 records → the SLIMbus QMI is not logged in item79. Instrument gives no framer detail.
⇒ **The AP side of the working framer resume does essentially NOTHING SLIMbus-specific: no clock, no regulator, no regmap,
no attributable SCM — just the (untraced) QMI POWER_REQ(ACTIVE) to the ADSP.** Reconfirms the framer is 100% ADSP-internal.
**UT-side AP runtime instrumentation is EXHAUSTED.** The only remaining variable is the ADSP's internal response to POWER_REQ.

### FRONTIER (post-folyt.96): tightened
Given byte-identical fw AND now a runtime-repeatable framer bring-up on UT (POWER_REQ ACTIVE → re-frame) where the AP does
nothing but send QMI, the divergence is purely **the ADSP's internal response to POWER_REQ(ACTIVE): frames on UT, dead on
pmOS.** Identical fw + different response ⇒ the ADSP reads a different INPUT (a HW/PLL/LPASS reg state, or a TZ-auth-left
state). NEXT decisive move = the two-sided runtime differential with the validated lever:
  **pmOS: does its NGD runtime-PM resume re-frame?** (expected NO; makes pmOS a fast reboot-free dead-framer bed for cave/RE).
Then fw-cave the real framer-program leaf (needs static RE) armed on a UT resume (known-good) vs pmOS resume (dead).

### folyt.97 (2026-07-11) — STATIC RE of the framer-clock enable leaf (limit reached → dynamic-capture cave designed)
Goal: find the physical framer-clock (LPAPLL1→SLIMbus core rclk 24.576MHz) register-poke leaf in adsp.mbn to cave it.
Tooling: llvm-mc-21 --arch=hexagon --disassemble via fp3-scripts helper; VA→FOFF base = 0xf00fd000 (verified: splice stock
11406070 @ foff 0x3c2ba0 = VA 0xf04bfba0). durable mbn = scratchpad-durable-adsp.mbn (9962764 B, build ADSP.VT.3.0-00161).

**Call chain decoded (static):**
- `f019eb40` (leaf state-machine, = handle+0x48): checks handle+0x38≠0 AND handle+0x44 bit0; then calls
  `f01a12bc(r0=handle, r1=#1)` (enable, cmd=1) and stores rc to handle+0x48. (Also a big switch r0 vs 1,2,4,8..4095 =
  gear/bit-index→rodata clock-name lookup; the two callr targets are f01a12bc=0xf01a12bc and f01a1538.)
- `f01a12bc` (NPA enable-op): r16=object, **r17=subobj=memw(handle+0x10)**. Two indirect dispatches:
   1. `r2=memw(r17+#20); callr memw(r2+0)` — r17+0x14 = **rodata HAL vtable 0xf066a688** → `f01a09bc` (STATIC).
   2. `r3=memw(r17+#4); callr memw(r3+#4)` — r17+0x4 = **RUNTIME driver-node ptr** → the physical-work fn.
- `f01a09bc` = array-indexed vote/freq aggregator (minu/maxu over memw(r5+r7<<3) tables) — **NO HWIO poke** (confirmed).

**CONCLUSION (defensible RE limit):** the physical CBCR poke is **runtime-dispatched via subobj+0x4** (a runtime-registered
driver node); its fn address is written into a runtime vtable at init, so **pure static RE cannot pin it**. The rodata HAL
methods (f01a09bc aggregator, f01a0d0c bookkeeping) are not pokes. ⇒ Must resolve the leaf **dynamically**.

**folyt.96 makes this iterable:** the enable path re-runs at runtime on UT (framer re-frames on resume), so a cave placed on
this path WILL fire on a runtime `echo on > .../c140000.slim/power/control` — no reflash per iteration once a caved fw is loaded.
(Caveat to test FIRST: does the *runtime resume* re-enter f01a12bc, or a different runtime-PM-specific path? The report's
"boot-time-once" claim was pre-folyt.96 and pmOS-only; must verify on UT with an invocation counter.)

**NEXT BUILD (folyt.97 cave — reuses folyt.94 fix-VA machinery):** splice in `f01a12bc` after `r17=memw(r16+#16)` +
null-check, capture to SMEM stash (≤0x50B, PA 0x86302ab0 region): magic, invocation-counter, handle(r16), subobj(r17),
memw(r17+0)=class ptr, **memw(r17+4)=driver-node ptr, memw(memw(r17+4)+4)=RESOLVED physical-op fn (the leaf!)**,
memw(r17+0x14)=rodata vtable. Straight-line, null-guarded, single exit, NO cave-issued MMIO (rule 4). Then: sign (qtestsign
-v3), build ut-p1 image, flash UT p1 once, reboot, then runtime resume cycles reading the cave → (1) counter proves runtime
re-run, (2) the resolved fn addr = the leaf to disassemble next for the actual HWIO poke + poll-mask.
Device now: slot_a/UT stock, NGD control=auto (healthy). No fw flashed yet.

### folyt.98 (2026-07-11) — ☠️ CRITICAL DATA-INTEGRITY FINDING: durable = pmOS fw ≠ UT stock fw (premise contradicted)
Building the folyt.97 SN97 cave, I deployed a durable-based split to UT p1 → PIL **"Failed to load segment[8]/[9], ret=-1;
Q6 image loading failed"** → ADSP never booted (framer dead, cave magic absent). Root cause found by direct comparison:

- `scratchpad-durable-adsp.mbn` md5 = **3ed6924d** = the documented **pmOS stock adsp.mbn** (context line 388, memory index).
- UT p1 stock adsp.mdt md5 = **bab175ed** (different file).
- **Direct segment compare: pmOS(durable) seg4 vs UT stock b04 — SAME length (0x69c910) but 864066/6932752 bytes (~12.5%)
  DIFFER**, first diff @0xc51. Diff is clustered: heavy at 0x010000–0x050000 and **NEAR-TOTAL (~90%) at 0x500000–0x5e0000
  (~1MB)**; the middle (0x110000–0x200000) nearly matches. The splice word (11406070 @ in-seg 0x360ba0) happens to match.
- **Version strings are IDENTICAL** in both (`ADSP.VT.3.0-00161-00000-1_20200518_015733`, same build id+timestamp).
- ☠️ **The cave region (in-seg 0x4ef098) is NOT zero in UT stock** (it is in the pmOS durable) → a durable-based cave would
  overwrite real UT code even if it loaded.

**CONSEQUENCES (honest, measurement-integrity):**
1. **folyt.94 "UT positive control" (HWL4) is INVALID.** It used the same durable→UT-split-into-stock recipe, so it ALSO
   failed PIL segment-load → the ADSP never booted → the HWL cave's absence proved NOTHING about whether f019abb0 runs at
   boot. The "CONFIRMED refutation of f019aaf8/abb0" must be **downgraded to UNKNOWN** (the refutation may still be true, but
   this experiment did not establish it).
2. **The foundational premise "adsp.mbn byte-identical UT↔pmOS (cmp, HARD)" (context line 165) is CONTRADICTED** by a direct
   segment diff (12%, incl. a ~1MB near-total-diff region). Either the original `cmp` was flawed/measured something else
   (note the separate, weaker F6 claim is only *version-string* identity), or UT and pmOS genuinely ship different ADSP
   binaries under the same version tag. **This reopens whether the framer difference is firmware after all** — the
   near-total-diff 1MB region (0x500000–0x5e0000, likely a data/config/calibration blob) is a prime suspect and was never
   examined. DO NOT keep asserting "identical fw → purely environmental" until this is re-verified.
3. All prior firmware caves (T3/SNPA/SNPB/register-level-v4) were deployed to **pmOS** (single self-consistent mbn, PAS) →
   those remain valid *for pmOS*. The RE call-chain addresses are valid *for the pmOS(durable) fw*, NOT necessarily UT stock.
4. **folyt.96 (runtime framer lever on UT) is UNAFFECTED** — it is a pure register/runtime-PM observation, no firmware involved.

**REPLAN:**
- To cave the WORKING (UT) side, must base the patch on **UT stock fw** (reconstruct mbn from UT split → RE addresses on IT
  → patch → qtestsign → re-split → inject full/consistent set). The RE must be redone/verified on UT stock (code differs 12%).
- To cave pmOS, the durable-based SN97 IS valid (self-consistent) → deploy to slot_b/pmOS: at pmOS boot the config-group
  enable runs (rc=0 false success), the cave fires, resolving the runtime-dispatched leaf address (as pmOS sees it).
- **FIRST, re-verify the byte-identity premise**: reconstruct the UT mbn from its split and cmp to the pmOS durable
  segment-by-segment; characterize the 0x500000–0x5e0000 region (code vs data; what it holds). This gates the whole framing.
Device: slot_a/UT stock restored, framer ALIVE (tasha=2, pgd/ifd/sb-1), healthy. No bad fw left on device.

### folyt.98b — full per-segment UT vs pmOS(durable) diff (premise resolution data)
Same version string AND same build timestamp (_20200518_015733) in both, yet:
  seg00 hdr 0% | seg01 hash 16% | seg02/03 ~0% | seg04(code 0xf015f000) 12% | seg05 3% | seg06/07 0% |
  seg08 0% | seg09 8% | seg10(0x2db00000) 57% +size-differ(0x20) | seg11(0x2dbef000) 29% +size-differ |
  seg12 13% | seg13 0% | seg14 19%
Interpretation (measured, cautious): identical build-timestamp argues these are the SAME source build, so the heavy diffs
in the 0x2dxxxxxx DDR-data segments (seg10/11/14, incl. size differences) are most likely **packaging/data-blob or
padding/alignment differences between how UT (vendor split) and pmOS (repacked single mbn) store the image**, NOT different
compiled logic. BUT seg04 (pure code, 0xf015f000) differs 12% at same size/alignment — that is harder to explain as
packaging and is the item that must be nailed down. NEXT (offline, safe): disassemble a few matching-vs-differing spots in
seg04 to see if the 12% is real instruction differences or a systematic artifact (e.g., relocations/pointers baked
differently); characterize the 0x500000-0x5e0000 near-total-diff sub-region (strings? data table?). Until resolved, treat
"byte-identical fw" as UNPROVEN, and treat "the difference is purely environmental" as an open question, not a settled frame.

### folyt.98c — characterization: the UT↔pmOS diffs are per-instruction SMALL deltas, not different logic
Classified all 264600 differing 4B words in seg04: only 2% are pointer-like (0xf0/0x2d/0x8b VA space); 98% are tiny
systematic deltas in single instruction bytes (samples: 7850cd03/cf03, 4bd0ca06/cc06, 4b904804/4a04, 6a033c10/6b033c10 —
+1/+2 in a register/immediate/address field). Combined with IDENTICAL build timestamp + IDENTICAL strings + IDENTICAL
structure, this is NOT wholesale-different firmware/logic — it is the same build differing by pervasive small per-instruction
values (relocation/rebasing), OR an artifact of the `scratchpad-durable` being a *processed* reference rather than the raw
pmOS partition.

**RESOLVED framing (honest):**
- "adsp.mbn byte-identical UT↔pmOS" (context line 165) is **literally FALSE** (pervasive small diffs) — but the images are
  the **same build/logic**, so the premise's *intent* ("both run essentially the same ADSP code") is likely intact. The
  framer difference is still most plausibly environmental, BUT this was never as airtight as "byte-identical" implied.
- ☠️ Caveat: `scratchpad-durable-adsp.mbn` (md5 3ed6924d) may be a **processed** working copy, not the raw pmOS partition.
  A clean test = read slot_b/pmOS partition adsp.mbn RAW and UT slot_a reconstructed mbn RAW, then cmp. Until then the exact
  UT↔pmOS byte relationship is UNCERTAIN.
- **Operationally robust (regardless of the above):** any firmware artifact (hashes/cave) is slot-specific — a durable-based
  image CANNOT load on UT (PIL hash mismatch), which is why H97 failed and why folyt.94's HWL4 "positive control" was invalid
  (→ f019aaf8/abb0 refutation = UNKNOWN, not CONFIRMED).

**Clean next steps (offline/safe):** (1) get the RAW pmOS partition adsp.mbn (slot_b) + reconstruct UT mbn from slot_a
split; cmp to settle the premise with clean references. (2) For a UT-side cave: RE + patch on UT-stock b04 (code differs, so
verify f04bfba0/f019eb40/f01a12bc/cave-region on UT stock before building). (3) For a pmOS-side SN97 cave: durable-based
build is valid → deploy slot_b; boot config-group runs (rc=0) → resolves the runtime-dispatched leaf.

### folyt.99 (2026-07-11) — TEST: pmOS adsp fw on UT (PIL) → device STUCK, recovery pending
Discriminating experiment (does pmOS fw boot audio on UT?): signed durable(pmOS fw) qtestsign-v3 → FULL split (all 16 segs +
compact mdt, self-consistent) → injected ALL into ut-p1-stock.img copy = ut-p1-pmosfw.img → dd to UT /dev/mmcblk0p1 (=modem_a;
only adsp.* changed, modem intact) → reboot. RESULT: UT did NOT return to adb; device stuck at USB **0000:0afe "Fairphone FP3"**
(NOT normal booted 05c6:9024, NOT fastboot, NOT 900e) for >5 min. adb/fastboot both see nothing; adb server restart no help.
Likely a boot hang (pmOS adsp fw incompatible with UT PIL bring-up / audio-HAL hard-wait) OR flaky UT reboot.
RECOVERY PLAN (needs physical): power-cycle → if UT boots to adb, dd ut-p1-stock.img back; if stuck again, enter fastboot
(bootloader) → `fastboot flash modem_a ut-p1-stock.img` (mmcblk0p1 = modem_a) → reboot. Backup intact: ut-p1-stock.img
(md5 e5de6864). Artifacts: adsp-pmosfw-signed.mbn, ut-pmosfw-split/, ut-p1-pmosfw.img.

### folyt.99 RESULT — ★★ pmOS adsp fw BOOTS AUDIO ON UT (PIL) → firmware DEFINITIVELY EXONERATED
After login+USB-replug (flaky-reboot recovery; it was NOT a real hang — UT booted, adb just needed replug), the pmOS fw
(mdt 2cee0f1e on partition) on UT/PIL:
- **tasha snd-card present + tasha-slim-pgd/ifd + sb-1 ENUMERATED** (codec got a logical address → framer clocks the bus).
- **FRM_STAT = 0x060d1901** (physically framing, identical to stock-UT), FRM_CFG=0x000d0c83, NGD_CFG=7, NGD_STATUS=0x000d040e.
- ASM stream activity in dmesg (audio DSP live).

⇒ **The EXACT pmOS adsp firmware brings the framer up under UT/PIL, while the SAME fw is dead under pmOS/PAS
(FRM_STAT=0, 0x40c).** This is a direct fw-swap cross-test — the cleanest possible discriminator.

**CONCLUSIONS (robust):**
1. **Firmware is DEFINITIVELY NOT the differentiator.** folyt.98's "premise contradicted / maybe fw differs" worry is
   RESOLVED: the byte-level UT↔pmOS diffs (relocations/rebasing) are irrelevant — the pmOS fw content is fully capable of
   framing; it does so under PIL. The original "environmental, not firmware" framing is now on FIRM ground (direct swap,
   not a byte-identity claim).
2. **The difference is purely the boot ENVIRONMENT: PIL (subsys-pil-tz, UT) vs PAS (qcom_q6v5_pas, pmOS).** Same fw →
   PIL frames, PAS does not. The investigation refocuses squarely on what PIL establishes that PAS doesn't (the LPASS
   clock/power precondition the ADSP needs before its internal framer PLL can lock).
3. This also gives a VALID positive control (unlike the invalid folyt.94 HWL4): a full self-consistent split of a
   durable-based image DOES load + frame on UT — so the split/sign pipeline is correct; folyt.94 failed only because it
   injected a PARTIAL set (mdt/b01/b04) leaving mismatched stock segments.
Device: slot_a/UT running pmOS-fw (framer alive, functional); restoring canonical stock next.

### folyt.100 (2026-07-11) — "proof of the working side": runtime re-triggers EXHAUSTED, boot-ftrace is the only path
Goal (user): first capture what the WORKING PIL path does (SCM/clock/regulator) during ADSP bring-up, as ground truth.
Findings on re-trigger feasibility on UT:
- **No userspace ADSP-SSR trigger:** subsys2=adsp restart_level=SYSTEM; no /sys/kernel/debug/msm_subsys (even with
  subsystem_restart enable_debug=1); no restart/crash sysfs. (confirms folyt.95 blocker.)
- **unbind/rebind of subsys-pil-tz FAILS:** `echo c200000.qcom,lpass > .../subsys-pil-tz/unbind` then `.../bind` → rebind
  probe FAILS: `genirq: Flags mismatch irq 364 (adsp)`, `Unable to request proxy unvote IRQ: -16`, `probe of
  c200000.qcom,lpass failed with error -16`. The unbind leaks the proxy-unvote IRQ so re-probe can't re-acquire it. The
  ADSP itself was NEVER stopped (framer stayed alive tasha=2) → this does NOT re-run the bring-up; the captured trace
  (only pm8953_l8 regulator toggle + SDCC clocks, ZERO scm_call) is just failed-unbind noise, NOT the bring-up.
- ⇒ The ONLY way to observe the full PIL ADSP bring-up (pas_init/auth_and_reset SCM + proxy clocks/regs) on UT is a
  **boot-time ftrace** (cmdline `trace_event=scm:*,regulator:*,power:clock_*` + big buffer; the bring-up runs ~20s into
  boot, captured in the ring, read after boot). Needs a boot.img cmdline change + reflash (boot_a=mmcblk0p27). Caveat:
  the boot.img cmdline field may be near-full and the bootloader (lk2nd/ABL) appends dm=/vbmeta/root — verify room.
- ☠️ Side effect to clean up: the failed rebind left c200000.qcom,lpass UNBOUND (ADSP still running, framer alive, but AP
  driver detached) → reboot to restore clean binding. Device: slot_a/UT stock fw, framer alive; rebooting to re-bind.

### folyt.100b — boot-ftrace of PIL bring-up DEFEATED by userspace; live capture on UT EXHAUSTED
Flashed a traced boot_a (cmdline += `trace_event=scm:*,regulator:* trace_buf_size=64M`, id recomputed; boot_a=mmcblk0p27,
backup ut-boot_a-backup.img). Booted (needed login+replug). RESULT: the ftrace ring captured scm+regulator only from
0.3s→6.97s, then **tracing_on flipped to 0 at ~7s** (UT userspace/init disables ftrace) — while the ADSP PIL bring-up runs
at **20.1s** (`adsp: loading`→`Brought out of reset`@20.37s→`Power/Clock ready`@20.40s). So the auth_and_reset window is
AFTER userspace killed tracing → NOT captured.
Also: adsp-loader unbind/rebind (`soc:qcom,msm-adsp-loader`) does NOT restart the ADSP (framer stays alive); only surfaced
GPU scm (0x42000c02) + two kworker/u16 SCM svc-0xd calls (0x42000d0d args incl. ascii "pm8953_l..."; 0x42000d07) — same
mysterious pair from folyt.96b, still not the auth_and_reset.
⇒ **Live capture of the working PIL auth_and_reset SCM sequence on UT is EXHAUSTED** (SSR: no node; subsys-pil-tz
unbind/rebind: IRQ-leak probe-fail, no restart; adsp-loader rebind: no restart; boot-ftrace: userspace disables tracing_on
at 7s < 20s load). Remaining options are heavier: (a) find+neutralize the userspace tracing_on-disabler (rootfs mod) so the
boot ring survives to 20s; (b) custom UT kernel with an early ADSP-scm snapshot trigger; (c) SOURCE-level SCM diff
(subsys-pil-tz.c vs qcom_q6v5_pas.c) — offline, labeled soft. Device: slot_a on TRACED kernel (functional, framer alive,
stock adsp fw); ut-boot_a-backup.img restores canonical boot.

### folyt.101 (2026-07-11) — SOURCE-level PIL vs PAS: AP proxy resources are EQUIVALENT (negative but narrowing)
Since live capture is blocked, did the source-level diff (labeled SOFT). pmOS PAS path (qcom_q6v5_pas.c):
- `qcom,msm8953-adsp-pil` → `msm8996_adsp_resource`: proxy_pd_names={"cx"}, firmware_name="adsp.mdt", pas_id=1, ssctl 0x14.
- driver enables clk "xo" (+ optional "aggre2", absent on msm8953) + proxy PD "cx".
- SCM crypto clocks handled by the `qcom,scm-msm8953` node: clocks = GCC_CRYPTO_CLK/AXI/AHB (core/bus/iface) → qcom_scm
  enables them around SCM calls.
vs UT PIL proxy (F1-UT): {xo, crypto-auth scm_core/iface/bus/core_src, vdd_cx}.
⇒ **The AP-side proxy resource sets are EQUIVALENT: xo (both), cx (both), crypto core/bus/iface (both — PIL via pil-tz
proxy, PAS via qcom_scm node).** Both load adsp.mdt to the SAME carveout (adsp@0x8d600000 in DT), both use TZ PAS SCM
(pas_init_image/mem_setup/auth_and_reset). ⇒ the "PIL votes a resource PAS doesn't" hypothesis is FALSE at source level.
**Frontier (post-fw-exoneration):** fw exonerated (folyt.99); AP proxy resources equivalent (this) → the PIL-vs-PAS
divergence is NOT AP resource provisioning. It is in the TZ/PAS call **sequence/arguments/timing** or TZ-internal behavior,
below AP visibility. The one thing source can't settle is whether the runtime SCM arg/sequence actually matches (live
capture blocked). Candidate deeper probes: (a) diff pas_init_image/mem_setup/auth_and_reset arg construction pil-tz vs
qcom_q6v5_pas (needs UT downstream source); (b) the QDSP6SS/halt-reg handling (does either poke Q6SS pre-auth?);
(c) memory-ownership (hyp_assign/pas_mem_setup) differences. Device: slot_a on traced kernel (functional), backup ready.

### folyt.102 (2026-07-11) — downstream DT+clock source read: AP-equivalence now AIRTIGHT; QDSP6SS direction DEAD
Read the ACTUAL oracle source (`$FP3_PMOS/ubports-fp3-kernel`, 4.9.218 halium-10.0, HEAD 12d9b944c).
- **UT ADSP node** (msm8953.dtsi:2023) `compatible="qcom,pil-tz-generic"` @0xc200000, pas-id=1 → bound to `subsys-pil-tz.c`
  = **pure TZ-PAS wrapper** (pas_init_image/mem_setup/auth_and_reset via SCM). The QDSP6SS-poking drivers
  (`pil-q6v5.c`/`pil-msa.c`) are for the **MSS modem only**, NOT the ADSP. ⇒ **neither** UT nor pmOS does AP-side
  QDSP6SS bring-up on msm8953 → the "QDSP6SS/mem_setup AP-poke" lead is DEAD (no such AP surface for the ADSP).
- **UT proxy set** (from the DT node): `vdd_cx-supply=pm8953_s2_level @ RPM_SMD_REGULATOR_LEVEL_TURBO, 100000uA`;
  clocks/proxy-clocks = `xo(clk_xo_pil_lpass_clk), scm_core, scm_iface, scm_bus, scm_core_clk_src@80MHz`;
  proxy-timeout 10000ms; smem-id 423; ssctl 0x14; pas-id 1. NO vdd_mx, NO LPASS core clock.
- **`clk_xo_pil_lpass_clk`** = `DEFINE_CLK_BRANCH_VOTER(xo_pil_lpass_clk, &xo_clk_src.c)` (clock-gcc-8953.c:93) =
  merely an **XO vote** → functionally identical to mainline `RPM_SMD_XO_CLK_SRC`. Not a distinct LPASS clock.
- **No `lpasscc-msm8953` exists in mainline** (drivers/clk/qcom has only sc7180/sc7280/sdm845/sm6115/… lpasscc). On
  msm8953 the LPASS/SLIMbus core clocks are ADSP-INTERNAL (ADSP fw programs its own LPASS PLL/clocks); there is no
  AP-side LPASS clock controller that could differ between PIL and PAS.
- pmOS PAS votes cx via `dev_pm_genpd_set_performance_state(cx, INT_MAX)` (qcom_q6v5_pas.c:161) = **≥TURBO corner**,
  matching/exceeding UT's TURBO vote. cx-corner hypothesis DEAD.

**CONCLUSION (source, now HARD to the extent source can be):** every AP-visible input to TZ is equivalent PIL↔PAS —
same pas_id(1), same carveout (adsp@0x8d600000), same metadata (fw exonerated folyt.99), same xo-vote, same cx@≥TURBO,
same crypto core/iface/bus. Same device ⇒ same TZ image (tz partition, flashed from same stock). So TZ receives
**identical inputs** yet framer differs. ⇒ the differentiator is NOT AP resource provisioning and NOT an AP LPASS clock.

**REFRAME of the frontier:** the remaining AP-visible layer between "ADSP running" and "framer framing" is the
**NGD/QMI SLIMbus handshake** (slim-qcom-ngd-ctrl → ADSP SLIMbus service 0x301, node 5). The framer is brought up in
response to the AP NGD's QMI power-up request; the known upstream qcom-ngd-ctrl PAS-race (patchwork 1075549) is exactly
"NGD probes after ADSP already up (PAS case) → power-up request path mis-sequenced". This has NEVER been measured on
pmOS as an ADSP-up-but-NGD-handshake-fails discriminator. NEXT (LIVE, on slot_b/pmOS): determine whether pmOS's ADSP
boots OK (remoteproc running + QMI SLIMbus svc 0x301 present) with the framer dead (⇒ NGD-handshake layer, AP-fixable),
or the SLIMbus QMI service is absent (⇒ deeper). Also try the folyt.96 runtime-PM lever ON pmOS (does power/control=on
kick the QMI power-up request?). Device: slot_a/UT traced kernel, framer alive; switching to slot_b/pmOS for the measurement.

### folyt.103 (2026-07-11) — LIVE pmOS measurement + PAS proxy-hold experiment
Booted slot_b/pmOS (kernel 7.0.9-msm8953) and took the discriminating measurement (ADSP-up-but-handshake vs deeper):
- **ADSP fully UP**: remoteproc2 `adsp -> running`, adsp.mbn loads, "remote processor adsp is now up" @13.4s.
- **ADSP audio DSP ALIVE**: APR/GPR audio services registered (aprsvc:service:4:3..4:b).
- **SLIMbus QMI power request SUCCEEDS (acked)**: `DBG power_up: QMI power request OK`, ver=0x105, then `ngd_status=0x40c`.
  ⇒ NOT a QMI-handshake failure — the ADSP acks the AP's SLIMbus power-up request.
- **Framer never frames anyway**: `capability exchange timed-out STATUS=0x40c CFG=0x0 INT_STAT=0x0`; codec
  `wcd9335-slim: Failed to get logical address`; `TX timed out MC:0xd`. Retries (state=3 then state=2), same result.
- NGD QMI 301 traffic already matches downstream exactly (prior note 2026-06-30 in the driver: SELECT_INSTANCE(0x20,
  mode=MASTER via apps_is_master=false @ line 1412) + POWER_REQ(0x21), no CHECK_FRAMER on 301). So QMI layer exhausted.
⇒ Failure is strictly BETWEEN power-ack and framer-clocking-the-bus. QDSP6SS is NOT an AP surface on msm8953 (folyt.102);
  the remaining AP-tunable PAS difference is the PROXY-VOTE HOLD.

**LIVE POWER STATE (pm_genpd_summary):** `c200000.remoteproc` = **suspended, performance 0** — the ADSP's cx proxy
vote (voted INT_MAX in qcom_pas_pds_enable at start) has been **DROPPED at handover** (qcom_pas_handover:396 →
qcom_pas_pds_disable sets cx perf 0 + puts, and unvotes xo). `cx` domain is only held at **perf 48 by the GPU**
(oxili_gx_gdsc etc.) — possibly BELOW the corner the ADSP framer PLL needs. LPASS_CLK_ID_* (Q6AFE audio-lane clocks)
all idle except internal-digital-codec core; those are not the SLIMbus framer clock.

**EXPERIMENT (single change, boot-safe):** neutralize `qcom_pas_handover()` → do NOT release proxy; hold cx@INT_MAX +
xo for the whole uptime. DBG breadcrumb "DBG folyt103: handover fired - HOLDING proxy". Vehicle: MODULE hot-swap
(CONFIG_QCOM_Q6V5_PAS=m) → build → replace qcom_q6v5_pas.ko → reboot → capture.
- **Hypothesis:** framer PLL needs sustained cx@max the ADSP's own post-handover self-vote doesn't supply.
- **Signal:** FRM/NGD via dmesg + /sys/bus/slimbus/devices laddr.
- **PASS:** framer frames (ngd_status has NGD_LADDR / capability exchange completes / wcd9335 gets laddr / snd tasha-slim
  enumerated). **FAIL/baseline:** still STATUS=0x40c, capability timeout, no laddr.
- **Interpretation guard (marker-vs-lever):** if PASS, this is a real AP lever (proxy hold) → candidate fix. If FAIL,
  the entire AP power/proxy axis is EXCLUDED live (not by source-reasoning) → answer is TZ-internal/ADSP-self-vote path.
Build: linux-postmarketos-qcom-msm8953 --src (running). Device: slot_b/pmOS, framer dead (baseline reconfirmed).

### folyt.103 RESULT — PAS proxy-hold: framer STILL DEAD → AP power/proxy axis EXCLUDED (live)
Hot-swapped patched qcom_q6v5_pas.ko (vermagic 7.0.9-msm8953 match; md5 a13a7348), clean reboot.
- **Code path CONFIRMED ran**: `qcom_q6v5_pas c200000.remoteproc: DBG folyt103: handover fired - HOLDING proxy (cx+xo)`.
- **Proxy IS held**: pm_genpd_summary now `cx ... c200000.remoteproc active, performance 2147483647` (INT_MAX) for the
  whole uptime — vs baseline (folyt.103 pre) `suspended, performance 0`. The intended change took effect exactly.
- **Framer STILL DEAD (identical baseline)**: `ver=0x105 ngd_status=0x40c` → `capability exchange timed-out
  STATUS=0x40c CFG=0x0 INT_STAT=0x0`; `wcd9335-slim: Failed to get logical address`; `TX timed out MC:0xd`;
  `slimbus 217:1a0:1:0: deferred probe pending`. snd = bare "Fairphone 3" (no tasha-slim). adsp=running.
⇒ **VERDICT (marker-vs-lever = FAIL/exclusion):** sustained AP cx@INT_MAX + xo does NOT enable the ADSP SLIMbus framer.
  The **entire AP power/proxy axis is EXCLUDED by a live experiment** (not source-reasoning). Combined with fw-exoneration
  (folyt.99), AP-resource-equivalence (101/102), QMI-301-match (prior), and QDSP6SS-not-an-AP-surface (102): **no
  AP-visible lever remains.** The PIL↔PAS differentiator is below AP visibility — TZ-internal (PAS SCM arg/metadata/mem
  ownership) or an RPM/interconnect global state the downstream boot establishes that mainline does not.
Revert: `git checkout drivers/remoteproc/qcom_q6v5_pas.c` in linux-fp3; device orig .ko backed up at
$HOME/qcom_q6v5_pas.ko.orig (restore + depmod + reboot). Device: slot_b/pmOS, patched .ko live (proxy held), framer dead.
NEXT candidate (AP-testable, NOT yet excluded): interconnect/RPM bandwidth votes — does downstream vote an LPASS/SLIMbus
NoC path (msm-bus) that mainline's adsp/slim nodes never request? Check icc summary + downstream bus votes.

### folyt.103 addendum — AP NGD driver ALSO matches downstream (last AP-side check)
Compared mainline qcom-ngd-ctrl.c vs downstream slim-msm-ngd.c end-to-end:
- power_up flow identical: qmi_power_request(true) → read NGD_STATUS → (if !laddr) program NGD_INT_EN + RX_MSGQ timeout
  → ngd_setup → wait reconf(1s).
- **NGD_CFG write identical**: both write `NGD_CFG_ENABLE(BIT0) | RX_MSGQ_EN | TX_MSGQ_EN` to NGD base. Mainline's
  `CFG=0x0` at timeout is a SYMPTOM (block held unclocked by ADSP while framer down), not a missing enable write.
- select_inst mode=MASTER (apps_is_master=false) both; check_framer(0x22) not on svc301 (prior session tried it, no help).
⇒ **AP side is provably complete & downstream-equivalent** (power/proxy/QMI/NGD-setup/CFG). Device reverted to baseline
  (source git-checkout; device .ko restored to orig b723524a, effective next boot; current boot still has proxy-held .ko).

## ★ CONSOLIDATED VERDICT (post-folyt.103) — the AP is fully exonerated; the wall is below AP
fw (folyt.99 swap) = exonerated · AP proxy resources (101/102) = equivalent · AP proxy POWER held@max (103) = excluded LIVE
· QMI 301 traffic (prior) = matches downstream · QDSP6SS (102) = not an AP surface on msm8953 · AP NGD setup/CFG (103add)
= matches downstream · same SoC ⇒ same TZ image. **No AP-visible lever remains.** Same fw + same TZ + same AP env →
framer frames under PIL, dead under PAS. The differentiator is TZ-internal (PAS SCM metadata/mem-ownership the two kernel
wrappers construct differently) or a global RPM/TZ state the downstream boot establishes. Going deeper requires either
TZ-side RE (adsp.mbn already RE'd; TZ/tz.mbn not) or a strategy pivot. This is a genuine fork → surfaced to user.
