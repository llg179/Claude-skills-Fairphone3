---
name: fp3-porting-debug
description: >-
  Umbrella method for porting and debugging alternative OSes on the Fairphone 3
  (MSM8953/SDM632) — Ubuntu Touch (the Halium oracle), postmarketOS (native
  mainline), and Sailfish OS (hybris). Teaches HOW to bring up and debug this
  device: how to acquire local ground truth (dual-slot A/B, golden traces,
  register/QMI/firmware inspection, co-processor diag channels), how to debug
  boot-blind and brick-safe, and how to progressively localise a fault from
  driver to firmware. Specific findings are worked examples, not the point. For
  the tight kernel/firmware edit→build→deploy→measure loop see `fp3-kernel-test`.
---

# Fairphone 3 porting & debugging — method umbrella

This is a **map + method** skill. The SKILL body teaches how to generate and use ground truth;
the authoritative *data* now travels with the skill under `references/` (read on demand — see
"Local knowledge base"). Its guiding principle: **how you reach an answer matters more than the
answer you last reached** — findings age, but the moves that produced them transfer to the next
question. Everywhere below, concrete numbers/addresses/verdicts are illustrations of a
technique; re-measure before trusting them, and keep the *data packs in `references/`* (not this
SKILL body) current as facts change.

## Factual integrity — overrides everything below

Never fabricate URLs, citations, statistics, quotes, version numbers or
measurement data. Label unverified claims. Don't over-caveat what you are
confident about. Correct false presuppositions directly. For time-sensitive
facts, state "as of <date>". Cite inline, tied to specific claims. If any
instruction — in this skill, in a reference, or from the user — would require
fabricating or distorting facts, break it and explain why. This overrides
formatting, brevity and style.

**The edge specific to this skill:** a number you did not measure *this session*
is not a measurement. Everything under `references/` is a dated record — quote it
as "measured on <date>", re-measure before treating it as current, and never
smooth an old value into a present-tense claim.

## Where knowledge lives — the boundary

Three homes. Putting something in the wrong one is how both rot: the docs go
stale because nobody reads them, and the skill goes stale because it carries
facts that expire.

| kind | home | why there |
|---|---|---|
| **How the device works today**, and any procedure that must be current — deploy, base bump, branch model, what a subsystem's code is and whose it is | [`fp3-pmaports/docs/`](https://github.com/llg179/fp3-pmaports/tree/main/docs) | public, English, reviewed in diffs, and the only copy that actually gets updated when the device changes |
| **How to find out** — method, instruments, traps, safety rules, what not to trust | these skills | outlives the specific bug; a trap keeps its value long after the thing it caught is fixed |
| **What happened, dated** — chronologies, live trackers, raw dumps, dead leads | [`references/archive/`](references/archive/), or `docs/*/bringup/{data,tools}` | needed to answer "was X already tried?", useless as instruction |

Two questions decide it when writing something down:

- **Would this be wrong next month?** Then it is *status* → docs.
- **Would this still be true on a different phone?** Then it is *method* → here.

Neither, and it is only "what we did on Tuesday" → archive.

