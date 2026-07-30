# FP3 audio (SLIMbus) — entry context for a new session

> **★★★★★★ FULLY SOLVED — AUDIBLE SOUND (folyt.208, 2026-07-24): clean music plays in the headphones, with correct rhythm and pitch, and working volume control. The project's GOAL is met on the earpiece/headphone SLIMbus path.**
> The solution was TWO independent breakthroughs, one after the other:
> 1. **Framer wall (folyt.196-199):** QDSP6SS `0x0c20002c` bit3 (see below) → the WCD9335 enumerates / gets a logical address.
> 2. **Missing physical MCLK (folyt.208):** the codec-MCLK `func1` pinmux (pm8953 gpio1 → RPM DIV_CLK2) was NEVER applied, because the `gpio-gate-clock` DTS node used `pinctrl-names="active","sleep"` instead of `"default"` (the clk-gpio driver does not select pinctrl states; the driver core only auto-applies `"default"` at probe). The proof was `pin 0 (gpio1): (MUX UNCLAIMED)`. Additionally the state had to be reduced to the bare mux (extra drive-strength/bias/output pinconf made the state-apply fail → gate-clock probe abort). After the fix: **EFUSE_STATUS 0x00→0x01 (Bert's year-old unsolved wall now completes), 0 RX overflows, the DAC consumes.** Commit `2c2fd91` on fork `fp3-7.0.9-audio` (pushed, over port 443; SSH push on port 22 stalls on the live-USB network).
> **Volume control (folyt.208b):** the headphone path runs through the interpolator's SECONDARY/MIX branch (INT1_2/INT2_2 MUX → SEC MIX) → the real loudness control is **`RX1/RX2 Mix Digital Volume` (numid 13/14)**, NOT the plain `RX Digital Volume` (numid 4/5, main branch, no effect) and NOT `HPHL/HPHR Volume` (numid 49/50, PA gain only, 0…+1.4 dB). Comfortable: Mix=48 (~−36 dB). Ground truth: the `On` widgets under `/sys/kernel/debug/asoc/Fairphone 3/217:1a0:1:0/dapm/*`.
> **Remaining (optional, separate task):** the microphone path (AMIC audio-routing bring-up); the base AMIC routing was removed (those are PM8953 analog-codec widgets, which do not exist on the FP3). Outreach: #255 CLOSED by the user; the linux-arm-msm SOLVED mail + the Bert reply drafts are ready, the user sends them.
>
> **★★★★★ SOLVED (folyt.196-199, 2026-07-23): the root of the framer wall is QDSP6SS `0x0c20002c` bit3 — see the first ★★★★★ section below. §0 and every addendum are NOW HISTORICAL.**
>
> **This entry doc holds: the CURRENT, authoritative state (§0) plus the durable reference
> (device, symptom, address map, guardrails, tooling). Live content only — the chronological
> investigation lives in the journals.**
> _This file lives in the `fp3-porting-debug` skill's `references/` directory; the sibling data packs
> below are co-located there too. The journal and the scripts stay in the project (§9)._
> - **File map + "what have we already examined" table:** `data-index.md` (same dir, references/) ← READ THIS FIRST
> - **Live tracker:** `slimbus-audio-tracker.md` (same dir)
> - **Full journal:** `FP3-slim-debug-journal.md` (in the project)
> - **Red herrings (what was ruled out, and why):** `slimbus-audio-red-herrings.md` (same dir)
> - **Full ordering of the working UT framer boot (when/what/boot-vs-userspace):** `ut-framer-boot-sequence.md` (same dir, folyt.194 live capture)
> - **Method/guardrails:** the `fp3-porting-debug` + `fp3-kernel-test` skills

---

## ★★★★★ folyt.196-199 (2026-07-23) — SOLVED: THE YEARS-LONG WALL IS DOWN. ROOT = QDSP6SS `0x0c20002c` bit3. (READ THIS FIRST — every section below, including the folyt.183 reframe, is NOW HISTORICAL)

**The root cause of the framer silence is FOUND and FIXED LOCALLY.** Not a physical wall, not an external BSP/QXDM matter — a single undocumented QDSP6SS register bit.

### The root cause
The mainline **PAS** boot path leaves **`0x0c20002c` (QDSP6SS, an undocumented register between GFMUX_CTL@0x20 and PWR_CTL@0x30) bit3** SET; the downstream **PIL** path clears it (UT/PIL=`0x103`, pmOS/PAS=`0x10b`). With it set, the ADSP framer **never answers** the SLIMbus master-capability exchange → the WCD9335 gets no logical address → silent audio. The bit is **AP-writable** (not XPU-protected). Cleared, the framer frames.

### How we found it (folyt.196)
Three questions from the user brought it out:
1. "Was there no devcfg diff?" → ruled out (byte-identical).
2. "Could an internal HW register value depend on the load path?" → **YES** → this surfaced the old `report-attachments/DIFF-0xc200000-UT-vs-pmOS.md` (folyt.91) diff, which had recorded the `0xc20002c`: UT=`0x103` vs pmOS=`0x10b` (bit3) difference — but had **never tested it for causality**.
3. "Set the UT value on mainline" → a **LIVE `/dev/mem` write** `0x10b→0x103` LATCHED + re-capability → **`SLIM SAT: Rcvd master capability`** → the codec enumerates.

### The fix (in two layers)
- **PAS driver (`qcom_q6v5_pas.c`)**: a dedicated `msm8953_adsp_resource` desc (`.slim_framer_quirk_reg = 0x0c20002c`, `.auto_boot=true`, `.firmware_name="qcom/msm8953/fairphone/fp3/adsp.mbn"`, `.pas_id=1`); in `adsp_start`, after AUTH_AND_RESET, `ioremap` + `clear BIT(3)`. **⚠️ RACY** (see below).
- **NGD driver (`qcom-ngd-ctrl.c`) — RELIABILITY FIX**: puts the bit3 clear **immediately BEFORE the capability trigger** (`qcom_slim_ngd_power_up`, ahead of `writel(DEF_NGD_INT_MASK)`), driven by the optional DT property `qcom,slim-framer-quirk-reg=<0x0c20002c>` (probe: `devm_ioremap`). **This is the real mechanism.**

### Why the NGD timing is required (folyt.199b, LIVE r14 dmesg evidence)
```
[20.012] slim-framer quirk: QDSP6SS 0xc20002c 0x101->0x101   ← PAS quirk NO-OP: bit3 is ALREADY 0 here (runs too early)
[21.668] capability exchange timed-out                        ← 1st capability FAILS (the ADSP sets bit3 AFTER the quirk)
[22.788] wcd9335-slim 217:1a0:1:0: Failed to get logical address
[22.796] SLIM SAT: Rcvd master capability                     ← the RETRY succeeds
[22.846] wcd9335-slim 217:1a0:1:0: WCD9335 CODEC version is v2.0  ← codec enumerates (racy)
```
→ The PAS quirk runs **too early** (the ADSP sets bit3 LATER, during its own init). The NGD fix clears it at the right moment (before capability) → the 1st capability should succeed.

### Session tally (all on OUR physical FP3, up to laddr)
own config 0/24 + Bert-full-DT 0/10 + Bert-EXACT-6.11 0/8 = **0/42 laddr BEFORE the bit3 fix** → AFTER the bit3 fix: **the codec enumerates** (r14/6.13, racy). We reached **Bert's frontier** (the post-laddr `WCD9335 CODEC version is v2.0`).

### CURRENT STATE (folyt.198-199, overnight)
- **6.13 (r14)**: installed, framer works racily (enumerates, with a retry). Device: pmOS slot_b, SSH `sshpass -p $FP3_PW ssh fp3@$FP3_DEV_IP`.
- **6.19.5 (latest, `linux-fp3-619` aport + bert-repro `fp3-619` branch)**: build #1 (plain PAS quirk) RUNNING — reproducing the fix on the newest kernel (the user's request). Build #2 is already coded on the `fp3-619` branch: **reliability fix (NGD)** + **sound card** (`apq8016_sbc.c` SLIMbus backend + SLIM Playback/Capture dai-links → an actual ALSA card).

### OPEN (engineering, NOT a wall)
1. **Reliability** — the NGD timing fix instead of the racy PAS quirk (build #2 validates: the `capability exchange timed-out` + `Failed to get logical address` disappear).
2. **Sound card** — the graft DT had no slim DAI link; now added (SLIMBUS_0_RX→wcd9335 AIF1_PB, SLIMBUS_0_TX→AIF1_CAP) plus SLIM channel-map support in the machine driver. Validation: `/proc/asound/cards` shows "Fairphone 3"; after that, audio-routing + mixer for actual headphone sound.
3. **Bert's efuse stage** comes next; then upstreaming (the NGD fix is generic, DT-property-gated).

### Artefacts
- `bert-repro` (`$FP3_PMOS/bert-repro`): branch `fp3-6.13-quirk` (6.13) + branch `fp3-619` (6.19.5, HEAD = quirk desc + graft + reliability NGD + sound card). **NEVER push.**
- Aport 6.13: `pmaports/device/community/linux-postmarketos-qcom-msm8953` pkgrel=14, patch `0010-FP3-clear-QDSP6SS-0x0c20002c-bit3`.
- Aport 6.19.5: `pmaports/device/testing/linux-fp3-619`.
- The file that recorded the root diff: `report-attachments/DIFF-0xc200000-UT-vs-pmOS.md` (folyt.91).

### ★ PLAYBACK ROUTING + VOLUME — durable operational reference (folyt.208, 2026-07-24)
The ALSA mixer sequence to set by hand for audible sound (card `hw:0,0`; `aplay -D hw:0,0 <file.wav>` bypasses PipeWire and therefore plays at 0 dBFS, so you must attenuate with the codec mixer volume):

- **Headphone (3.5 mm, stereo):** `SLIMBUS_0_RX Audio Mixer MultiMedia1=1`, `SLIM RX0 MUX=AIF1_PB`, `SLIM RX1 MUX=AIF1_PB`, `RX INT1_2 MUX=RX0`, `RX INT2_2 MUX=RX1`, `RX INT1/INT2 DEM MUX=CLSH_DSM_OUT`. Output: `HPHL/HPHR PA`. (The signal runs on the interpolator's SECONDARY/MIX branch: INT1_2/INT2_2 → SEC MIX → MIX2.)
- **Earpiece (mono):** `SLIM RX0 MUX=AIF1_PB`, `RX INT0_2 MUX=RX0`, `RX INT0 DEM MUX=CLSH_DSM_OUT`, `EAR PA Volume`.

- **★ VOLUME (the key — easy to get wrong):** on the headphone path the real loudness control is **`RX1 Mix Digital Volume` (numid 13) + `RX2 Mix Digital Volume` (numid 14)** — because the signal goes through the MIX branch. Scale −84…+40 dB, 1 dB per step (value 84 = 0 dB, 0 = −84 dB). Comfortable: **Mix=48 (~−36 dB)** with a full-scale source. ⚠️ Has NO effect: `RX0/RX1 Digital Volume` (numid 3/4/5, the MAIN branch, unused with this routing) and `HPHL/HPHR Volume` (numid 49/50 — PA gain only, 0…+1.4 dB, 0.07 dB per step). On the earpiece the main branch (INT0) is used → there `RX0 Digital Volume` (numid 3) is the one that applies.
- **Which control is on the active path? Ground truth:** the powered DAPM widgets — the lines reading `: On` under `/sys/kernel/debug/asoc/Fairphone 3/217:1a0:1:0/dapm/*` → they show which INTn/MIX is in the signal path, hence which `RXn (Mix) Digital Volume` matters. (Do not guess from control names.)
- Test script (with the correct numid 13/14): not in `scripts/`; it is `fp3-audio-test.sh` in the project (ear|hp|spk|mic).

### ⚠️ The "Artefacts" block above is partly OUTDATED (folyt.208 correction)
The `bert-repro` "NEVER push" is NO LONGER true: `origin` (upstream) is forbidden, BUT the user's fork (`github.com/llg179/linux`, branch **`fp3-7.0.9-audio`**, HEAD `2c2fd91`) is a valid push target — the 6 audio commits are pushed THERE (over port 443; SSH push on port 22 stalls on the live-USB network). The current aport is `pmaports/device/testing/linux-fp3-709` (pkgrel=3, patches `0001-wcd9335-efuse-sstate.patch` + `0002-fp3-audio-mclk.patch`).

> **THE ENTIRE SECTION BELOW (folyt.183 reframe, §0, addenda) IS HISTORICAL.** The individual MEASUREMENTS remain true, but the "wall / regression-test-is-the-way" FRAME is SUPERSEDED: the root cause is found and fixed. folyt.183 correctly predicted "not a physical wall" — the concrete cause was bit3.

---

## ★★★ folyt.183 REFRAME (2026-07-23) — THE "PHYSICAL WALL / NOT LOCALLY FIXABLE" VERDICT IS OVERTURNED (read THIS before the addendum/§0 below)

**EXTERNAL data (LKML, therefore strong, NOT our own analysis):** on 2025-02-09 Bert Karwatzki, on a **near-mainline**
kernel (`github.com/msm8953-mainline/linux` = OUR repo, FP3), **GOT a logical address for the WCD9335**:
quote "After I get a logical address for the wcd9335 slim device … until `wcd9335_enable_efuse_sensing()`".
`wcd9335_enable_efuse_sensing()` runs ONLY AFTER `slim_get_logical_addr()` SUCCEEDS → **the framer CAN come up
under mainline PAS too.** Source: https://lkml.iu.edu/hypermail/linux/kernel/2502.1/00985.html

⚠️ **The thread got NO reply** (index #00985, confirmed 2026-07-23; neither Srinivas nor Luca responded) →
the Bert thread as community help is a DEAD END, and our own outreach email will very likely go unanswered too.
**Consequence: do not wait for a reply — the right path is the SELF-CONTAINED 6.13 regression reproduction** (see below),
which does not depend on community help; the Bert datum is thus not an open conversation but a FINISHED existence proof.

⇒ **The conclusion of §0 below (folyt.144-157) and of the folyt.158-191 addendum — "the wall is physical PIL↔PAS,
not resolvable locally, only an external BSP/QXDM capture helps" — is TOO STRONG and SUPERSEDED.** A
near-mainline configuration exists in which the framer comes up → our silence is a **regression OR a DT/config difference**,
NOT an unavoidable physical wall. Every INDIVIDUAL measurement in the months-long "every SW layer is identical, yet silent ⇒ physics"
chain remains TRUE (byte-identical framer/clock, identical fw, etc.) — but the GLOBAL conclusion drawn from them
was wrong: identical-on-the-measurable-layer ≠ no-difference (Bert's config differs in something we did not diff
locally — kernel version OR DT/binding).

**What we ruled out AFTER the reframe (all flash-free, folyt.183):**
1. **qcom-ngd-ctrl capability code** = byte-identical to Bert's base (the intervening 7-patch Bjorn race fix only touches
   probe ordering/pm_runtime/SSR cleanup, not the capability path).
2. **mclk2 codec binding** = red herring (old binding; our driver requests mclk+slimbus, both present).
3. **pd-mapper** = WORKS (⚠️ the earlier "missing" claim was OUR OWN GREP ERROR — `grep pdm` instead of `pd-mapper`;
   in reality `qcom_common.pd-mapper.0/.2` is bound, servreg-locator 0x40 registered).
4. **audio_pd PDR path** = dead (`slim_pd_status` never runs, the 0x42 servreg NOTIFIER is missing from the bus),
   BUT probably **ORTHOGONAL** to framing (power_up runs anyway after the QMI power-req; the ADSP frames based on
   the QMI req, not on the AP's PDR bookkeeping) — do NOT chase it as a differentiator.

**Next step (PREPARED, needs supervision):** the 6.13 regression test. The `bert-repro` worktree
(@origin/6.13/main) is ready, our FP3 slim DT is grafted onto it, and the DTB compiles CLEANLY. The FLASH is supervised
(brick safety: raw boot_b + loop image + the config-source discrepancy `SLIM_QCOM_NGD_CTRL=y` in pmaports vs
`=m` on the running machine; the user cannot replug). Bert's exact DT/config would settle regression-vs-DT for good —
not available. Journal: folyt.183. Memory: `project_fp3_audio_codec.md` (updated, old verdict SUPERSEDED).

**Methodological lesson (written into skill feedback):** a conclusion of "physical wall, nothing to be done", reinforced
over months, was overturned by a single EXTERNAL existing-and-working reference. Lesson: before you claim
"not locally fixable", look for an existing working near-identical configuration (an upstream fork, another porter's LKML post) —
one positive existence proof is stronger than any number of your own "every layer is identical" negatives. See
`fp3-porting-debug` "Unavailable is a cost" + "Contributing findings back upstream" (research-if-already-done).

---

## folyt.158–191 ADDENDUM (2026-07-22) — ⚠️ the "every layer is identical" measurements below are TRUE, but the "physical wall" GLOBAL conclusion drawn from them is SUPERSEDED per the folyt.183 reframe above

The INDIVIDUAL measurements of §0 below (folyt.144-157) stand; journal entries folyt.158-191 refuted nothing — BUT the
"all of it reinforces the physical wall" frame is wrong in light of the folyt.183 reframe above (the wall is not unavoidable; Bert came up).
The individual closures:
- **Bootloader closed (folyt.179):** lk2nd (the mainline bootloader) source audit — ZERO LPASS/SLIMbus operations.
- **Full 1 MB SMEM two-sided byte diff (folyt.180):** no framer-config difference at the SMEM level either.
- **Public BSP source diff (folyt.178):** the AP SLIMbus driver is ruled out as a differentiator — the precondition
  is in the PIL/LPASS ADSP bring-up, not in the AP driver.
- **QMI/APR timing (folyt.183-184):** SLIM(0x301) is the FIRST QMI transaction in the boot window; the APR/q6 stack
  comes up fully on pmOS TOO, BEFORE the capability timeout → audio-PD/APR is NOT the missing link.
- **ALSA control graph (folyt.182):** a third independent confirmation — the UT working mixer sequence vs the pmOS
  lack of controls.
- **Exhaustive local sweep (folyt.190):** power/clock/genpd/regulator/interconnect (no anomaly),
  forcing an AFE port from the working q6 stack (blocked by the missing codec, the same wall as a downstream
  consequence), ADSP DIAG F3 capture (the F3 mask goes out, but the DATA channels yield ZERO framer messages —
  the runtime-PM trigger does not elicit the log; per the static RE this would only have confirmed FS=0 anyway,
  NOT the physical cause), hostname/AP identity (ruled out — there is no software-based discrimination).
- **UT-side golden DIAG F3 (folyt.191):** the working framer's SLIMbus messages captured READABLY during playback
  (LA=0xc4, channel setup) — but the bring-up capture (FS 0→1) is CLOSED: there is no userspace SSR trigger
  (`/dev/subsys_adsp` fops are open/release only, no write/ioctl restart), and the boot-armed diag capture
  caused a BOOT HANG (recovery: cross-slot overlay edit, see journal).

⚠️ **A roadmap file from 2026-07-22 (`FP3-audio-status-and-roadmap-2026-07-22.md`, project root) proposes a ULOG cave
experiment to read out the result of the `0xf04d14cc` toggle detector (`r17`/`ctx+0xe54`), allegedly obtainable
"only via ULOG".** This is REDUNDANT: the detector's DECISION (the mode flag `ctx+0x78`) was already captured
live in **folyt.130b** (cave `FMD2`) — result: `mode=ACTIVE` on the dead (pmOS) side too (the good
value; this REFUTES the external-clock-toggle hypothesis). `ctx+0xe54` (the capability-wait object) was likewise
captured live in **folyt.149** (cave `FST1`) — result: `-2` (TIMEOUT), symmetrically on both sides.
**Do not rebuild this cave** — the signal is already in hand, by a more direct method (direct ctx-field reads
rather than log-string decoding). The roadmap file needs updating or archiving; the authoritative
state is HERE and in the journal, up to folyt.191.

**Current frontier UNCHANGED:** solely (B) an external BSP/QXDM electrical capture from a stock boot —
see §0 "FRONTIER" below + the `MEMORY.md` project memory (`project_fp3_audio_codec.md`).

### COMPONENT TABLE (2026-07-22) — moved

The full examined-module component table (32 rows, what matches / what differs) has been moved to:
`FP3-audio-status-and-roadmap-2026-07-22.md` (project root), at the end of section 1 — it lives there
together with the authoritative cross-session status document.

---

## 0. CURRENT STATE — ★ READ THIS FIRST

**The symptom (hard):** FP3 earpiece/mic/headset on the WCD9335 (Tasha) codec, over SLIMbus.
On UT (downstream 4.9, PIL boot) the framer comes up → audio works; on mainline pmOS (PAS boot)
`FRM_STAT=0`, NGD `STATUS=0x40c` → silent. The speaker works (aw8898/MI2S, not SLIMbus).

### Consolidated verdict (folyt.144, LIVE-confirmed folyt.145–154, OFFLINE-exhausted folyt.155–157): EVERY SW LAYER EXHAUSTED; the wall is physical PIL↔PAS, BELOW register/fw-config/AP/codec

Identical fw + identical TZ (same SoC) + identical AP environment → the framer frames under PIL, is dead under PAS.
Every software layer is complete AND identical on both sides; the ONLY fault is that under PAS the framer
**does not physically drive the SLIMbus CLK**, while believing itself "successful". The closed evidence chain:

- **★ The framer AND the whole LPASS clock controller are BYTE-IDENTICAL — a clean live /dev/mem two-sided diff, with no device round-trip
  (folyt.142, `dump_lpass_regions.py`+`diff_lpass_regions.py`):** the LPASS_AP alias (0x0c000000) covers both the framer (0xc140000)
  AND the clock controller (0xc000000) → both slots read from /dev/mem in steady state. The whole LPASS-CC
  (0x14000) is functionally byte-identical UT↔pmOS (PLL L_VAL=0x20, USER_CTL=0x0022830f, RCGR CFG=0x509, CBCR=1); the
  ONLY diff is `0xc001024`=PLL_TEST_CTL_U (benign). ⇒ **C1 clock DEFINITIVELY RULED OUT.**
- **★ There is NO AP-settable framer lever (folyt.143, `frm_causality.py`):** the framer state bits that differ working↔dead
  (+0x804 bit23=running, +0x430 bit4) do NOT latch on an AP /dev/mem write → they are HW/ADSP-owned STATUS (markers), not levers.
- **★ The fw activation RUNS SUCCESSFULLY on the dead side too (folyt.144, coredump):** framer ctx@0xf08884e8 mode +0x78=1
  ACTIVE (on failure the caller would write 0), flags clean, valid handles, HW-desc@0xf0809f30 = AP-phys 0x0c140000 +
  0x0c104000 + the full SLIMbus channel table 0xc0..0xce, NO error flag → the fw is configured, it just does not start framing.
- **★ The codec is READY (folyt.144):** the WCD9335 reset is released at probe (`wcd9335_power_on_reset`); `wcd-mclk` (9.6 MHz)
  en=0 is a CONSEQUENCE (MCLK only in the playback DAPM; the codec's SLIMbus interface runs on the framer CLK, not on MCLK).
- Live deadlock (pmOS dmesg): `QMI power request OK`→`waiting for capability (reconf)`→`capability exchange timed-out
  STATUS=0x40c`→`TX timed out MC:0xd,mt:0x2`→wcd9335 `Failed to get logical address`.

⇒ **Sole locus:** the ADSP fw framing-START trigger / capability handshake (the folyt.118 physical-realisation wall
proven at register level) — NOT fixable at AP/register/fw-config/codec level.

### folyt.145–154 — the sole locus measured LIVE and the framing START reverse-engineered apart (five new angles, all reinforcing the physical wall)

- **★ The framing-START routine LOCALISED: `0xf04d14cc`** (called by the mode update `0xf04c36e8`). Chain: message build (`0xf04d166c`, capability opcode 0xf/0x10 via the callable at ctx+0xe08) → transmit `0xf0174d20` (**a QuRT-INTERNAL IPC queue send** — NOT AP-QMI, NOT direct bus MMIO) → wait `0xf0174eb4` (queue-recv-with-timeout, `r2=#0x1388`=5000 ms) → status dispatch `0xf0175b38`. The capability request is ADSP-INTERNAL (framer manager→bus driver thread); the answer depends on the internal bus transaction completing → no frame, no answer.
- **★ LIVE dead-side TIMEOUT proven (FST1 cave, folyt.149):** the wait's return value = **0xfffffffe (−2 = TIMEOUT)**, ctx+0xeb0=1 (processing did not run). The deadlock is SYMMETRIC: both the AP-NGD AND the ADSP framer time out — now HARD-measured on the firmware side too, not tea leaves. (`build_snapFST1_patch.py` + `smem_snapFST1_read.py` + `fst1_pmos_onboard.sh`; splice AFTER the wait at 0xf04d15bc, SSR reload.)
- **★ The NATURE of the "deadlock" = a TIMEOUT CASCADE, NOT a classic lock-ordering deadlock, and FS=0 is its DOWNSTREAM symptom (not the locus).** Circular dependency: `FS=1 (physical frame)` is needed for the `bus transaction` → which is needed for the `capability answer` → which is needed to `finish bring-up`. On the dead side FS=0 breaks the chain AT ITS ROOT: no frame → the bus driver thread never closes a transaction → never posts an answer → the framer manager's queue-recv (5000 ms) AND the AP-NGD both time out. The word "deadlock" only captures the symmetry (both parties waiting on the same never-completing handshake). ⇒ **the capability timeout is NOT an independent fault and NOT the locus** — it is upstream of FS=0 (folyt.131b: capability subsumed), the first measurable trace of the physical frame start failing to happen. On UT the frame PHYSICALLY starts (FS=1) → the bus transaction closes → the answer arrives in ~2 ms → no timeout, with the same code/message/5000 ms timeout. So "why the deadlock" leads back to the ONE open question: why does the frame not physically start under PAS while every fw-controlled layer is byte-identical (folyt.155-157).
- **★ force-success does NOT frame (FSF1 cave, folyt.150):** forcing `ctx+0xe54=0` (the success branch) → the framer's FS stays 0, NGD CFG=0, no enumeration. A WEAK negative (insufficient data: without a real capability answer the success handlers may return early), but it supports the physical wall.
- **★ framer register HAL + map DECODED (folyt.152):** the HAL is `0xf04bfe34` (is-set), **`0xf04bfe54` (WRITE: `memw(base+table[id])=val`)**, `0xf04bfe90` (read); descriptor tables @`0xf0726400`. **6 register groups**, base offsets {0x200,0x400,0x600,0x800,0x1000,0x2000}, identical layout (+0x00/0x10/0x14/0x18/0x30/0x40/0xf0/0x100). Group2(0x400)=FRM_CFG, Group1(0x600)=the FS status group. ⚠️ **The `+0x600` frame-enable is ALREADY set byte-identically on both sides** → there is no unset SW bit; only a self-clearing trigger pulse remains conceivable (which the dead side never reaches before the capability timeout). The write tracer (FWT1) stalled the SSR (hot HAL hook) → reboot; avoid in that form.
- **★ block2 (0x0c104000 = ADSP 0xee104000) = the SLIMbus BAM/data plane, RULED OUT as a trigger (folyt.153-154):** the HW-desc holds it at +0x1c; `regdump_pmos.py` already identified it as "SLIMbus-BAM v1.7.0". On pmOS it is LIVE (DMA ptr 0x8e2916bc + CFG 0x512 = configured), and it is DOWNSTREAM of framing → not frame generation. The two-sided diff is BLOCKED: the UT stock kernel's /dev/mem is restricted (MMIO=0x40 fill) → UT-side MMIO ONLY via a loadable module (framer_mmio_dump.ko) OR a DEVMEM oracle kernel. Dead dump: `framer-clock-dumps/pmosdm_block2.bin`.

**Frontier (folyt.154):** register-level dead-side analysis is exhausted — EVERYTHING looks configured (a recurring pattern). The only software gap is the framer's HW self-clearing frame-trigger pulse, which the dead side never reaches before the capability timeout; catching/forcing it requires deep RE (the exact location of the frame-start HW write inside the HAL call tree is not yet localised, and the write tracer in hot-HAL form stalls the SSR). Two realistic ways forward, both hard: **(A)** a two-sided diff of the ACTIVE framer register state **via a loadable module** (UT+pmOS with the same .ko, as folyt.143 did for the framer) to catch the self-clearing trigger; **(B)** an external BSP QXDM diag capture (not up to us).

### folyt.155–156 — OFFLINE RE (zero device risk): the register/firmware-software line is EXHAUSTED

- **★ EVERY framer register write enumerated + identical on both sides (folyt.155):** all 4 callers of the write HAL (`0xf04bfe54`) (**FN_A** `0xf04c437c`, the active-config writer: `base+0x210=0xFF000000`/`+0x410=0xb`/`+0x810=3`, gated on sat_hw_owner `ctx+0x74`; **FN_B** `0xf04ca3b0`: `base+0x610=7`) plus the `0xf04bfdf0` RMW enable (bit0 of the group bases) — ALL byte-identical on the dead side (dump cross-check). Offset tables: T0400=group bases {0x200,0x600,0x400,0x800,0x1000,0x2000}, T0440=group+0x10. **T1b timing skeleton:** the framing START (`0xf04d14cc`) has a single data-dependent wait, the 5000 ms capability wait (`0xf0174eb4`, FST1 −2); the FN_ACTIVATE_SEQ busy delay (`0xf0174a74`) is gated on framer_mode==0 → skipped on both master sides. There is no earlier divergent poll.
- **★★ The two-sided word diff of the ENTIRE 176 KB framer aperture (folyt.156): EXACTLY 10 differing words, ALL markers/downstream:** framer STATUS markers {0x204,0x404,0x430,0x604,0x804} (the HW-written output; 0x430/0x804 proven non-latching in folyt.143) + downstream NGD {0x1000,0x1004,0x1008,0x1010,0x1014}. **Not a single differing config/input register.** Other write primitives too (`0xf04bfd90` base+0x3000, `0xf04c0248` base+0x400) are all on the framer base → **C3 (a separate fw-written PHY/pad block) CLOSED: there is no third block** (the HW-desc maps only framer+BAM, both exhausted).
- **⇒ SUMMARY:** every fw-controlled layer is byte-identical on both sides (config + full aperture + every write + clock + BAM + mode + fw activation). The only difference is the framer's STATUS output (FS=0 vs 1) plus downstream. **The ONE remaining SW-testable question:** does a self-clearing trigger PULSE fire on the dead side (a resting diff cannot see it) — ONLY the (A) live two-sided loadable-module capture can decide. Realistically this too would reinforce the physical wall; the weight of (B) an external BSP QXDM diag grows (the PIL↔PAS difference is BELOW the fw registers). Journal: `FP3-slim-debug-journal.md` folyt.155-156.

**Closed disproof (folyt.145):** forcing wcd-mclk ON = a no-op (codec SLIMbus enumeration requires the framer CLK, not MCLK; on UT the codec enumerated WHILE audio_ext_lpass_mclk enable=0). Do NOT build on it.

### What is RULED OUT (physical fact — do not re-run)

| topic | verdict |
|---|---|
| firmware | NOT the difference — the pmOS fw FRAMES on UT/PIL (decisive swap) |
| AP proxy resources + power | equivalent — cx@INT_MAX + xo held THROUGHOUT → framer dead |
| QMI 301 handshake | = downstream (SELECT_INSTANCE MASTER + POWER_REQ, acked, ver=0x105) |
| QMI payload / SELECT_INSTANCE "3rd TLV" | EXONERATED — the 14 B TLV is byte-identical to mainline, "not the lever" |
| NGD setup / NGD_CFG | = downstream (the ENABLE\|RX\|TX write is there; CFG=0 is a symptom, not a cause) |
| QDSP6SS AP poke | not an AP surface on msm8953 (ADSP = pure TZ-PAS) |
| AP RPM vote / bb_clk1 / cx-corner | ruled out (no AP-visible LPASS clock; PAS INT_MAX ≥ PIL TURBO) |
| SMMU / pinmux / reset / interconnect | no delta (structural) |
| TZ SCM metadata (auth) | equivalent — the PAS auth SUCCEEDS; the divergence is AFTER a successful auth |
| boot order / timing | ruled out — a fresh PAS auth after every other subsystem, framer still dead |
| global-state inheritance | ruled out — warm reboot UT→pmOS without power-off (RPM/PMIC preserved), framer dead |
| TZ runtime | no error/fault/xpu; the TZ ring does not log the ADSP framer (invisible) |
| the last AP bw vote (icc crypto→EBI) | UINT_MAX voted under PAS → framer still dead |
| config-group software dispatch | IDENTICAL working↔dead (pointer graph byte-identical) |
| framer-branch clock enable | IDENTICAL working↔dead (CKB7b/B) |
| framer-branch clock RUNNING (CLK_OFF) | IDENTICAL — CLK_OFF=0 on both sides (CKB8); the clock RUNS on the dead side too |
| framer clock RATE/SOURCE (RCGR CFG/M/N/D) | IDENTICAL `0x00000509` (src=5, /5, MND off) working↔dead (CKB9) → **the whole clock trunk ruled out** |
| framer MODE (active vs external) | the dead side is **ACTIVE** (`memw(ctx+0x78)=1`, FMD2 folyt.130b) → the ADSP is the framer master, it is NOT waiting on external; external-switch REFUTED |
| the whole LPASS clock controller (0x14000) | **BYTE-IDENTICAL** UT↔pmOS from live /dev/mem (folyt.142); the only diff 0xc001024=PLL_TEST_CTL_U is benign → C1 clock ruled out for good, with no device round-trip |
| framer state bits as an AP lever (+0x804 bit23, +0x430 bit4) | an AP /dev/mem write does NOT latch (folyt.143) → HW/ADSP-owned marker, not a settable lever |
| fw framer activation (0xf04d14cc) | RUNS SUCCESSFULLY on the dead side too (coredump folyt.144): mode ACTIVE, valid handles, HW-desc + channel table, no error flag → the fw is ready, it just does not start framing |
| WCD9335 codec readiness | reset released at probe (folyt.144); wcd-mclk en=0 is only a CONSEQUENCE (MCLK = playback DAPM, not the SLIMbus interface's clock) |
| the ENTIRE framer aperture (176 KB) | **two-sided word diff = EXACTLY 10 differing words, ALL markers/downstream** (folyt.156); no differing config/input register ANYWHERE |
| every framer register WRITE | enumerated (4 write-HAL callers + RMW + inline) — ALL byte-identical values on the dead side (folyt.155-156) |
| block2 / SLIMbus-BAM (0xee104000) | data plane/DMA, DOWNSTREAM of framing (LIVE and configured on pmOS) → not the frame trigger (folyt.153-154) |
| C3 — a separate fw-written PHY/pad block | **DOES NOT EXIST:** the fw HW-desc maps only framer+BAM (folyt.156); the `slim_msm`/framer DT node has no power supply in either tree → there is no AP-controlled framer PHY supply (folyt.157) |
| codec buck-rail DT diff (eldo2 vs l5) | a real diff, BUT codec-side (the SIDO buck is for the codec's answer), BELOW the framer FS (FS is upstream, 131b) → unlikely to be the cause of FS=0 (folyt.157) |

### DEAD LEADS (do not chase — proven dead ends)

| lead | why it is dead |
|---|---|
| ACDB as the framer trigger | REFUTED — golden trace: framer t=22.262, ACDB traffic only from t=25+ → ACDB is post-framer |
| q6afe / APR branch | exhausted — the AFE clock branch is dead (0/54 SLIMbus clock IDs in the Q6AFE enum); the AFE port is refuted; AFE config(SLAVE) is post-framer port config |
| q6_core_clk clock failure (F3) | red herring — `q6_core_clk` is not registered, wrong domain (voice), independent of boot path |
| `0xee00d01c` as the framer-branch CBCR | a misidentified clock (the real branch is `0xee012014`); force-write → deterministic NO-BOOT |
| `0xf019abb0` / HWL4 static CGC leaf | deprecated as a capture site (early-phase write, magic ABSENT) |
| CBCR bit force / brute force | deterministic NO-BOOT — the branch requires the proper enable sequence, it cannot be forced |

### FRONTIER (folyt.157) — the register/firmware-SOFTWARE line is EXHAUSTED; what remains is (B) external + the physical wall

**EVERY earlier candidate is CLOSED** (details in the RULED OUT table above + the journal):
- **(C1) framer clock** — CLOSED (128d enable/running/rate + 142 the whole LPASS-CC byte-identical from live /dev/mem). Do NOT re-measure.
- **(C2) framer config/PAGE** — CLOSED (133 every config register identical; 134 whole page shows only markers; **156 the ENTIRE 176 KB
  aperture = 10 differing words, all markers/downstream**). Do NOT re-measure.
- **(C0) capability handshake** — subsumed (131b: FS=0 → it never frames → the exchange never even starts). Not the locus.
- **(C3) LPASS PHY/pad** — CLOSED (156: the fw HW-desc maps only framer+BAM, there is no third block; 157: the framer
  DT node has no power supply in either tree → there is no AP-controlled framer PHY supply). Not the locus.
- **block2/BAM (0xee104000)** — data plane downstream, not a trigger (153-154).

⇒ **There is no static register/SW lever left.** Everything controlled by the fw AND the AP DT is byte-identical; the only difference is the framer's
STATUS output (FS=0 vs 1) plus downstream. The wall is **physical/environmental PIL↔PAS**, BELOW the fw registers AND the AP config.

**The ONE remaining SW-testable question (156):** does a self-clearing trigger PULSE fire on the dead side (a resting diff cannot
see it). BUT `framer_mmio_dump.c` takes a resting snapshot (it will not catch a pulse), and the fw write tracer stalls the SSR (152) → the realistic
yield of the (A) live two-sided loadable module is CONFIRMATION, not a lever.

**Frontier ranking:**
1. **★ (B) external BSP QXDM diag capture** — the highest value; the PIL↔PAS difference is in the co-processor-internal bus transaction,
   which only a BSP diag can see. Externally dependent (forum/Fairphone ticket/pmOS channel) — **check its status, do not write it off.**
2. **(A) for live confirmation only** — see above; a resting-only module will not find a lever. Do not make it the first move.

**Durable method reminders (for any future dead-side measurement — not candidate-specific):**
- Both-sides anchor: the mode-update entry `0xf04c36e8`; absolute framer base `0xee140000` → no ctx dependency.
- Cave anchor: an unconditional **fn-ENTRY splice** (not a transition-gated log — see FMD1's failure); OMIT the stash-zeroing `m.flush()`
  (it returns EINVAL on /dev/mem). For a transient return/wait value → splice INSIDE the fn (the FST1 pattern).
- **★ Write the readout DIRECTLY to a synced file (`py > f; sync`), NOT through a `{ } | tee` pipe** (a mid-run reboot loses the late output).
- **★ Ensure disk headroom BEFORE a dead-side fw experiment** (journal vacuum → 270M+; at 210M the measurement campaign itself causes a disk-full loop).
  A persistent USB link wedge → ~~physical replug~~ device-side UDC re-bind (host-side reset still
  FORBIDDEN, and measured to be useless: it never drops VBUS — [Unattended access](../../../../../../README.md#unattended-access-no-on-device-login-no-usb-replug)). **Cross-slot fix for a reboot loop:** from UT,
  `losetup -fP /dev/mmcblk0p31` (=pmOS system_b, DOS PT) → `e2fsck -fy loopXp2` → mount → repair.
- Offline: the full disasm cache `scratchpad/tier1/seg2_full.dis` (llvm-objdump hexagon, seg2.elf @0xf015f000); two-sided dumps
  `framer-clock-dumps/{utdm_framer,pmosdm_framer}.bin` (176 KB, real); coredump `adsp-coredump.elf` + `coredump_resolve.py`.
- Older artefacts (historical): `build_snap{FRS*,FST1,FSF1,FMD*,CKB*}_patch.py` + `smem_*_read.py` + `*_onboard.sh`.

### Current device state (re-verify every session)

- Healthy baseline: slot_b/pmOS, STOCK ADSP fw (md5 `3ed6924d`), remoteproc2=running,
  framer DEAD baseline (`STATUS=0x40c`). `set_active b` → pmOS.
- The bw-vote kernel in the `linux-fp3` tree (DT `scm` crypto→EBI); the patch is STAGED (uncommitted — see §8).
- A journal cap is configured (`/etc/systemd/journald.conf.d/cap.conf`, `SystemMaxUse=40M`) against the disk-full reboot loop.
- ☠️ Guardrail: before a cold-boot deploy, journal-vacuum + a `df -h /` gate (the 2.4 G loop rootfs is tight).

## 1. THE GOAL

Working earpiece / in-call / microphone audio on the Fairphone 3 under **native mainline
postmarketOS** (7.0.x-msm8953, phosh), as a long-term EOL-proof direction. Currently SILENT;
only the speaker (MI2S/aw8898) works.

## 2. THE SYMPTOM (the end-to-end failure chain, from dmesg)

```
ADSP boot OK → NGD power_up QMI OK → capability exchange TIMEOUT (NGD STATUS=0x40c)
→ wcd9335-slim "Failed to get logical address" (TX timeout MC:0xd) → codec deferred → no sound card
```

**The HARD register fact (SLIMbus core base `0x0c140000`, `/dev/mem`, both slots):**
the decisive differential is the framer's `FRM_STAT` (`0x0c140404`): UT/PIL `0x060D1901` → pmOS/PAS **`0x00000000`**,
i.e. the framer is configured (`FRM_CFG` identical) but not "alive". The full framer+NGD register table:
**§7.1**.

☠️ Measurement nuance: when idle the block runtime-suspends → every word reads a constant `0x40`/`0x50` (NOT 0, NOT a hang)
— so read it forced-active (`power/control=on`) or during a fresh boot. (Ruled-out "why" leads:
reset/pinmux/power/codec/interconnect — in the "ALREADY RULED OUT" table of `data-index.md`.)

## 3. THE SUBSTRATE (device — re-verify every session, the names shift)

- **SoC** MSM8953 / Snapdragon 632, Adreno 506, aarch64. **Codec WCD9335 (Tasha)** on SLIMbus
  (earpiece/mic/headset are SLIMbus-only; the speaker is aw8898 on MI2S). PMIC PMI632.
- **A/B slots everywhere** — oracle slot_a, test slot_b, `fastboot set_active a|b`,
  zero-risk rollback. `set_active` also clears the retry/unbootable state.
- Boot chain: XBL → ABL → **lk2nd** (flashed into boot; provides fastboot and boots the kernel).
- **secure-boot is OFF** → `adsp.mbn` (an unencrypted ELF32 QDSP6/Hexagon image) can be re-signed and patched
  with `qtestsign -v3` (proven).
- **Access:**
  - pmOS (SUT): SSH `fp3@$FP3_DEV_IP`, password `$FP3_PW`. Device sudo asks for a tty →
    `echo $FP3_PW | sudo -S <cmd>`. The link is stabilised (§5): `fp3-ssh 'cmd'`, iface `fp3`,
    host IP `$FP3_HOST_IP/16`. ☠️ Push scripts across as base64 (`fp3-ssh "echo <b64>|base64 -d>/tmp/x.py && echo $FP3_PW|sudo -S python3 /tmp/x.py"`) — `cat|ssh 'cat>f && sudo -S'` swallows stdin before the sudo password.
  - UT (oracle): `adb -s $FP3_SERIAL`, root via `sudo` + PIN `$FP3_PW`. **NEVER `sudo adb`**.
    ✅ FIXED (folyt.91): the login (lockscreen PIN) and the USB replug are **not needed** — adb comes up by itself
    ~90 s after boot, even on a LOCKED greeter (`ro.adb.secure=0` + the host key persisted in
    `/data/misc/adb/adb_keys`). The old "login+replug required" was a first-time-setup artefact. → user presence
    is NOT required for the oracle. (After a reflash, check `ro.adb.secure`.) The sudo prompt eats stdout:
    `echo $FP3_PW|sudo -S sh -c '…' 2>/dev/null` (not `grep -v '^\[sudo\]'`).

## 4. THE ROLE OF THE THREE OSes (the basis of the differential method)

- **Ubuntu Touch / Halium = the ORACLE** (reference). Downstream 4.9.x, EVERYTHING works. It boots the ADSP via the
  PIL/TZ path → the framer comes up. No CONFIG_DEVMEM by default; a custom DEVMEM kernel EXISTS for live register reads
  (memory `project_ut_devmem_kernel`) — BUT the STOCK UT kernel already has `/dev/mem`
  (folyt.86), readable without flashing. **★ The POSITIVE case is measurable here** (folyt.99: the pmOS fw frames on UT).
- **postmarketOS mainline = the SUT.** PAS (`qcom_q6v5_pas`). Working: display/touch/GPU/WiFi/modem/
  charger/speaker. The wall: SLIMbus audio. **Build:** `pmb build --src <linux-fp3>` is REQUIRED
  (the `_pYYYYMMDDHHMMSS` suffix means a correct build). Flash order: dtbo→lk2nd→vbmeta→rootfs→reboot.
  (`CONFIG_QCOM_Q6V5_PAS=m` → the PAS driver `.ko` is hot-swappable without flashing; folyt.103.)
- **Sailfish (hybris)** = the third port; provenance in `sailfish-components.md`. It does not touch the audio wall.

## 5. THE HOST↔DEVICE LINK — STABILISED (folyt.75, zero device risk)

pmOS `usb-moded` (`ncm.usb0`, `18d1:d001`) picks a random MAC every boot → the host-side fix:
- `/etc/systemd/network/10-fp3.link`: `[Match] Driver=cdc_ncm` → `Name=fp3`, `MACAddressPolicy=none`.
- NM profile `fp3`: ifname=fp3, static `$FP3_HOST_IP/16`, autoconnect.
- `scripts/{fp3-link.sh,fp3-ssh.sh}` (→/usr/local/bin). **They NEVER touch the USB layer.**
- ☠️ After a MAC change, stale ARP → `sudo ip neigh flush dev fp3; sudo ip addr replace $FP3_HOST_IP/16 dev fp3`.
- ☠️ NCM jam (`NETDEV WATCHDOG: transmit queue timed out`) → poll PASSIVELY, it recovers on its own
  (minutes). To catch the device after a reboot: a background SSH hammer (see `scratchpad/catch_fp3.sh`).
- The device rootfs is TIGHT (2.4 G loop, ~95 %, ~117 M free at folyt.77); check `df -h /` before a firmware deploy.

## 6. TECHNIQUES / METHODS (the durable "how")

- **Dual-slot A/B is the engine of measurement.** `set_active` is also the reset.
- **The golden A/B diff is the central move.** Measure the same layer on both sides.
  **★ But: pin down the POSITIVE side too, do not only exonerate the negative.**
- **HARD vs SOFT evidence (the folyt.77 lesson):** a register-level differential is hard;
  an idle snapshot / a source-code judgement / a single-slot stash is soft, NOT a closure. A negative must be
  proven at the RIGHT timing and in the RIGHT layer.
- **Register truth > logs.** `/dev/mem` mmap from Python (`dd`/`devmem` can return 0 on a hardened kernel).
- **☠️ NEVER scan a whole register block blindly** (folyt.77: a full 0x80000 GCC scan → bus hang →
  watchdog reboot). Only concrete offsets verified from a driver (`gcc-msm8953.c`), or `clk_summary`
  (debugfs, safe). A bus hang CANNOT be interrupted by a timeout.
- **SSR reload = a ~2 s fw iteration, BUT the framer clock is boot-time ONE-SHOT** → a cold-boot deploy is required.
- **Firmware RE:** offline disassembly (seg2.elf) → a decision point; cave + entry trace + SMEM exfil.
- **Without an ADSP debug port:** the SMEM_LOG ring / an injected SMEM tracer / devcoredump / a 900e ramdump.
- **"Unavailable" is a cost, not a verdict:** name the change and its magnitude, then rank.
- **One change per run + never block the boot + a DBG breadcrumb.**

## 7. FULL ADDRESS MAP (per component, searchable — firmware: ADSP.VT.3.0-00161-00000-1)

> **Searchability:** for offset-based entries the `base + offset = full address` form is always
> given, so the complete MMIO/VA address is greppable verbatim.
> **Framer parameters:** gear = `0xA` (10), root rclk = 24.576 MHz,
> clock source = `HAL_CLK_SOURCE_LPAPLL1` (LPASS Audio PLL → 24.576 MHz).
> **VA→file-offset conversion:** `FOFF = VA − 0xf00fd000` (durable mbn; e.g. `0xf04df244` → `0x3e2244`).

### 7.1 AP — SLIMbus core registers (base `0x0c140000`, `/dev/mem`)

This is the HARD differential (see §2). ☠️ When idle the block runtime-suspends → every word reads `0x40`/`0x50` (NOT 0) — read it forced-active or during a fresh boot.

| base + offset | full address | reg | UT / PIL (works) | pmOS / PAS (dead) |
|---|---|---|---|---|
| `0x0c140000` + `0x400` | `0x0c140400` | framer `FRM_CFG` | `0x000D0C83` | `0x000D0C83` (identical config) |
| `0x0c140000` + `0x404` | `0x0c140404` | framer `FRM_STAT` | `0x060D1901` | **`0x00000000`** (not alive) |
| `0x0c140000` + `0x1000` | `0x0c141000` | NGD `CFG` | `0x00000007` | `0x00000000` |
| `0x0c140000` + `0x1004` | `0x0c141004` | NGD `STATUS` | `0x000D040E` | `0x0000040C` |
| `0x0c140000` + `0x1014` | `0x0c141014` | NGD `INT_EN/STAT` | `0xBE000000` | `0x00000000` |

### 7.2 ADSP — clock MMIO (RCGR/CBCR, runtime-mapped; NOT readable from the AP, only via an ADSP cave)

The framer clock is `audio_core_slimbus_core_clk`, clock-id `0x12014`, RCGR domain `0x12000` → runtime map base `0xee012000`.
The framer-branch enable is **BYTE-IDENTICAL UT↔dead** (both ENABLED, caller `0xf01d41ec`, value `0x1`) → the wall is PHYSICAL (the parent RCG root / source PLL does not supply under PAS), NOT software dispatch.

| base + offset | full address | reg | value / verdict |
|---|---|---|---|
| `0xee012000` + `0x0` | `0xee012000` | RCGR root (`CMD_RCGR`) | `0x80000000` — ROOT_OFF=1, ROOT_EN(bit1)=0; UT↔dead IDENTICAL |
| `0xee012000` + `0x4` | `0xee012004` | RCGR `CFG_RCGR` | `0x00000509` — src=5, div=9; UT↔dead IDENTICAL (sets rate only) |
| `0xee012000` + `0x14` | `0xee012014` | **framer BRANCH CBCR** ✅ | the CORRECT framer branch (clock-id `0x12014`→+0x14); enable BYTE-IDENTICAL UT↔dead |
| `0xee012000` + `0x18` | `0xee012018` | framer branch (2nd one enabled) | enable BYTE-IDENTICAL UT↔dead |
| `0xee032000` | `0xee032000` | sibling ibit (domain `0x32000`) | deterministic map pattern |
| `0xee026004` | `0xee026004` | CBCR in the `ibit_clk` pattern | handle+0x1c example |
| `0xee000000` + `0xd01c` | `0xee00d01c` | ☠️ MISIDENTIFIED clock | CKB3 handle+0x1c; a DIFFERENT clock, NOT the framer branch (CKB6 force → no-boot) |

Standard RCGR write offsets (from the RCGR base): `+0x8`=M, `+0xc`=~(N−M), `+0x10`=~N, `+0x4`=CFG set bit #13, `+0x0`=CMD\|=bit0 (+ poll CMD bit0).

### 7.3 ADSP fw — static call chain (VA, code/rodata, boot-stable)

| VA | role |
|---|---|
| `f04d0628` | log fn — *"Turning on satellite/standalone slimbus ref clock"* |
| `f04ce37c` | slim/framer bring-up (single caller) |
| `f04bf8c0` | handle acquisition — GetProperty(devcfg)+DAL clock-get → ctx+0xe18/+0xe14 |
| `f04bfb68` | clock primitive (outer); calls `f04bfaa0` then `f0191c68` |
| `f04bfba0` | `r17=r0` = the rc of `f0191c68` (SMEM cave splice site; stock `11406070`) |
| `f04bfaa0` | DAL clock work; `call f019f134(r0=handle, r1=#6 enable)` |
| `f0191c68` | config-group processor (gate `memw(0xf0913658)`; jump table `0xf0663a5c`) |
| `f019f134` | DAL clock op = vtable dispatcher → `callr memw(handle+0x48)` |
| `f019eb40` | physical-clock-op entry = state machine (handle+0x38, handle+0x44 bit0) |
| `f01a12bc` | NPA op layer (subobj=`memw(handle+0x10)`); the 2nd callr = apply (the runtime-dispatched leaf, folyt.97) |
| `f01a09bc` / `f01a0d0c` | HAL methods — rate aggregator / NPA bookkeeping (ZERO MMIO) |
| `f01d6994` | apply_fn (folyt.74; NPA aggregation, ZERO MMIO) |

The `f04bfb68` clock primitive also calls the config-group processor (`f0191c68`) → the leaf is `HalHwIo_EnableClock`/`halHwIo_EnableCgcClock` (CGC; `hal_hwio_clkctrl.c`). The register base is mapped AT RUNTIME (`HalHwIo_Init`) → there is no MMIO constant in the static image.

### 7.4 ADSP fw — clock registry + CBCR primitives (VA)

The framer clock is REGISTERED in the static LPASS AudioClockManager name→{id,ops,hw-desc} table; the name→ID resolution SUCCEEDS → the wall is at the physical ENABLE, not at the lookup.

| VA | role |
|---|---|
| `f0821de8` | registry entry (`audio_core_slimbus_core_clk`); `+0x04`=clock ID `0x12014`, `+0x3c`=`0xd01c` (CBCR offset field) |
| `f0821960` | ops vtable (enable method `f04df244`, 2nd method `f04df31c`) |
| `f0889538` | HW descriptor → sub-descriptor chain `f04df0ac…f04df51c` (CBCR/PLL offsets) |
| `f04df244` | RCGR rate update; `r17=memw(handle+#0)` = the RCGR/CBCR MMIO base (a data field, NOT an immediate) |
| `f04df0ac` | CBCR **SET** primitive (`memw(memw(desc+12))\|=memw(desc+16)`) |
| `f04df0c8` | CBCR SET store — the two SET paths merge here (the correct splice point) |
| `f04df0d4` | CBCR **CLEAR** primitive |
| `f04df100` | CBCR **TEST** (status poll) |
| `f04df0b4` | ☠️ CKB4/5 splice — only ONE of the enable branches → false negative |
| `f04df260` | snapCKB splice (r0=handle, r17=base) |
| `f04df2e4` | snapCKB2 poll-read splice |
| `f019abb0` | ☠️ static CGC leaf (`halHwIo_EnableCgcClock` return) — DEPRECATED as a capture site (magic ABSENT, early-phase write) |

### 7.5 ADSP fw — .bss / rodata / config-group live dispatch (VA)

| VA | role |
|---|---|
| `f0913658` | config-group GATE (`.bss`) — =0 on BOTH sides → NOT a differential |
| `f0c85450` / `f0c85440` | config-group cfg (`.bss`) — ☠️ TRANSIENT scratch, a post-return splice reads stale data |
| `f09141e0` | HW descriptor table (`.bss`) |
| `f0663a5c` | jump table (config-group processor) |
| `f066a688` | HAL vtable (RODATA) |
| `f0678aea` | rodata string — `"audio_core_slimbus_core_clk"` |
| `f067915f` | rodata string — `"audio_core_slimbus_lfabif_clk"` |

Config-group live dispatch (folyt.114–118): handle = `memw(ctx+0xe18)`; `memw(handle+0x48)` = the `0xf019eb40` resolver thunk; driver node = `memw(memw(handle+0x3c)+0)`. The `f04bfba0` splice cave magic is `'CGP1'`. The pointer graph (handle +0x38/+0x3c(NULL)/+0x40/+0x44/+0x48) is BYTE-IDENTICAL working↔dead.

### 7.6 Runtime structures (vary per boot — one captured example; the offsets are stable)

**ctx (`=r16`):**

| offset | value / role |
|---|---|
| `+0x74` | sat_hw_owner = 1 |
| `+0x78` | framer_mode |
| `+0xe14` | group id (an invocation artefact, NOT a lead — folyt.94) |
| `+0xe18` | core-clk handle = `0xf0ab3998` |

**core-clk object (`0xf0ab3998`):**

| offset | value / role |
|---|---|
| `+0x08` | → `"slimbus"` |
| `+0x0c` | → `"/pmic/client/rail_cx"` |
| `+0x48` | = `0xf019eb40` (physical-clock-op entry) |

**NPA subobj (`= memw(handle+0x10)`):**

| offset | value / role |
|---|---|
| `+0x04` | runtime driver node (the physical poke dispatches here, folyt.97) |
| `+0x14` | = `0xf066a688` (HAL vtable RODATA) |
| `+0x2c` | agg rate = 3 |
| `+0x54` | gear = 8 |

**snapCKB runtime handle layout (`f04df260` splice):**

| offset | value / role |
|---|---|
| `+0x00` | RCGR MMIO base (`0xee012000`) |
| `+0x04` | registry-entry ptr (`0xf0821de8`) |
| `+0x0c` | ops vtable (`0xf0821960`) |
| `+0x1c` | 2nd MMIO ptr / CBCR (`0xee026004` in the ibit pattern) |

### 7.7 SMEM exfil + cave addresses

☠️ Cave rules (folyt.94): NEVER do a cave MMIO read (a posted write ≠ a safe read); the SMEM stash is ≤ ~`0x50B`; "magic absent" ≠ "the leaf did not run" (a UT positive control is required).

| base + offset | full address | role |
|---|---|---|
| `0x86300000` | `0x86300000` | SMEM base (PA) |
| `0x86300000` + `0x2ab0` | `0x86302ab0` | item 469 slot#12 stash (PA) = ADSP VA `0xe1302ab0` (offset `0x5b000000`) |
| `0xe1302ab0` | `0xe1302ab0` | the stash's ADSP VA (`0x86302ab0` + `0x5b000000`) |
| `0xf064e098` | `0xf064e098` | cave VA = file offset `0x551098` |
| `0xf04bfba0` | `0xf04bfba0` | splice VA = file offset `0x3c2ba0` |
| `0xf00fd000` | `0xf00fd000` | the VA→FOFF conversion base (durable mbn) |
| `0x8d600000`…`0x8e6…` | carveout | ☠️ NEVER mmap live → XPU wedge |

### 7.8 Message layer — AFE ports + diag SSIDs + QMI

**Diag SSID:**

| SSID | role |
|---|---|
| `ss=8500` | the ADSP audio + SLIMbus-master diag SSID (READABLE `0x79` EXT, NOT hashed: `SlimBus.c`/`SlimBusMaster.c`/`AFESlimbusDriver.cpp`/`AudDevMgr.cpp`/`clock_manager.cpp`) |
| `ss=53` | ☠️ SENSORS (NOT slim) |

**Golden UT slim AFE paths** (needed AFTER the framer comes up; the slim paths do NOT do per-stream clock enabling → the framer clock is boot-time ONE-SHOT):

| function | AFE port | topology | note |
|---|---|---|---|
| earpiece | `0x4000` | `0x10313` | SLIMBUS_0_RX mono |
| headset | `0x400c` | `0x20314` | stereo HPH |
| speaker | — | — | MI2S/aw8898 (NOT slim) |

**AFE param / QMI:**

| identifier | role |
|---|---|
| `AFE_PARAM_ID_CDC_SLIMBUS_SLAVE_CFG` = `0x00010235` | the `afe_set_config(AFE_SLIMBUS_SLAVE_CONFIG)` param; post-framer port config, NOT a framer trigger |
| SvcId `0x301` | the slim QMI service (SELECT_INSTANCE+POWER_REQ) |
| QRTR node5 | ADSP |

**UT diag** = the classic `/dev/diag` diagchar (`ut_diag_f3.py`: ioctl SWITCH_LOGGING(7)→MEMORY_DEVICE_MODE, write `0x20`+HDLC). Mainline: the auto-bound ADSP DIAG channels under `/dev/rpmsg*` + `scripts/diagtap.py`/`diagcap.py` (feature+F3 mask to the CNTL node → the ADSP F3 stream).

## 8. GUARDRAILS (MANDATORY — the daily phone is a SEPARATE FP3)

- **AP `/dev/mem` reads ONLY:** the safe SMEM range `0x86300000–0x86500000` (2 MB), AND
  non-gated register blocks (GCC/NGD) **at a concrete offset**. ☠️ **NEVER a whole-block scan**
  (folyt.77: a 0x80000 full GCC scan → NoC hang → watchdog reboot). ☠️ **NEVER** a gated LPASS/SLIMbus
  register while idle (→900e). ☠️ **NEVER** mmap the carveout (`0x8d6–0x8e6`) live (XPU→wedge).
- **NEVER emit firmware diag** (wedge→boot loop, proven twice). Only pure load/store or a coredump.
- **For a crashing fw, `recovery=disabled` is MANDATORY** before flashing; NEVER cold-boot a crashing fw unattended.
- ☠️☠️ **NEVER restart the USB/link from the host** (remove/authorized toggle/USBDEVFS_RESET/unbind-rebind, `ip link down/up`, `nmcli` cycling). It does not fix the device-side NCM/gadget jam ("non-enumerating" for ~15 min), **AND `/mnt/1TB` is a USB-attached disk — a host USB reset can unmount `/mnt` mid-run** (2026-07-11: this happened, the working tree was lost). Recovery = passive polling or a DEVICE reboot. (The `fp3-link reset` verb was deleted for this reason.)
- **NEVER `sudo adb`.** `sudo fastboot` is fine.
- **The 10-minute Bash cap** kills `pmb install`/flash → run detached + poll. `pmb build` fits in the foreground.
- **Kernel-tree commits are LOCAL** (origin=upstream), NEVER push. *(folyt.208 nuance: `origin` is still forbidden, but the user's own fork `github.com/llg179/linux` branch `fp3-7.0.9-audio` IS a valid push target — see the folyt.208 correction in §"Artefacts".)*
- **Flashing is user-approved**; one change per run; reset the retry count between runs.
- **Recovery from a boot loop:** power off (Power ~10 s) → Power+VolDown → lk2nd fastboot (18d1:d00d) →
  `fastboot set_active a && reboot` (UT) → from UT, fsck the pmOS rootfs (losetup -P p31 → `e2fsck -fy`)
  → `set_active b && reboot`. **But: in folyt.77 the watchdog reboot recovered BY ITSELF** (journald gracefully
  released the dirty loop rootfs) — wait passively first, do not jump to physical recovery.
- **Flash-vehicle lessons (folyt.112–113):** `pmb flasher` can fail on the chroot's `android-tools` (exit 7) → the OLD kernel
  boots (☠️ after flashing, ALWAYS verify the `uname -v` build date BEFORE measuring). A host fastboot bulk flash → **a D-state stall**
  (~0 CPU, blocked immediately) → a fresh enumeration (user power-cycle) + `fastboot -S 256M` sparse flash resolves it (8/8 chunks). ☠️ Avoid `getvar
  max-download-size` (it worsens the wedge); a hung fastboot pipe is ONLY cleared by a physical power cycle.

## 9. TOOLING / FILE MAP

- **File index (searchable, "what have we already examined"):** `data-index.md` (in the root).
- **Kernel trees:** `$FP3_PMOS/{linux-fp3 (mainline/PAS), ubports-fp3-kernel (downstream/PIL/oracle)}`.
- **Cave/fw pipeline:** `scripts/m2/` + `scripts/build_snap*_patch.py` + `deploy_snap*.sh`
  + `smem_snap*_read.py`. Signed images: `scripts/m2/adsp-*-signed.mbn`.
- **Diag/measurement:** `scripts/{diagtap.py,diagcap.py,parse_f3.py,adsp-smem-log.py,regdump_pmos.py,
  qrtr_lookup.py,ut-capture-framer.sh,gcc_snapshot.py (☠️ full scan, do not use),catch_fp3.sh}`.
  Out-of-tree AFE test: `$FP3_PMOS/q6pll/q6pll_test.ko`. Live clk_summary: `scratchpad/clk_summary_pmos.txt`.
- **Link:** `scripts/{fp3-link.sh,fp3-ssh.sh}` (§5).
- **Stock fw:** `scripts/m2/adsp.mbn` (md5 3ed6924d = pmOS) + the device `.stockbak`. The UT stock adsp.mdt is `bab175ed`.
- **Journals/docs (the detailed history, see `data-index.md` in the project):** `slimbus-audio-tracker.md` (live tracker);
  `FP3-slim-debug-journal.md` (the full journal). The dated result files are listed by `data-index.md`.
  HW basics: `hw-facts.md` (this directory); the Sailfish port (a SEPARATE track, not audio): `sailfish-components.md`+`sailfish-customizations.md`+`sailfish-akcioterv.md`.
  **★ `pmos-bringup.md` §9.15–9.30** = the genesis of the audio investigation + **§9.17 the FULL golden call UCM/mixer recipe**
  (earpiece=SLIMBUS_0_RX→RX INT0 EAR PA; headset=SLIMBUS_6_RX→HPHL/R; mic=SLIMBUS_0_TX←DMIC) — THIS is what you need once the framer comes up.
  **Memory:** `~/.claude/projects/-mnt-1TB-Fp3-Sailfish/memory/` (`project_fp3_audio_codec.md`).

## 10. SCRIPT INDEX (for the AI: `scripts/` — what each script is for)

> Everything is under `scripts/`; the large fw-RE toolkit is in `scripts/m2/`. Shared env:
> `source scripts/fp3-env.sh` (paths, serial `$FP3_SERIAL`, partitions, helpers).
> ☠️ Guardrails: §8. A `python3` reader is required for `/dev/mem` (dd/devmem return 0 — rule 6).

**Device access / link:**
- `fp3-env.sh` — shared env, source it from the others. `fp3-ssh.sh` — non-interactive SSH to pmOS.
- `fp3-link.sh {status|up|wait|ip}` — host NCM link management (☠️ NEVER a usb reset, only passive polling).

**Slot / flash / boot:**
- `slot.sh get|set [a|b]` — A/B retry count + slot (fastboot). `boot-watch.sh` — reboot + output watching.
- `flash-pmos.sh [full|vbmeta|lk2nd|rootfs]` — pmOS flash. `swap-to-pmos.sh`/`swap-to-ut.sh` — slot switching.
- `setup-dualslot.sh` — dual-slot setup. `to-twrp.sh`/`twrp*.sh`/`twrp-dd.sh` — TWRP. `sd-fsck.sh`/`ut-backup.sh`.
- **`test-slim-kernel.sh`** — the MAIN pmOS kernel loop: build→install→flash system_b→boot→slim/NGD dmesg capture.
  `flash-wait-capture.sh` — flash + boot wait + capture (more general).

**Register / memory readers (`/dev/mem`, mmap):**
- **`frm.py [label]`** ★ — the reader for the §2 framer+NGD table (FRM_CFG/STAT + NGD CFG/STATUS/INTS), with a verdict
  (FRAMING/DEAD/GATED); works on UT AND pmOS. **Use this to check framer state.**
- `regdump_pmos.py` / `regdump.py` — NGD/SLIMbus register dump. `rdmem.py`/`rdreg.sh`/`rdreg2.sh` — raw registers.
- `rdtlmm.py` — TLMM/pinmux. `p2_read.py` — P2 positive-case registers. `read_0x2c_snapshot.py` — the QDSP6SS 0x2c marker.
- `m2/frm_read.py`/`m2/frm_wake.py` — a minimal framer reader/waker. ☠️ `gcc_snapshot.py` — a full GCC scan, **DO NOT USE** (bus hang→watchdog).

**QMI / QRTR / ADSP diag (the message layer):**
- `qrtr_lookup.py` — QRTR service census (ADSP=node5, slim svc 0x301). `adsp-smem-log.py` — the SMEM_LOG ring (APPS envelope).
- `diagtap.py`+`diagcap.py`+`parse_f3.py` — the pmOS ADSP DIAG F3 tap (rpmsg CNTL). `qsr_resolve.py`/`f3_dump.py` — QSR hash/F3.
- `ut-diag-adsp.py`/`ut_diag_f3.py` — the classic UT `/dev/diag` F3. `diag*.sh`, `pmos-*diag*.{py,sh}`, `poll_pipes.py`/`poll2.py` — helpers/capture.

**Firmware RE / cave pipeline (adsp.mbn patching — for the §7 call chain):**
- `build_snap<X>_patch.py` — a cave builder for a given splice/leaf (X ∈ {T3, T3b, VA, HWL/HWL3/HWL4, H97, 2..9/A..D});
  paired with `deploy_snap<X>_{pmos,ut}.sh` (deploy) + `smem_snap<X>_read.py` (reading the stash). `smem_toc_read.py` — the SMEM TOC.
  **Most recent:** H97 (the runtime-dispatched leaf, folyt.97), HWL4 (fixed VA, folyt.94), T3 (config group, folyt.93).
- `m2/` — the full RE toolkit: **`m2/qtestsign`** (the v3 signer), `elfmap.py`/`make_elf.py` (mbn↔ELF), `seg{1,2,3}.elf`
  (code segments for disassembly), `golden-framer-regs.txt`, `build_m*.sh`/`deploy_m*.sh` (the earlier m-series caves),
  `stock_ulog_probe.py`, `m2/frm_read.py`. Stock fw: `m2/adsp.mbn` (pmOS 3ed6924d).

**Audio/codec test + UT-side capture (needed AFTER the framer comes up):**
- `ut-capture-framer.sh` — the UT golden framer bring-up capture. `ut-discover.sh`/`ut-trace.sh`/`ut-ssr-trace.sh` — UT discovery/SSR trace.
- `ear-tone*.sh`/`hph-test.sh`/`spk-tone.sh`/`voice-test.sh`/`voicehold.py` — sound tests. `dapm-probe*.sh` — the DAPM path.
- `ucm-look.sh`/`ucm-why.sh`/`fix-ucm.sh`/`set-vol.sh`/`sink-check.sh`/`verify-spk*.sh` — UCM/mixer/volume. `fdt_slim.py` — the slimbus DT.

**Charger / fuel gauge (a SEPARATE track, not audio):**
- `charge-test.sh`/`discharge.sh`/`thermprobe.sh`/`build_fg.sh`/`fg-verify.sh`/`gen_ocv.py` — the PMI632 charging/fuel-gauge port.

**DTB / module deploy / trace:**
- `deploy-dtb-and-trace.sh`/`deploy-ko-dtb-trace.sh` — DTB/`.ko` deploy + trace. `los-trace.sh`/`pdr_trace.sh`/`capture-dbg.sh` — trace/DBG.
- `pmos-baseline.sh`/`post-reboot.sh` — baseline/post-reboot helpers.

> Hot-swap quick tip (folyt.103): `CONFIG_QCOM_Q6V5_PAS=m` → the PAS driver `.ko` can be replaced without flashing
> (build --src → extract `qcom_q6v5_pas.ko` from the apk → vermagic check → scp → `/lib/modules/$(uname -r)/…` → depmod → reboot).