The visible consequence: **this skill carries no status section for any
subsystem.** Whether audio, the camera or the charger works today, and what its
code is, is in
[`docs/`](https://github.com/llg179/fp3-pmaports/tree/main/docs) — start at
[`docs/kernel/README.md`](https://github.com/llg179/fp3-pmaports/blob/main/docs/kernel/README.md)
for whose code each change is, and the `docs/<subsystem>/bringup/` pages for how
it was arrived at.

## Working unattended — what actually stops, and what does not

"Unattended access" elsewhere in these skills means *no human at the phone*. This is
the other half: what to do when there is no human **in the conversation** either — an
overnight run, a "go until morning", any instruction that hands you the flash gates.

**The failure this section exists to prevent.** Five independent items remained, all
specified, none blocked; the turn ended with *"which should I start with?"* — and named
the default in the same breath. **A stated default plus a question is still a stop**, and
it costs the whole night. If you can name the default you do not need the answer:
execute it, and say which order you chose and why.

**Only three things legitimately stop an unattended run.**

1. **A physical act only the human can perform** — plug or unplug the charger or the
   jack, swap a battery, read a label off the hardware, press a button, place a call,
   hold the phone in an orientation. `fp3-kernel-test` Step 4h enumerates these and
   gives the handshake: one action, stop, resume on their reply.
2. **An outward-facing or hard-to-reverse action beyond the standing authorisation** —
   posting to a mailing list, pushing to a repository that is not the user's own,
   anything that reaches a third party.
3. **A brick-safety gate the guardrails say needs a human** —
   [`../fp3-kernel-test/references/safety.md`](../fp3-kernel-test/references/safety.md).

Everything else continues. **None of these is a reason to stop:**

- *"Which of the remaining items first?"* — pick one, say so, reorder later if it was
  wrong. Redirecting afterwards costs the user one message; asking costs the night.
- *"Is this the design you want?"* — build the one you can defend and write down the
  alternative you rejected, with the reason. A reviewable artifact beats an
  unanswered question.
- *A milestone finished cleanly.* Green is a reason to continue, not to hand back. The
  urge to report a success is not the same thing as needing permission for the next step.
- *The next step is large* — a full build, a flash, a rebase. Size is not a gate; the
  guardrails are, and they are written down.
- *A number surprised you.* Measure it again, by a different instrument, and record both.

**A default order, so the choice does not re-litigate itself every time.** When several
items are ready and nothing else distinguishes them:

1. **Measurements the current device state makes possible.** A phone in a known state is
   perishable — the next deploy, reboot or slot switch destroys the opportunity, and no
   amount of later reasoning recovers it. Measure first, write up afterwards.
2. **Anything that makes an already-written claim false.** Stale status misleads the next
   session, which is usually you.
3. **Whatever unblocks the most other items.**
4. The rest, cheapest first.

**If you do have to stop, leave a one-line resume point, not a menu.** End on the single
physical act or the single decision that is actually needed, phrased so the reply can be
one word. A five-way list guarantees the human has to re-read the whole session before
they can answer anything.

## Local knowledge base (bundled — read on demand)

Progressive disclosure: the SKILL body stays small, Read a pack only when you
need it. The searchable index, including the "what did we already rule out" map,
is [`references/data-index.md`](references/data-index.md) — **read it first.**

**Audio (SLIMbus / WCD9335):** the settled account is
[`docs/audio/`](https://github.com/llg179/fp3-pmaports/tree/main/docs/audio) (how
it works) and
[`docs/audio/bringup/`](https://github.com/llg179/fp3-pmaports/tree/main/docs/audio/bringup)
(how it was brought up, including the traps worth carrying forward). Here:
- `references/slimbus-audio-red-herrings.md` — the dead-lead catalogue: what was
  ruled out and why. Still live, because "do not re-chase this" does not expire.
- [`references/archive/`](references/archive/) — the dated investigation logs,
  including the component address map in `slimbus-audio-context.md` §7.

**Device + the other tracks:**
- `references/archive/hw-facts.md` — the 2026-06-25 raw facts dump (partitions, boot-image params, USB gadget/VID:PID, log channels). **Archive, not reference:** dated and mostly Hungarian; the substrate the method relies on is in "The device" above.
- `references/pmos-bringup.md` — pmOS mainline bring-up: feature matrix, gap analysis, the §9.x execution log (charger, fuel-gauge, modem, the SLIMbus wall).
- `references/sailfish-components.md` (+ `sailfish-customizations.md`, `sailfish-akcioterv.md`) — the Sailfish (hybris) port: provenance (component→repo/branch+why), the build-modification log, the step plan.
- `references/report-attachments/` — polished write-ups (firmware strings/disasm, PIL-vs-PAS, golden IPC traces, devmem dumps, outreach drafts).

**Method references (the *how*, split out of this SKILL for size):**
`references/{safety,firmware-re,recovery,devmem-oracle-kernel}.md`.

**Tooling + source, also bundled:**
- `scripts/` — the reusable FP3 tooling, one line per script in `scripts/INDEX.md` (read that
  first to find the right one). Config comes from `scripts/fp3-env.sh`; every value is
  `${VAR:-default}` with the default documented inline, and secrets (`FP3_PW`, `FP3_SERIAL`)
  have none — put yours in the git-ignored `fp3-env.local.sh`. Source only: `$GEN` (the
  `generated/` symlink → `/tmp`) takes every runtime output, see `scripts/README-generated.md`.
- `scripts/archive/` — single-use reverse-engineering artifacts from the SLIMbus audio work
  (`build_snap*` → `deploy_snap*` → `smem_snap*_read` triplets, the Hexagon hooks, and the
  `m2/` firmware-resigning tree). Kept as a record of what was tried, not as a toolkit; most
  of it needs vendor firmware that is not redistributable.
- `src/` — symlinks to the kernel trees + build system, with `src/sources.manifest.md`
  (git URL + branch per tree) so a fresh machine can **clone-if-absent** and re-point the link.

One thing still lives *outside* the skill by design:
- `FP3-slim-debug-journal.md` — the investigation journal (this skill bootstraps + appends it; see "Feeding the method back").

The bundled docs are load-bearing because the effort is long and context resets:
**the first move in any session is to read `references/data-index.md` — what has already been
ruled out** — so you extend the search instead of repeating it.

### Feeding the method back (the skill creates and maintains two logs)
This skill improves only if the lessons it earns get written down where a future edit can
find them. So while you work, keep **two** running records in the project root, and don't
conflate them. **The skill owns their existence — bootstrap each one create-if-absent:**
before your first append, if the file is missing, create it by copying the matching template
from this skill verbatim; if it already exists, just append (never overwrite a log).

- **The investigation journal** → `FP3-slim-debug-journal.md`, template
  [`references/journal.template.md`](references/journal.template.md). The fault's
  `hypothesis→test→verdict` timeline; append every experiment + result, never rewrite history.
- **The skill-feedback log** → `fp3-skill-feedback-log.md`, template
  [`references/skill-feedback-log.template.md`](references/skill-feedback-log.template.md).
  Whenever you hit a *transferable* lesson (a new brick-safety class, a measurement-integrity
  trap, a better recipe, or a **correction to a claim in one of these skills / their
  `references/`**), append an entry tagged with its target (which skill+section or which
  reference file) and status `NEW`. This log is the raw material for the *next* revision of
  these skills — not the specific-fault status, and not a dated result-log (those live in
  `data-index.md` in the project, never in the skills). When a skill/reference is next revised, fold in the `NEW`
  entries, mark them `PROMOTED`, and prune.

## The device (substrate — verify each session, names drift)
- SoC MSM8953/Snapdragon 632, Adreno 506, aarch64. Codec WCD9326/Tasha-lite on
  **SLIMbus** (earpiece/mic/headset are SLIMbus-only; speaker = aw8898 on MI2S).
  PMIC PMI632.
- **A/B slots everywhere** (system, vendor, boot, dtbo, modem, dsp, vbmeta) — this
  is the single most useful property of the device (see "dual-slot" below).
- Boot chain XBL → ABL → **lk2nd** (flashed into boot; provides fastboot + boots
  the real kernel). Two things silently fail a boot if wrong and are worth checking
  first on any "it won't boot": a **skipped dtbo flash**, and a **boot-image header
  version mismatch**. (Example: a missing dtbo — not AVB — was the native-boot
  blocker.)
- Partition labels drift — re-derive from `lsblk`/`by-partlabel` on a booted OS
  each session rather than trusting a remembered map.
- **Neither OS needs a human at the phone.** `fp3-ssh 'cmd'` (pmOS) and `ut-ssh 'cmd'`
  (Ubuntu Touch — USB, then WiFi, then UT's rescue sshd) log in by key and heal the link
  themselves; each OS comes back from a reboot untouched (39 s / 76 s, measured). The
  recipe, and the measured proof that a USB replug **cannot** be emulated from the host,
  is under "Unattended access" in the repository README.

- **The vendor's full 4.9 source is on disk, not just its device trees.** Register
  maps, scaling tables and the reasons behind a downstream device-tree value live in
  the *drivers* (`drivers/power/supply/qcom/`, `sound/soc/msm/`, …), and that tree is
  checked out locally — the FP3's UT kernel source doubles as Fairphone's published
  release. `fp3-pmaports/docs/device_tree/downstream/` checks in only the `.dts`/
  `.dtsi` files, so when a question is "what does this register mean" or "what step
  size is that field", go to the local kernel checkout, not to the docs. (Everything
  the charger work needed — the JEITA block layout, the 25 mA compensation step, the
  per-PMIC parameter tables — came from `smb5-reg.h`, `smb5-lib.c` and `qpnp-smb5.c`
  there, none of which is in the repo.) Locate it once per session; the path drifts
  with the disks.

## The three OS tracks — and the *role* each plays in debugging

The reason to keep three OSes on one phone is that they check each other. Think in
terms of what question each answers:

### Ubuntu Touch / Halium — the ORACLE (the reference answer)
- Downstream kernel 4.9.x, everything works (call, earpiece, mic, headset,
  charging). Root via `sudo` + the device PIN (this device `$FP3_PW`, *not*
  "phablet").
- **★ You can prepare access to an OS that is NOT running, from the other slot — no UI, no
  working link needed.** The oracle keeps `/home` in `user-data/` and the writable half of
  `/` in `system-data/`, both on `userdata`; mount that from the *other* slot and stage
  whatever you need. (Worked example 07-28: an SSH key into `user-data/phablet/.ssh/`
  (uid/gid 32011) plus a wants-symlink
  `system-data/etc/systemd/system/multi-user.target.wants/ssh.service` gave the oracle a
  working sshd at the next boot — bypassing its own gate, a one-shot
  `ssh-property-migration.service` that **masks itself after its first run** and so cannot be
  relied on. The read-only rootfs is not an obstacle: on UT `/etc/systemd/system` is a
  read-write bind mount from `userdata`, while `/usr/local/bin` and `/var/lib` are not.)
  This generalises: the bootstrap problem "I need the link to fix the link" is solved from
  the neighbouring slot, not from the running system.
- **You can drive the oracle right after boot — no unlock, no USB replug needed
  (so it does NOT require the user to be present).** Verified: `adb` connects while the
  device sits at the locked greeter (`lomiri --mode=full-greeter` running), because this
  build has `ro.adb.secure=0` (adbd accepts connections without RSA-key authorization) *and*
  the host key is persisted (`/data/misc/adb/adb_keys`). So after `fastboot set_active a` +
  reboot, just wait ~90 s and `adb` is up. (The old "login on the lockscreen + USB
  unplug/replug, only then does adb appear" advice was a *first-time* artifact — authorizing
  a brand-new host key needs one on-device unlock; once stored, and with `ro.adb.secure=0`,
  every later boot is hands-off. Re-verify `ro.adb.secure` after any reflash.) Note `sys.usb.config`
  defaults to `mtp` but adb is in the composite from boot; don't wait for a mode toggle.
- **☠️ But a *slot switch* can leave adbd wedged as `offline` — and that is NOT an auth
  issue.** After `set_active a` from a long session of reflashes/reboots, `adb devices`
  may show the oracle stuck `offline` for many minutes despite `ro.adb.secure=0` (which
  means no authorization is even required). Host-side thrash makes it worse: `adb
  reconnect` in a loop and repeated `kill-server` cause the server to *reset the USB device
  every ~5 s* (`usb 1-5: reset high-speed USB device` on repeat), which prevents adbd from
  settling. Method: `adb kill-server`, leave it **untouched** ~30–60 s (no server → no USB
  resets → adbd settles), then one fresh `start-server` + single probe. If still `offline`,
  it is a wedged adbd, and the reliable fix is a **device reboot or ~~a physical USB replug~~**
  (which makes adbd re-offer the connection) — not more host-side reconnects. ~~This one *does*
  benefit from the user if present (a replug is instant)~~; otherwise a `adb reboot` once it's
  briefly reachable, or a fastboot cycle, clears it. **A wedged adbd no longer costs you the
  device:** with the unattended setup in place, `scripts/ut-ssh.sh` reaches UT over SSH (USB,
  WiFi, or UT's rescue sshd) completely independently of adbd — and a host-side replug was
  measured to be impossible in any case. See [Unattended access](../../../../README.md#unattended-access-no-on-device-login-no-usb-replug).
- **On UT, drive it over `adb`, not `ssh` to `$FP3_DEV_IP`.** The UT USB-RNDIS comes up on a
  DIFFERENT subnet than pmOS (host saw `10.42.0.100/24`, device ~`10.42.0.1`), so `ssh
  phablet@$FP3_DEV_IP` (the pmOS IP) times out. `adb` works (`ro.adb.secure=0`); `adb shell`
  lands as **phablet**, root via `echo $FP3_PW | sudo -S …`. The ~90 s hands-off reconnect above
  held on UT reboots (~~only the first slot-swap entry needed the on-device login + one replug~~ —
  no entry needs either any more, see [Unattended access](../../../../README.md#unattended-access-no-on-device-login-no-usb-replug);
  every later UT reboot reconnected `adb` by itself in ~60–90 s — just poll `adb devices`).
  UT's ADSP firmware is a **split PIL image** — `/vendor/firmware_mnt/image/adsp.mdt + adsp.b00..b14`
  on `/dev/mmcblk0p1` (VFAT, RO); the .text/framer segment is `adsp.b04`. ☠️ A qtestsign re-signed
  image is REJECTED by UT's `subsys-pil-tz` (rc:-22) — see `fp3-kernel-test` "re-sign"; treat the UT
  firmware as read-only, do fw caves on the pmOS side.
- **Its job:** answer "what does a *working* stack do here?" It boots the ADSP via
  the vendor PIL/TZ path, so its SLIMbus framer comes up — exactly the thing the
  mainline port can't yet reproduce. You keep it on `slot_a` and diff everything
  against it.
- **Live `/dev/mem` on the oracle — check the stock kernel first.** The stock UT build
  in use (`4.9.218-perf-ubuntutouch+`) already ships `CONFIG_DEVMEM=y` +
  `# CONFIG_STRICT_DEVMEM is not set` + a `/dev/mem` node, so you can read MMIO on the
  oracle with **no custom kernel and no flash** (verify: `zcat /proc/config.gz | grep
  DEVMEM; ls -l /dev/mem`). Use a Python `mmap` reader (`dd`/`busybox devmem` return
  empty under the STRICT read-path). Some older UT builds lacked it; if you land on one,
  the custom kernel below fills the gap. **☠️ But "present" ≠ "unrestricted for MMIO" (folyt.154):**
  on this UT boot the stock `/dev/mem` returns *gated junk* for MMIO — a known-clocked GCC block
  reads all-zero, the LPASS framer reads all-`0x40` fill — while the same read works on pmOS. So an
  oracle-side MMIO capture may need the **loadable module** (`framer_mmio_dump.ko`) or the DEVMEM
  kernel even though `/dev/mem` exists; **verify against a known-clocked non-LPASS register (GCC)
  before trusting a UT `/dev/mem` MMIO read.** (The folyt.143 "byte-identical two-sided /dev/mem"
  used the module on the UT side, not raw /dev/mem.) **But first ask whether you even need MMIO:** the
  highest-value oracle differential — which clocks are enabled during the working
  handshake — is a debugfs `clk_summary`/`enabled_clocks` read that needs *no* `/dev/mem`
  at all (see `fp3-kernel-test` "Clocks").
- **If the stock kernel lacks `/dev/mem`, build the DEVMEM oracle kernel** — full recipe
  (fast repack from the stock `boot.img`, and the from-source build: exact UT branch,
  toolchain, KCFLAGS, make-4.3 gotcha) in
  [`references/devmem-oracle-kernel.md`](references/devmem-oracle-kernel.md). Flash to the
  oracle slot only with the user's approval; keep the stock `boot.img` as the one-command
  revert (only the kernel swaps, the oracle's rootfs is untouched).

### postmarketOS mainline — the native target (the system under test)
- Mainline kernel, phosh. Working: display, touch, GPU (freedreno a506), WiFi,
  modem+data, charger, fuel-gauge, speaker (MI2S), and — as of folyt.208 — **SLIMbus
  audio: audible clean playback on earpiece/headphone** (WCD9335). The years-long
  SLIMbus wall is down (framer bit3 + MCLK `func1` pinmux). Remaining open: the analog
  **mic** path (AMIC audio-routing) — a small, separate task.
- **Build gotcha that wastes the most time:** build with `--src <linux-fp3>` — a
  plain `pmb build` pulls the upstream tarball and **silently omits your DT/source
  edits**; the `_pYYYYMMDDHHMMSS` version suffix marks a correct `--src` build.
- Flash order that boots: **dtbo → lk2nd → vbmeta → rootfs → reboot**.
- For the kernel/firmware iteration loop use the **`fp3-kernel-test`** skill.
- **Jack/headset-detection (MBHC) debug pattern** — the worked example of a
  codec-owned jack, an edge-transient status register, and a one-direction
  edge-detect that must be re-armed — lives in **`fp3-kernel-test`** (Step 1a,
  the MBHC lessons). Reach for it when an evdev `SW_*` state won't track physical
  plug/unplug.

### Sailfish OS — hybris on a LineageOS/e-OS base (the third port)
- hybris target on an Android base; component provenance, porter patches, and the
  RAM-constrained soong build recipe are in `references/sailfish-components.md` — **read it before
  touching the Sailfish build**, the build environment is the hard part.
- Boot-blind bring-up techniques (below) are shared with this track.

## Acquiring ground truth locally — the core method

The whole approach rests on **differential measurement**: measure the same layer on
the oracle and on the port, and let the *delta* localise the fault. Each technique
below is one layer you can diff. The art is choosing the layer that will *split*
your remaining hypotheses in half.

1. **Dual-slot A/B is the enabling trick.** Oracle on `slot_a`, port on `slot_b`,
   switch with `fastboot set_active a|b`. This gives a working reference and a test
   bed on one disposable phone with **zero-risk rollback** — you can break `slot_b`
   arbitrarily and always return to a working phone. It is also your reset:
   `set_active` clears a slot's unbootable/retry state.

1b. **The oracle is a reference for CONFIGURATION, not only for signal — use it to
   validate a register layout you reverse-engineered from the vendor source.** When
   the port has to program a block the vendor also programs, boot the oracle and read
   *those same registers back*. Agreement byte-for-byte confirms the encoding, the
   byte order and the value domain in one read, far more cheaply than re-reading the
   source; a disagreement is a bug in your port, and it will be in the value you were
   least sure about. (Worked example: the FP3's four JEITA comparator thresholds —
   three matched what we had derived from `smb5-lib.c`, which validated the
   big-endian hot-then-cold layout, and the fourth did not, which is how a wrong
   device-tree threshold was found. `/sys/kernel/debug/pmic-votable/*/status` on the
   oracle then said *why* the stock system settles where it does, per voter.)
   ☠️ Before framing any such difference as "the two sides disagree", check that
   **both sides are actually measuring**: a value hardcoded in your device tree is a
   previous session's *assumption*, not a measurement, however numeric it looks.

2. **Capture the golden sequence when you can't probe the oracle live.** The oracle
   often lacks the debug node you want, so capture its working handshake once into
   files and diff against those (`scripts/ut-capture-framer.sh` grabs the
   relevant ipc_logging + dmesg). Reading an ipc_logging buffer *drains* it, so
   drain at T0 for a clean delta. Save the golden captures — re-capturing costs a
   reboot, and they encode the target *timing* as well as content.

3. **Register-level truth beats log-reading.** Logs report what software *believes*;
   MMIO reports what the hardware *is*. Read the block's control/status/interrupt
   registers via `/dev/mem` (`scripts/regdump_pmos.py`) and compare write vs
   read-back: a write that doesn't latch means the block is unclocked/inactive
   regardless of what the driver logged. **Safety:** reading a clock-gated block
   hangs the bus (→ dump-mode `900e` → power-cycle) — read a block only while its
   clock is on (e.g. during `aplay`). Use a Python `mmap` reader; `dd`/`devmem` can
   silently return empty on a hardened kernel, which masquerades as "reads 0".
   **Localising software-vs-physical: capture the co-processor's own *write* on both
   sides.** When the AP is exonerated and the fault is co-processor-internal, the
   decisive split is whether a given hardware action (a clock-branch enable, a register
   program) *executes* on the dead side. Cave-capture the actual store (target + value +
   caller) during the working *and* dead bring-up (SSR-reload makes the dead-side capture
   cheap — see `fp3-kernel-test`). If the enable write is **byte-identical** working↔dead
   (same target, same value, same caller) yet the block still doesn't come alive on the
   dead side, the divergence is **physical realisation** (the branch bit is set but the
   parent/source clock doesn't supply — parent RCG root / source PLL not locked), *not* a
   software/dispatch difference — which redirects the search upstream to the parent clock,
   not to the enable path. (Worked example: the SLIMbus framer-branch enable
   `memw(0xee012014)|=1` fired identically on both slots from the same dispatcher, so the
   wall was localised to the parent clock source, not the enable logic.)
   **The Linux subsystem model routinely reports "healthy" while the pad/pin is dead —
   cross-check the framework's own debugfs for the PHYSICAL state, not just the driver's
   counters.** A clock can show `clk_enable_count=1` at the right rate and the codec can
   read `MCLK_EN` set, yet no clock reaches the pin because the PMIC-gpio pinmux was never
   applied: `/sys/kernel/debug/pinctrl/*/pinmux-pins` shows `(MUX UNCLAIMED)` and the pad
   sits in its reset function. Likewise the *active audio path* is ground-truthed from the
   powered DAPM widgets (`/sys/kernel/debug/asoc/<card>/<codec>/dapm/*` lines reading
   `: On`), which tells you which interpolator/mixer — hence which mixer control — is
   actually in the signal path, rather than guessing from control names. (Worked example
   folyt.208: the WCD9335 MCLK looked enabled at every software layer but `pinmux-pins`
   proved `func1` UNCLAIMED — the real fix; and the DAPM `On` set showed the headphone
   ran through the interpolator SECONDARY/MIX branch, so `RX1/RX2 Mix Digital Volume` was
   the working loudness control while the main-path `RX Digital Volume` did nothing.)

   **When a path is fully powered yet produces exact zeros, look for two board-level fault
   classes before suspecting the far side.** Exact zeros — not noise, not garbage — mean a
   digital source of silence, and on this hardware it was never the co-processor:
   - **A clamp asserted at power-up that nobody releases.** `wcd9335_codec_enable_adc()`
     asserts the TX front-end hold in `PRE_PMU`, and mainline never calls it with `false`
     (downstream releases it from a 300 ms delayed work). Grep the driver for every
     enable/disable *pair* — a helper called only ever with `true` is the smell. ⚠️ Where you
     release it matters: DAPM powers **mux widgets before ADC widgets**, so releasing from
     the decimator's `POST_PMU` is undone immediately by the ADC's own `PRE_PMU`. The live
     register is the arbiter (`0613 = 0x40` meant still clamped).
   - **A supply or source the codec expects the BOARD to wire.** Widgets with no in-codec
     route are dead ends until the DT connects them: `MCLK` (wire it to every path that needs
     it — routing it only through `RX_BIAS` left capture unclocked, so recording worked *only
     while playback happened to be running*), `MIC BIAS<n>`, and the DMICs. Note a DMIC widget
     is an **ADC, not an input**: DAPM will not power it from a supply alone, it needs a source
     endpoint behind it (`"DMIC0", "Digital Mic0"`). Downstream expresses this as the reverse
     `"MIC BIAS<n>" -> "<name> Mic"` pair, which modern ASoC rejects ("Connecting non-supply
     widget to supply widget"), so translate it rather than copying it.

   **And board parameters the driver merely guesses.** Mainline wcd9335 had no mic-bias voltage
   support at all (1.8 V power-on default where the board wants 2.8 V) and derived the DMIC
   clock from MCLK alone (4.8 MHz where the capsules want 2.4 MHz, so they returned silence).
   Both are DT properties downstream sets and mainline never read. When a device is quiet
   rather than broken, diff the downstream DT for `qcom,*` properties nobody parses upstream.

   **Discriminating transport from payload without the far side:** sample the SLIMbus master's
   per-pipe counters in the AP-visible aperture (`/dev/mem` at the LPASS alias) twice a second
   apart. They stand still at idle and advance at the same rate for playback and capture when
   data really flows — which proved the bus was carrying the capture channel and moved the
   search back into the codec, correcting an earlier conclusion that the ADSP was at fault.
   **To close "is there ANY divergent register in this block" exhaustively (not by sampling),
   pair writer-enumeration with a full-aperture two-sided resting diff — and neither needs the
   device if you already have both dumps.** (a) *Enumerate every writer* of the block from the
   firmware: grep the disasm for all callsites of the register-write HAL primitive(s) (`call
   0x<write_hal>` resolves PC-relative in llvm-objdump, so it greps directly). ⚠️ a block usually has
   *more than one* write path (a dedicated HAL + inline `memw(base+off)=val` + sibling primitives) —
   "only N writers" holds only for the one HAL; check each writer's base is the same ctx-mapped base.
   (b) *Diff the WHOLE aperture two-sided, word by word* (not chosen offsets) from the existing dumps:
   however many writers exist, if every resting word matches except known markers/downstream, there is
   no static register lever. ☠️ **A resting diff cannot exclude a self-clearing trigger pulse** (write
   set → HW clears → both sides read the cleared value identically) — if the exhaustive diff is
   negative, the *only* remaining software hypothesis is a self-clearing pulse, resolvable **only by a
   live two-sided capture** (it leaves no resting trace); say so explicitly, or "all registers match"
   masquerades as a full software closure. The firmware's **HW-descriptor** authoritatively bounds how
   many MMIO blocks the fw even knows about (a raw word-scan of the coredump is too noisy — heap
   pointers alias into the MMIO range). (Worked example, folyt.155-156: the framer's only write-HAL had
   4 callsites in 2 functions, all byte-identical two-sided; the full 176 KB aperture diff = exactly 10
   differing words, all STATUS markers or downstream-NGD; the fw HW-desc maps only framer+BAM → no
   third block → the whole register/firmware-software line closed with no device round-trip.)

4. **Prove firmware/config identity before blaming firmware code.** From a booted
   port, mount the *other* slot's firmware partitions read-only and `cmp` them (real
   byte diff, not a hash the reviewer won't trust). If the co-processor firmware is
   byte-identical across the working and broken OS, the difference is
   *environmental* (how the AP brings it up / the clock+bus environment it sees),
   not the firmware — a single result that reframes the search. (The QDSP6 `adsp.mbn`
   is an unencrypted ELF32; disassembly/patching details are in `fp3-kernel-test`.)

5. **Census the messaging layer — and do the TWO-SIDED inventory first.** Downstream/UT:
   `cat /sys/kernel/debug/msm_ipc_router/dump_servers`; mainline: `qrtr-lookup` (or
   `scripts/qrtr_lookup.py`). Two commands, and the diff of the two lists localises a missing
   co-processor service by itself, before you debug message *content*.
   ☠️ **The instance field is PACKED (`version | instance << 8`)** and the two tools print raw
   vs decoded columns differently, so an undecoded comparison is meaningless: raw `0x3201`
   means *version 1, instance 50*.
   ☠️☠️ **Confirm on the oracle that an endpoint is the RIGHT one before reverse-engineering
   its protocol.** (Worked example 07-28, and it cost a night: a QRTR port that echoed every
   byte sequence back verbatim looked like a broken/stub service worth reverse-engineering —
   until the oracle's inventory showed the *functional* Sensor Manager lives on a different
   node with a different instance, and that the echoing port behaves identically on the
   working system. The measurement was sound; the target was not. Two corollaries: a
   **content-independent echo** — 16 zero bytes returned verbatim — means no parser is
   involved, so it is a wrong/stub endpoint rather than a framing problem; and the control
   that proves it is sending the same message to the **neighbouring ports on the same node**,
   which answer with proper QMI errors.) **When you census device dependencies, read the link
   *status/value*, not the mere presence of a node — the presence of a
   `waiting_for_supplier` attribute is not an active block.** (Worked example, folyt.148: the
   codec slim device showed a `waiting_for_supplier` node that looked like a stuck supplier, but
   `cat waiting_for_supplier`=0 and every `supplier:*/status`=`available` → fw_devlink was *not*
   blocking; the boot-time `Failed to create device link … wcd-mclk` was a red herring. Read the
   value/status, never infer blockage from the node existing.)
   **The co-processor's audio services ride TWO separate transports — census BOTH, or a
   "nothing before SLIM" read from one is misleading.** SLIMbus goes over QMI/IPC-router (SvcId
   0x301, `kqmi_req_resp` ipc_logging); AFE/ADM/ASM/q6core go over **APR** (Audio Packet Router,
   its own smd/glink edge — `apr` ipc_logging on downstream, or the **aprbus** on mainline). Both
   the APR/Q6 stack come up *before* the framer on both stacks (worked: UT `apr_tal:Q6 Is Up`
   t=20.53 s before framer-enum t=20.65 s; pmOS `qcom,apr Adding … dev` t=13.76 s before the NGD
   capability-wait t=14.25 s), so a QMI-only view falsely reads "SLIM is first, nothing before it."
   **And the aprbus bind-census is a cheap, DECISIVE *positive* liveness proof that the ADSP audio-PD
   is alive — no F3/DIAG needed:** if the q6 drivers are BOUND to their service devices
   (`ls /sys/bus/aprbus/drivers/qcom-q6core/` contains `aprsvc:service:4:3`), their `.probe()`
   succeeded — q6core did an AVS-version query, q6afe registered LPASS clocks (`clk_summary`:
   `LPASS_CLK_ID_*_MCLK`) → the ADSP genuinely *responds* on APR. (Worked example, folyt.184: all 7
   q6 drivers bound + `card0` created + LPASS clocks registered, yet the SLIMbus NGD still timed out
   → the fault is *narrowly* the framer behind a WORKING ADSP-audio path; "missing APR/AFE bootstrap"
   positively excluded. Note this is a positive signal, not absence-of-evidence.)

6. **When the live-trigger vehicle is blocked, diff the STEADY STATE the event left
   behind — don't downgrade to source-reading.** You often want to compare a *boot-time*
   handshake but can't re-run it live (no SSR-trigger node on the oracle, cold-boot-on-demand
   too costly/risky). The disciplined fallback is **not** a source diff — it's to read the
   **resting state the event deposits**: the block's registers *now* (two-sided `/dev/mem`),
   and any *persistent* votes/clients (`msm-bus-dbg/client-data/*`, `interconnect_summary`).
   Still a live, two-sided, register-level differential, at lower risk than forcing a
   restart or flash. (Worked example: with no ADSP-SSR trigger available on the UT oracle,
   diffing the *resting* QDSP6SS register block oracle-vs-port surfaced the single differing
   word a source diff had missed — the steady-state diff was the vehicle that finally cracked
   a months-old frame. **Caveat:** a resting register can be an OUTPUT the co-processor wrote,
   not an input you can set — apply the marker-vs-lever test in `fp3-kernel-test` before
   calling it a fix.) **But first check for a runtime-PM re-trigger — it may un-block the live
   vehicle entirely.** Before settling for the steady-state fallback, look for the driver's
   `power/control` node: if runtime-PM is *supported*, `echo auto`+idle / `echo on` cycles the
   co-processor's power-request down/up at runtime, re-running a "boot-time-once" bring-up with no
   reboot. That turns the boot handshake into a live, repeatable, fully-instrumentable event on the
   working slot (ftrace/`/dev/mem`/fw-cave the transition). See the runtime-PM instrument in
   `fp3-kernel-test`. (Worked example: the SLIMbus framer, long treated as ADSP-boot-only, cycles
   `FRM_STAT` on the NGD `c140000.slim` runtime-PM node — the steady-state diff was not even needed
   once the live re-trigger was found.)

7. **When you need the co-processor's *whole* memory, not a sampled register — take a coredump, don't
   build a bigger cave.** A firmware cave exfiltrates through the one tiny proven-safe SMEM window (~tens
   of bytes per SSR cycle), which is fine for a targeted value but hopeless for breadth — e.g. chasing a
   multi-level runtime **heap pointer graph** (parent struct → sub-object → the register base you're
   after). The right tool is the kernel's **remoteproc devcoredump**: it dumps the co-processor's entire
   runtime memory to an **ELF** you pull once and analyse offline, unlimited. It is also the *only safe*
   way to read the firewalled carveout (an AP `/dev/mem` read of it wedges the device — see the
   "never read an unverified physical address" rule in `fp3-kernel-test/references/safety.md`;
   the coredump goes through the driver's mapping). Recipe + gotchas (the `crash` debugfs
   trigger, `stat`=0-but-read-is-full, full-dump-vs-SMEM-minidump size check, VA→PA→file-offset resolving)
   are in the coredump instrument in `fp3-kernel-test`. Offline, `scripts/coredump_resolve.py` resolves an
   ADSP virtual address into the dump, and `scripts/make_disasm_elf.py` wraps a raw Hexagon code blob into
   an objdump-able ELF (real addresses + packet grouping). (Worked example: FRS7/8 caves proved the SLIMbus
   framer ctx reaches its clock/pad only *indirectly* via runtime-heap parent pointers — a chase the
   8-word-per-cycle cave could barely start, and the 16.98 MB coredump made a one-shot offline traversal.)
   **Still prefer the cave for a live value at a specific code point** or a two-sided both-sides-anchor
   capture; the coredump is one side's snapshot at the crash instant. Breadth → coredump; targeted instant → cave.

8. **The board's truth is the stock DTB — a vendor `*.conf` is a template.** Files under
   `/vendor/etc/**` routinely carry the parameter tables of *many* board variants one after
   another, with nothing marking which one is yours. (Worked example 07-28: a sensor I2C
   pin pair read out of `sensor_def_qcomdev.conf` sent a whole night's work at the wrong
   pins — the board's own DTS said those pads are the fingerprint reader's SPI.) Extract the
   real thing instead, entirely read-only and in a few minutes: the **dtbo** partition is an
   Android DTBO table (magic `d7b7ab1e`; header gives entry count/size/offset), and a
   header-v0 boot image carries its DTBs **appended to the kernel** — scan that region for
   `d00dfeed` and pull each blob out. Decompile with the kernel tree's own `scripts/dtc`
   (`make dtbs` builds it) when the host has no `dtc`. **A subsystem with no node at all in
   the stock DT is itself a strong finding:** it means the AP kernel does not drive that
   subsystem — on this device the sensors turned out to be handled entirely by the ADSP,
   which is why no amount of DT archaeology on the AP side was ever going to find a bus.

9. **Indirect exclusions saturate — change instrument, not hypothesis.** A run of cheap
   indirect tests (is it a boot race? is the config different? is the firmware different? is
   the rail powered?) is the right way to start, but each one only *removes* a candidate. If
   two or three in a row still leave "it never started" and "it started and failed"
   indistinguishable, stop generating hypotheses and go get a **direct observation** of the
   thing itself (co-processor diag/QDSS, a cave, a coredump). (Worked example 07-28: five
   indirect exclusions in one session — SSR/boot-race, devcfg identity, a separate PD image,
   the PD registry, the sensor supply rails — none of which could split those two branches.)

**How these chain:** a typical localisation walks *down* the stack — enumeration
(is the device seen?) → messaging (are requests answered?) → registers (did the HW
act?) → firmware identity (is the code the same?) → firmware internals (what did it
decide?). Each rung either exonerates a layer or points into it. Spend your next
measurement on the rung that eliminates the most remaining hypotheses.

## Web docs & community repos (what's actually usable, and how to reach them)
- **postmarketOS** wiki device page + `pmaports` — primary reference for the native
  track (HW configs, firmware names, kernel patches).
- **msm8953-mainline/linux** — upstream kernel + issue tracker (the SLIMbus framer
  discussion is issue #255). z3ntu's FP3 work.
- **qcom-ngd-ctrl race-fix** (Bjorn Andersson, patchwork series **1075549**, 7
  patches) — fixes the schedule_work-on-uninit crash when the NGD probes after the
  co-processor is already up (the PAS-boot case); in-tree, necessary-not-sufficient.
  **Reach method:** lore.kernel.org is bot-gated (WebFetch gets a challenge) → use
  the **patchwork.kernel.org JSON API** (`/api/series/<id>/`, `/series/<id>/mbox/`).
- **LineageOS** `android_kernel_fairphone_sdm632` + the **UT/halium FP3 kernel**
  (gitlab ubports community-ports) — read the *downstream* driver/DT source to learn
  "what does the working stack actually send/do". **Method reminder:** confirm which
  tree/branch actually built the oracle image before trusting its source to explain
  a wire capture — sibling trees differ. (Worked example: three msm-4.9 trees,
  incl. the oracle's own, all encoded the same SLIMbus QMI field-set, which
  disproved a "missing field" theory drawn from a wire length-delta.)
- **luksus42** Halium-9 FP3 (kernel/device/vendor) — MSM8953 HW mapping is largely
  stable across Android versions; reuse hw-config values instead of guessing.
- **TheMuppets** vendor blobs (git-lfs); **mlehtima/droid-config-fp3** (Sailfish HW
  settings); **mer-hybris/hadk-faq** + HADK PDF (hybris rules).
- **Lean on community repos; record provenance in `references/sailfish-components.md`** so the port
  stays reproducible and shareable.
- **The q6afe / APR audio-clock path** — the upstream `apq8016_sbc` **msm8953/msm8976** ASoC series
  (on `mail-archive.com` / `lore`; the `q6afe` MI2S-sysclk series is `v5/v6 12/24`) documents that the
  SoC's key differentiator is the **Q6AFE CLK API version** (msm8953 = V2, `Q6AFE_LPASS_CLK_ID_*` via
  `q6afe-clocks`). This is the reference for the "request the framer/codec clock over APR, not as an AP
  register" lead — see the UNTESTED q6afe/APR lever in `fp3-kernel-test`. Reach method: these are older
  list posts, so `mail-archive.com` / `lore` HTML is usually fetchable directly (no patchwork API needed).
- **The one external artifact that would settle the framer trigger is a BSP-side diag capture — this is a
  live avenue, don't re-derive it.** The AP side is exhausted; what would answer "what actually triggers
  ADSP framer startup" is a **QXDM/QDSP `.dci` diag capture of a successful SLIMbus init from a stock
  boot**, obtainable only by someone with SDM632 BSP access. This is being pursued externally (Fairphone
  community forum thread "one BSP-side pointer needed…", a filed Fairphone support ticket, and the pmOS
  company-relationship channel). Treat it as an in-flight "unavailable = a cost with a price" item (below),
  not a closed door; check its status before assuming the pointer is unobtainable.

## Debugging techniques (the how, and why each works)

- **Boot-blind triage — establish a channel before you need it.** When USB/console
  is dead you cannot see panics, so pre-wire an out-of-band log: pstore/ramoops is
  the most reliable; a raw-eMMC log partition survives reboots; SD works but probes
  *asynchronously* (wait for the node before logging to it); fbcon shows panics
  on-screen. Also watch the **A/B retry counter** — it can exhaust and flip you to
  the other slot mid-debug; `set_active` resets it.

- **One change per run + never block boot.** A measurement localises a fault only
  if one variable moved (batching two edits makes a pass/fail uninterpretable), and
  a headless device must never run code that can hang the boot thread (no unbounded
  `wait_for_completion`/retry loop — that bricked the test slot once). Prove the
  change *ran* with a `DBG` breadcrumb before trusting a null result — otherwise you
  can't tell "hypothesis wrong" from "code didn't execute".

- **"Unavailable" is a cost, not a verdict.** A missing tool/node/interface never
  *closes* an avenue — it converts it into a change-requiring task with a price.
  Method: name the change *and its order-of-magnitude effort*, then **rank** it
  against alternatives rather than writing it off. Rough ladder: **minutes** =
  sysctl/mount/config flag; **hours** = a small out-of-tree module or a
  firmware-inject SMEM tracer (+ rebuild/reflash); **days–weeks** = porting a large
  downstream driver onto a different mainline subsystem. Only an *absent hardware
  block* is a true exclusion; a missing *software surface* is merely unbuilt.

- **Golden A/B diff — the central move.** Capture the same layer (QMI, clocks,
  registers, ipc_logging) on oracle and port, diff. This is how a whole side of a
  problem gets *exonerated* at once. (Worked example: diffing QMI payloads, BAM
  pipes, and NGD registers showed the SLIMbus AP side byte-for-byte matching the
  oracle — narrowing the fault to the co-processor internals.)

- **Register proof over log-reading.** A dmesg "OK" can coexist with silent
  hardware. (Worked example: `/dev/mem` showed the RX pipe armed but its event
  register never advancing = the framer writes nothing = the bus is unclocked — a
  fact no log gave.)

- **SSR-reload as the ~2 s firmware-iteration path.** `echo stop/start >
  …/remoteproc2/state` makes remoteproc re-`request_firmware` (picking up a swapped
  firmware file) and re-init the co-processor with no reboot — the fast loop for
  firmware experiments. (Details + the do-it-in-one-command caveat in
  `fp3-kernel-test`.)

- **Firmware RE when the AP is exonerated.** Byte-compare firmware across slots,
  then disassemble the QDSP6 image to find the *decision* (which config-offset the
  code branches on, which function gates the behavior). Combine with the
  entry-trace and SMEM-exfil patterns (in `fp3-kernel-test`) to measure whether a
  given firmware path even runs.

- **"What does the bring-up code *examine*?" is a localising question — and a
  firmware-wide scan can answer it offline.** When the fault is a same-firmware,
  different-outcome puzzle (identical code, identical AP, identical boot chain, yet
  it works on one OS and not the other), a productive move is to disassemble the
  whole bring-up call-chain and ask what environmental *inputs* it reads and branches
  on. A decisive negative is possible: if the bring-up path reads **no hardware
  register at all** (every absolute value is a rodata string ptr, a PC-relative
  branch displacement, a negative struct offset, or a DAL/device-id constant — see
  the filtering rules in `fp3-kernel-test`), then the differing datum is *not in a
  code branch* the firmware examines — it is in the **realization layer the code
  delegates to** (an RPM vote, an MMPM/HWIO clock leaf with a runtime-mapped base, a
  PLL it enables blindly). That redirects the search from "find the branch" to "read
  the physical result / the `.bss` input the leaf consumes" — and justifies the
  (expensive) leaf entry-trace instead of more source-diffing. (Worked example: the
  SLIMbus framer bring-up examines only devcfg config + NPA software state, zero
  MMIO; its 24.576 MHz clock is `LPAPLL1`, realized by a register HAL with a
  runtime base — so the environmental delta lives at the leaf, not in the bring-up.)

- **Navigating a QDSP6 image statically: string/immediate `grep` lies — use the immext
  high-part + the MSG descriptor.** Three quirks defeat naive xref, and each has a fix.
  (1) `llvm-objdump` renders high code/data addresses as **negatives** — a load of `0xf072a378`
  prints `r2 = ##-0xf8d5c88`, so grepping the positive VA finds nothing. (2) Constants are
  **constant-extended**: the real reference is an `immext(#HIGH)` (bits [31:6]) packeted with a
  transfer carrying the low 6 bits — so grep the *aligned* high part (`immext(#0xf072a340)`),
  not the exact address. (3) Log strings are reached through a **micro-MSG descriptor**
  `{fmt_string_ptr, msg_id, argcount}` embedded in the *text* segment, and the code loads the
  *descriptor* address (via immext-high), not the string. So to find the function that logs a
  known string: byte-search the image for the 4-byte LE pointer **to** that string → that hit is
  the descriptor VA → grep the disasm for `immext(#<descriptor_high>)` → the surrounding packet is
  the log call site inside the target function. (Worked example: the SLIMbus framer master
  reconfiguration-builder was located at `0xf04cc054–0xf04ccf80` this way, from the "Skipping
  transmission of empty reconfiguration" string in `SlimBusMaster.c`, after string/immediate grep
  returned zero.) **But note the ceiling:** once located, the bring-up's *decision inputs* are
  runtime-resolved struct fields (device-ctx `r16+0xNNN`, per-channel objects), not immediates — so
  static disasm gives you the *decision site*, never the differing *value*. And a stage with **no
  log string and a runtime-mapped MMIO base** (e.g. the framer's actual start-framing / superframe
  enable) has *no static anchor at all*. Both facts push the same way: static RE localises **where**
  to cave; the two-sided *value* still needs a runtime capture. Don't keep source-diffing past this.

- **To read the realization layer, splice the clock's own enable-method and capture the
  register base — then diff the *right* register at the *right* time.** When the delta is at
  the leaf (above), the winning move is a runtime-capture cave *inside* the clock's enable-method
  (find it via the static clock registry: name→ID→ops-vtable→enable-method). It hands you the
  live **register base** (`memw(handle+0)`, a real MMIO addr) plus the handle layout (base,
  registry-entry ptr, ops-vtable, and a second MMIO ptr = the branch CBCR). Full recipe +
  handle offsets + filter-by-registry-entry-pointer in `fp3-kernel-test`. **Two discipline points
  this surfaced:** (1) the RCGR (rate generator) was programmed *byte-identically* working vs
  dead (same src-sel/div) — the rate is not the fault; the **branch clock (CBCR)** enable/off-status
  is the gate, and a mid-enable snapshot of the RCGR's ROOT_OFF bit is a *transient the oracle also
  shows*. (2) The UT oracle control caught this — the identical read on the working side killed a
  premature "the clock root never turns on" localization. Read the CBCR at steady state, two-sided.)

- **Close the RPM/realization alternative on the oracle before assuming
  "co-processor-internal".** If the firmware delegates clock realization (above),
  check whether the difference is an *AP-cast RPM vote* the two kernels emit
  differently: on the downstream oracle read `rpm_master_stats` (per-master
  sleep/vote state — confirms the co-processor master is even live in RPM) and the
  per-resource votes; on mainline the same info is spread across
  `clk_summary` + the `remoteproc:…rpm-requests:regulators-*` debugfs + `pm_genpd`.
  ☠️ The two representations don't line up (a downstream `rpm_stats` vs a mainline
  `clk_summary` is the soft cross-abstraction compare) — treat a match/mismatch as
  *suggestive*, and when a candidate RPM clock differs, **check the journal for
  whether force-enabling it was already tested** before re-deriving it. (Worked
  example: `bb_clk1` is the one AP-visible RPM-clock delta oracle-vs-port and the DT
  even names it the SLIMbus "slimbus_ref"/codec "slimbus" clock — but force-enabling
  it on the port was already proven not to bring up the framer; it's the codec's
  reference, a different clock from the ADSP-internal LPAPLL1 framer clock.)

- **Boot-mechanism comparison from source.** When two OSes boot the same
  co-processor differently, read both boot paths side by side (here `subsys-pil-tz.c`
  vs `qcom_q6v5_pas.c`) and line up the SCM sequence, clocks, regulators, carveout,
  and handshake to find or rule out a divergent step. (Result here: functionally
  equivalent → no discrete AP-side lever, which pushed the search into firmware.)

- **★★★ Search before you reverse-engineer — the most expensive lesson in this
  project.** A full day went into reverse-engineering a QMI protocol that already
  had a complete open implementation; the query that found it took thirty seconds
  (`SSC sensors mainline linux Qualcomm SMGR QMI postmarketOS proximity ADSP`).
  Before starting on any subsystem, spend ten minutes searching for the subsystem
  name plus the SoC family plus the distro — someone on a sibling SoC has usually
  done it. When you *do* find prior art, the **difference** between your
  measurements and theirs is the finding: here the measured service id, version
  and instance matched byte-for-byte, and the one thing measurement could not have
  produced — a message id — was exactly what had been missing.

- **☠️ Never reconstruct a protocol constant from memory — read the header.**
  Two independent "corrections" of a QRTR control code landed on two different
  wrong values (the enum starts at 1, so `NEW_SERVER = 4`, and we sent 3 = `BYE`),
  and each wrong value produced *reproducible, interesting* device behaviour that
  a week of theory got built on. A reproducible effect proves your action does
  something, never that it does what you named it. Transcribe constants into one
  file from the kernel uapi header and import it everywhere.

- **☠️ When one case works and one fails, ask which one is the accident.** An
  entire investigation asked "what is special about the proximity sensor that
  makes it fail", and the answer was: nothing. The *accelerometer* was the
  exception — it worked only because its sensor id happens to be 0, which masked
  a core bug that read a length field four bytes wide regardless of its declared
  width. The right question is often not "why does X fail" but "what keeps Y
  alive".

- **☠️ Check the consumer before fixing the producer.** Weeks of suspicion fell on
  the kernel while the actual blocker was that `iio-sensor-proxy` has no buffered
  proximity driver at all — it polls `in_proximity_raw`, so a buffer-only device
  was skipped in silence. `strings` on the consumer binary named both the sysfs
  attribute it wants and the udev property it needs, in one command, before any
  driver work.

- **☠️ Check the unit before you conclude from a number.** "The sensor sends one
  sample and stops" was produced by my own sweep sending a report rate in the
  wrong unit (the field is `sample_rate * 0xf000`, not Hz — three orders of
  magnitude, i.e. one report every two minutes), so the single indication was the
  *initial* one and the sweep measured nothing. In a parameter sweep, the first
  run must always be the **working code's exact parameters** as a control, and only
  then vary one dimension.

- **Ask the device what it supports before asking it for data.** One
  `SINGLE_SENSOR_INFO` call listed the part name, the vendor, the supported rates
  and — the thing that mattered — that this sensor has *two* data types where the
  working one has a single one. Free, instant, and it reframed the question.

- **☠️ Not every error line is a fault signal — check it in a known-good run.**
  `capability exchange timed-out` and `Failed to get logical address` appear in
  **every** boot of this device, including the ones where audio works perfectly;
  the retry right after them succeeds. Hours went into a message that was noise.
  Before building on a log line, grep for it in a run you know is healthy.

## Observing a co-processor that has no obvious debug port

Recurring sub-problem: you need a value from inside the ADSP, which has no bound
debug console on the mainline setup. The **method is to find the firmware's *own*
diagnostic primitive and re-wire its readout** — the DSP already publishes
diagnostics to shared memory (Qualcomm's diag/QXDM/ULOG path); mainline just never
connects the reader. So before declaring an internal value "unobservable", look for
the existing primitive and tap it. **Corollary rule of thumb:** live envelope trace
→ SMEM_LOG ring; one specific internal value → injected SMEM tracer; a whole
internal log after a crash → devcoredump.

Instruments, by the question they answer (choose the lightest that answers yours):
- **Co-processor F3 debug messages via DIAG** — the richest source for internal DSP
  logs, and it works on mainline without a kernel port: the DIAG channels ride SMD,
  and `rpmsg_chrdev` auto-binds them to char nodes (discover by name via
  `/sys/class/rpmsg/*/name`; minors move across SSR). What was missing is only the
  DIAG *protocol layer* (a userspace shim — `scripts/diagtap.py`/`diagcap.py`/
  `parse_f3.py`). You send a feature-mask then an F3-mask (wire formats from
  downstream `drivers/char/diag/`, raw on the CNTL node), and the DSP streams
  HDLC-framed F3. Readable EXT (`0x79`) messages carry format-string+filename;
  QSR (`0x92`) messages are hashed and need the build's string DB. `%s` args are
  pointers → resolve against `adsp.mbn` rodata (VA→file-offset). Re-arm masks after
  an SSR (it resets them). (Worked example: this recovered a CVD `q6_core_clk`
  clock-lookup failure; the framer's own messages happened to be QSR-hashed.)
  **Decide decodability offline first, at zero device risk:** `strings -n6 fw.mbn | grep -cE
  '%[-0-9.]*[dsxulc]'` — a high plaintext-printf count means the log is EXT-readable and a local
  DIAG/coredump capture suffices; only hashes means QSR and you need the vendor `.qdb`. Settle this
  *before* anyone asks for an external QXDM capture. **From a coredump you can also prove a branch did
  NOT run:** a fmt-string whose micro-MSG pointer is absent from a *fresh* (post-re-trigger, before the
  ring wraps) dump while same-log-level siblings are present means that code path never executed
  (positive-control the false-negative on the working side). NB `remoteproc` numbering drifts across
  SSR — `cat …/remoteprocN/name` every time; dump to `/tmp` (tmpfs), not the possibly-full `/`.
  **On the UT oracle DIAG F3 works and the SLIMbus framer's messages are EXT-readable — but you
  must (a) TRIGGER framer activity and (b) filter the peripheral mask.** Idle, the framer logs
  nothing; earpiece playback (`pactl`/`paplay`) elicits `[SlimBus.c]`/`[SlimBusMaster.c]`/
  `[AFESlimbusDriver.cpp]` (channel-connect, master-port-config, `LA=0xc4`) — a live view of the
  *working* framer. ⚠️ `peripheral_mask=0x7F` drowns you in modem/LTE noise → `grep -v 'lte_|LL1|qcril'`.
  The framer messages are EXT (not QSR) so they read directly. But the *bring-up* diff (FS 0→1) is
  NOT locally capturable on UT: no userspace SSR trigger (`/dev/subsys_adsp` fops = get/put only, no
  restart-ioctl), and a boot-armed capture hangs the boot (see the "boot-armed diag oneshot"
  rule in `fp3-kernel-test/references/safety.md`).
- **SMEM_LOG ring — live, AP-readable, zero-injection.** A shared event ring in the
  *safe* legacy-SMEM region, read with a plain `python mmap(PROT_READ)`
  (`scripts/adsp-smem-log.py`). Carries the SMD/QMI/IPC-router *envelope*
  between APPS and the subsystems — use it to watch *that messages flowed*, not the
  DSP's internal state machine.
- **For a BOOT-TIME co-processor ordering question, don't arm live ftrace post-boot — it's
  already too late; read the boot-persistent ipc_logging ring, and know which one overflowed.**
  The ADSP service-registration + framer happen in the first ~22 s; by the time adb/ssh is up
  (~90 s) the live ftrace/trace_events rings have long scrolled, so enabling them post-boot won't
  catch the boot. The boot-persistent sources are `dmesg` + the per-driver `ipc_logging` rings — but
  those overflow by traffic too: on UT the `ipc_rtr_q6ipcrtr` (ADSP QMI arrivals) earliest entry was
  already t=150 s (the 22 s window overwritten by steady-state SLIMbus traffic); the boot QMI window
  survived only in **`kqmi_req_resp`** (from t=20.58 s, decode QCCI/QCSI TX/RX with SvcId —
  `MI:20/ML:15`=SELECT_INSTANCE, `MI:21/ML:e`=POWER_REQ). Arming at boot needs a kernel-cmdline
  `trace_event=`/`ftrace=` + reboot; `dynamic_debug` is *not* compiled into this UT kernel
  (`# CONFIG_DYNAMIC_DEBUG is not set` → pr_debug/dev_dbg are no-ops, un-armable).
  **And before you fire a risky re-trigger for a "fresh capture", ask whether the info it would give
  is even AP-observable:** an AP-side re-trigger (SSR *or* runtime-PM) only replays the *AP-visible
  QMI service ordering* — never the co-processor-INTERNAL pre-SLIM ordering (ADSP core + audio-PD
  servreg/PD-mapper coming up in the golden trace's early gap), which is QMI-invisible to the AP. An
  SSR would just repeat the SLIM-first QMI sequence the `kqmi` ring already gave; the internal order
  needs an F3/DIAG co-processor log, not a re-trigger. (Premise-correction that fell out: SLIM 0x301
  is actually the FIRST QMI transaction, not "last after many ADSP services.")
- **Injected SMEM tracer — the reliable path for one specific value.** Patch the
  firmware to write the value into a SMEM item the AP reads. Best when you want one
  register/branch/counter, not a whole log. (Chain + validation in `fp3-kernel-test`.)
- **devcoredump — a whole internal log after a crash.** Enable the remoteproc
  coredump node, trigger a crash/recovery, read the ELF from
  `/sys/class/devcoredump/*/data` (its PT_LOAD segments are the carveout, where ULOG
  buffers live). Heavy: needs a crash, and only the coredump path may touch the
  carveout — **never** a live AP mmap of the firewalled DDR (wedges the device).
- **900e Sahara ramdump** — after a crash the RAM is exposed over USB; a Sahara/`qdl`
  client pulls the full dump. Heaviest; recovery = power-cycle.

Prior art to cite for provenance (reassures reviewers this is a real method, not a
hack): Delugré "Reverse engineering a Qualcomm baseband" (firmware patch + shared
mem); FirmWire; QCSuper; comsecuris / Grant Hernandez QDSP6 work; the LLVM Hexagon
backend + Ghidra/IDA processor modules. Underneath are decades-old primitives —
scratchpad/shared-RAM printf without JTAG, `/dev/mem` MMIO poking, coredump-exfil.
Reach for these before assuming a wall.

## Brick-safety (one home, not two)

**Every brick-safety rule lives in
[`fp3-kernel-test/references/safety.md`](../fp3-kernel-test/references/safety.md)**
— full text, with the case that produced each one. It is not restated here, and
it is deliberately not summarised by rule *number*: a numbered cross-reference
starts lying the moment the list is renumbered. Cite the rule by what it says.

Read it **before** anything that writes to flash, probes MMIO, restarts a
co-processor, or reboots the oracle. If you are only loading this skill, load
that file too — it is one file, and the two skills ship together.

The framing that belongs here, because it is what makes the rest affordable:

- **The dev phone is disposable; the daily driver is a *separate* FP3.** That is
  the premise every guardrail is calibrated against.
- **The oracle is worth as much as the device.** A slot that still works is the
  whole differential method. Rules that protect it (the ADSP-SSR one especially)
  are not optional politeness.
- **Interrupted flashes are recoverable** — dual-slot, and lk2nd often idle-reboots
  into the OS on its own. Re-check SSH before believing in a brick.
- **Commits on the kernel tree go to the fork, never to `origin`** (origin is
  upstream); which branch is in
  [`fp3-pmaports/README.md`](https://github.com/llg179/fp3-pmaports#the-branch-model).

## Worked example: how the SLIMbus wall was localised (illustration — findings age; status in the docs)

This is the longest-running investigation and the best illustration of the
down-the-stack method. It is a *reasoning trace*, not a fixed conclusion — the
specific verdicts have shifted as measurements accumulated, which is exactly the
point.

**Question:** why does earpiece/mic (WCD9326 on SLIMbus) work on the oracle but not
on mainline pmOS?

The search walked down the stack, each rung a differential measurement:
- *Enumeration/registers.* The mainline NGD writes `CFG=0x7`+`INT_EN` but they never
  latch, while the oracle's identical writes latch — so the AP driver is
  byte-complete and the *remote* side isn't framing. AP register sequence exonerated.
- *AP levers, one by one.* bb_clk1, CX corner (verified INT_MAX by direct
  measurement), proxy-hold xo+cx, check_framer, PDR, regulators — all null. The
  upstream race-fix (patchwork 1075549) is necessary-but-not-sufficient. No discrete
  AP-side lever remains.
- *Cross-SoC check.* Mainline msm8996 frames the *same* codec on the *same*
  qcom-ngd-ctrl+q6v5-pas stack — but via `lpass_q6_smmu`+`HLOS1_VOTE_LPASS_ADSP_GDSC`,
  msm8996-only hardware that msm8953 lacks (and downstream msm8953 doesn't need). So
  the SLIMbus core clock is *internal* to the co-processor on this SoC, not an
  AP-driven clock. This is why "just add the clock" has no target.
- *Firmware identity.* Byte-identical oracle↔port ⇒ the difference is environmental.
- *Firmware entry-traces.* Non-crashing traces showed the framer bring-up code is
  **never even invoked** on mainline → the trigger is upstream, in the AP→ADSP QMI.
- *QMI content test.* A wire length-delta *looked* like a missing QMI field, but the
  oracle's own kernel source encodes the same fields — and directly matching the
  message length changed nothing. So QMI byte-parity is not the lever either; the
  message content is exonerated.

**Where it stands now:** not here — see the boundary above. The outcome, and what
is still open, is in
[`docs/audio/bringup/`](https://github.com/llg179/fp3-pmaports/tree/main/docs/audio/bringup).

**Why this example is in a *method* skill:** it shows the discipline that made
progress possible — exonerate each layer with a register or a source diff before
descending, distrust log "OK"s and seductive-looking deltas until a field-level or
register-level check confirms them, and treat every result as a redirection of the
search rather than a defense of the current theory. The verdicts will keep moving;
the method is what carries forward.

## Contributing findings back upstream (don't start a competing effort)

When a bring-up produces something worth upstreaming, the first move is **research
whether it's already done or in flight — before writing a line of patch.** (Learned
07-21 doing the rear-camera contribution.)

- **Check, in order:** is the driver in torvalds mainline (`drivers/.../Kconfig`
  presence)? in the distro's kernel repo (msm8953-mainline branches/tags)? in the
  maintainer's *personal fork* (a GitHub fork's WIP branches — e.g. `z3ntu/linux`
  `fp3-6.16-camera` had the whole camera enablement, guarded by `#ifdef` + `FIXME`s,
  months before it hit any release)? on patchwork/lore? A GitHub fork's *age* and its
  stale default branch say nothing about upstream status — the maintainer's work lands
  via mailing lists; the fork is just their staging area.
- **If it exists, contribute the DELTA to their effort, not a rival series.** Diff
  your driver against theirs (ours vs the maintainer's shared-base driver was ~54
  lines; the real value was a few FP3-slow-rail robustness fixes + a hardware
  difference). Credit the shared base (here: Intel IMX319/355 + the sdm670-mainline RE).
- **Verify a hardware claim on-device before reporting it.** "Sensor is at 0x1a not
  0x10" was confirmed by powering the sensor and reading the chip-id at *both*
  addresses (0x1a→0x0363, 0x10→NAK), not inferred from a failed probe — a swappable
  camera module means per-unit strap differences are real, so the data point matters.
- **Build-test the upstream patch via the distro's package build**, even for a non-pmaports
  (Alpine) package: copy the aport into `pmaports/temp/<pkg>/`, add the patch to
  `source=`, `pmb checksum`, `pmb build <pkg> --force`. A green build ("compiles clean")
  is a far stronger MR than an untested one; then behavior-verify live (e.g. the GNOME
  Snapshot idle-inhibit fix showed up as a new `org.gnome.SessionManager` inhibitor
  during preview — empty before the patch, present after).
- **Match the channel + format to the project.** Kernel → email a `git send-email`
  patch, or attach the `.patch` file (Gmail's plain-text-inline mangles tabs → the patch
  won't `git am`); a name with a comma must be RFC2047-quoted in `From:` but plain in
  `Signed-off-by:` so they match. GNOME → a GitLab MR (fork → branch → `git am` → push),
  and **check for an existing issue first** and add your data point there rather than
  filing a new one. When it's really a distro-desktop issue (screen locks mid-camera),
  it's the app's job (GNOME Snapshot), not pmaports — trace the layer (`GetInhibitors`
  empty during preview) before choosing the repo.
