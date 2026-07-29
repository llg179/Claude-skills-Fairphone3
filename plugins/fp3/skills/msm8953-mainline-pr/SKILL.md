---
name: msm8953-mainline-pr
description: >-
  How to turn the FP3 (MSM8953/SDM632) local kernel work — the wip/<base>/*
  topic branches: audio/wcd9335, camera/imx363, charger/smb2, voice — into a
  clean upstream submission. Because this work is AI-assisted, LKML is the only
  open destination: msm8953-mainline does not merge AI-assisted work and
  postmarketOS bans it outright. Encodes the maintainer guidance received on the
  msm8953-mainline channel: one branch per subsystem (not sub-split), few
  well-formed commits, and never mix DTS with driver code. Use whenever
  preparing a patch series from the llg179/linux fork.
---

# FP3 kernel work → upstream submission

This is a **process** skill: how to take device-support work that currently lives
on the personal fork (`github.com/llg179/linux`) and shape it into something a
maintainer will accept. The audio/WCD9335 series is the running worked example.

The fork's layout — `wip/<base>/<category>` → `integration/<base>` →
`submit/<base>/<category>`, and the rule that a change must land on both its wip
branch and integration — is **not repeated here**. It is defined in
[`fp3-pmaports/README.md`](https://github.com/llg179/fp3-pmaports#the-branch-model),
with the full base-bump procedure in
[`docs/rolling-a-new-base.md`](https://github.com/llg179/fp3-pmaports/blob/main/docs/rolling-a-new-base.md).
Read those for *what the branches are*; read this for *how to turn them into a
series*.

More generally: current state and procedure live in the docs, method and traps in
the skills, dated logs in archive — the split is stated in `fp3-porting-debug`
"Where knowledge lives".

The whole point: the fork's topic branches are ordered by *discovery* (one commit
per thing you learned, DTS and driver interleaved). Upstream wants them ordered by
*logic* (few commits, each one self-contained, DTS and driver never in the same
commit). This skill is the translation.

> **Read this first — the destination changed.** An earlier revision of this skill
> recommended a **pull request to msm8953-mainline as the easy first target** and
> stated that it had "no AI ban". **That is wrong and has been corrected below.**
> On 2026-07-25 the msm8953-mainline maintainer (barni2000), replying in
> [issue #197](https://github.com/msm8953-mainline/linux/issues/197), stated:
> *"we don't merge AI assisted work, it is only allowed at upstream."*
> For AI-assisted work the ordering of strictness is **inverted** from the usual
> assumption: postmarketOS = total ban, msm8953-mainline = will not merge,
> mainline Linux = permitted with disclosure. **Upstream is the only open door.**

---

## Know the versioning before you pick a base

The `msm8953-mainline` branch names look like a private scheme; they are **real
torvalds versions** (Linus bumped the major after 6.19). Three traps:

- **A stable point release is not a mainline tag.** `torvalds/linux` carries
  `v7.1` and moves on to `v7.2-rc*`; the `.3` comes from the stable tree, so
  **`v7.1.3` does not exist as a ref in `torvalds/linux`**. Any recipe comparing
  the fork against a torvalds tag of that number returns 404.
- **The local fork clone is depth-1 shallow.** `git merge-base` and
  `git log -- <path>` silently mislead — the latter returns a single commit for
  *every* path, which looks like an answer. Query the API instead:

  ```sh
  # what base is the branch really on?
  gh api "repos/msm8953-mainline/linux/contents/Makefile?ref=7.1.3/main" \
    --jq '.content' | base64 -d | head -5

  # which integration branch is newest?
  gh api "repos/msm8953-mainline/linux/branches?per_page=100" \
    --jq '.[].name' | grep -E '^[0-9]+\.[0-9]+' | sort -V | tail -5
  ```
- **A personal `fork/master` mirror goes stale** while upstream moves on. Re-sync
  before using it as a base; never rebase onto a stale mirror.

---

## Where the work can actually go

Three possible destinations, and for AI-assisted work only one of them is open.
Establish this **before** shaping any branch, because it sets the base, the
mechanics, and whether the effort is worth spending at all.

| destination | AI-assisted work | verdict |
|---|---|---|
| postmarketOS (pmaports, wiki) | banned outright, CoC-enforced | closed |
| msm8953-mainline (GitHub PR) | "we don't merge AI assisted work" | closed |
| mainline Linux (LKML) | permitted **with disclosure** | **the path** |

### Why msm8953-mainline is closed (do not re-litigate it)

Stated by the maintainer barni2000 in
[issue #197](https://github.com/msm8953-mainline/linux/issues/197), 2026-07-25:

> "FP3 is using different audio architecture and we don't merge AI assisted work,
> it is only allowed at upstream."

That is **two independent refusals**, and the first one applies even to
non-AI-assisted FP3 audio work:

- **The architecture point is correct and verifiable.** Every other msm8953/sdm632
  device in the tree uses the SoC-internal `qcom,msm8916-wcd-digital-codec` plus
  the PMIC-internal `qcom,pm8916-wcd-analog-codec` (in `pm8953.dtsi`) over
  **MI2S**. The FP3 is the **only** one with an external **WCD9335 on SLIMbus**.
  Their MBHC lives in `msm8916-wcd-analog.c`; ours lives in `wcd9335.c` — different
  driver, register map and bus. The fork has no device that would even exercise
  our code, so merging it would mean carrying untestable code.
- **The AI point is a project rule**, not a kernel rule. Accept it and move on.

Practical consequence: **do not open PRs against `7.1.3/main`.** Anything in this
skill that reads like PR preparation (base `origin/7.1.3/main`, GitHub flow) is
retained only for the day a *non*-AI-assisted, architecture-relevant change is
ready — e.g. the charger or camera work, if it were rewritten without assistance.

### The open path: patch series to LKML / the subsystem maintainer

- Sent by **email** (`git send-email`), plain-text patches, to the subsystem lists.
- **Base per subsystem:** driver/machine patches on the subsystem's `-next`
  (for ASoC that is Mark Brown's `sound/for-next`); DTS patches on fresh torvalds
  mainline (routed to `linux-arm-msm` + the qcom DT maintainers via
  `get_maintainer.pl`).
- **AI provenance is a documented requirement, not an open question** — see
  "Authorship and provenance" below. Two in-tree documents govern it and both must
  be satisfied: `coding-assistants.rst` (the `Assisted-by:` trailer, no AI
  `Signed-off-by`) and `generated-content.rst` (disclose what the tool did, in the
  cover letter).

**The audio series is a genuinely good upstream candidate**, and better than it
looks from inside the FP3 project. `wcd9335.c` in mainline has **no jack
registration at all** — no `snd_soc_jack`, no `set_jack`, nothing. That gap affects
every WCD9335 board in the tree, not just the FP3:

```
apq8096-db820c.dts              <- DragonBoard 820c, a reference board
msm8996-oneplus-common.dtsi     <- OnePlus 3 / 3T
msm8996-xiaomi-common.dtsi, -gemini.dts
msm8996pro-xiaomi-natrium.dts, -scorpio.dts
sdm632-fairphone-fp3.dts
```

Lead with that framing, not with "this fixes my phone".

All destinations share the three shaping rules below.

---

## The three maintainer rules (verbatim intent)

These came directly from the msm8953-mainline maintainer and **override any
instinct to over-split**:

### 1. One branch per subsystem — not sub-split within it

Separate branches for **camera, charger, audio, modem** are fine and expected.
Splitting *audio* into several submission branches
(`wcd9335-txfe`, `wcd9335-mbhc`, `wcd9335-dmic`, …) is "too complicated and not
useful" — do **not** do it. One `submit/audio` branch carries the whole audio
story.

### 2. Reduce the number of commits per task

The fork's topic branches accumulate one commit per thing you learned. When the
change is *fixing existing code*, collapse those discovery steps into few,
well-formed commits. Fifteen incremental commits become a handful of logical ones.
Keep a genuinely standalone bugfix as its own commit (so it can carry `Fixes:`),
but squash the "and then I also had to…" follow-ups into their final form.

### 2b. Split the import from the invention, and make the import traceable

Two rules, and the first one is structural:

**Never mix imported code and new work in one commit.** If a patch carries
somebody else's code *and* your addition to it, the reviewer cannot see which is
which, `git blame` credits you for their lines, and a revert takes out both. So:
one commit that brings the foreign code in, unchanged and attributed; a second
commit that changes it. The pair also documents itself — the diff of the second
commit *is* the answer to "what did you actually do?".

**Cite an import so it can be found without you.** A cherry-pick across repos
loses the original SHA, the author and the date; git records only that *you*
committed it. Reconstruct all of it in the message:

```
The driver comes from <repo URL>, branch <branch>, commit <sha> ("<subject>"),
authored by <name(s)> on <YYYY-MM-DD>; it is not in Linus' tree.
```

Take the fields from the source, never from memory:
`git log -1 --format='%H %an <%ae> %ad %s' --date=short <ref>`. Where the source
is a mailing-list series rather than a repo, `Link:` the cover letter instead of
the SHA. Keep the original copyright and `MODULE_AUTHOR` lines in the file, and
say in the message that you did — and where the code is *substantially* still
theirs, the honest move is to keep **them** as the patch author
(`git commit --author`) and describe your changes in the follow-up commit.

Then, for your own commits, a provenance paragraph splitting the change three
ways:

| kind | how to say it |
|---|---|
| **taken from someone** | name the source concretely enough to check: whose tree/driver/DT, which file, which node or function. "Qualcomm's downstream `pmi632.dtsi`, where the same channel appears as `chan@4a`" — not "from downstream" |
| **reused from the tree** | say the mechanism was already there and you only pointed at it. "reuses `SCALE_HW_CALIB_THERM_100K_PULLUP`, already used by the AMUX_THM channels" |
| **new here** | say so plainly, and what it was modelled on if anything. "new here, modelled on this driver's existing `vbat_chan` handling — same optional `devm_iio_channel_get()`, same `-EPROBE_DEFER` passthrough" |

Why this is worth the lines:

- **it separates the trustworthy from the guessed.** A vendor-sourced number and
  a number read off an oscilloscope carry different risk, and only the commit can
  record which this is;
- **it front-runs the objection.** Where you knowingly took an approximation —
  the generic thermistor curve instead of the vendor's per-pack table — say so,
  with the measured size of the error and what it is therefore *not* good enough
  for. A reviewer who finds that themselves reads it as a bug; a reviewer who is
  told reads it as a judgement call;
- **the person reading your patch may be the person you took it from.**

Trailer forms, the DCO rules and the four citation situations are in
[Authorship and provenance](#authorship-and-provenance); the repo's
`docs/kernel/README.md` and `docs/sensors/README.md` are organised by the same
three-way split, so keep the commit and the doc saying the same thing.

### 3. Never mix DTS with driver code in one commit

`.c`/`.h` (driver/logic) and `.dts`/`.dtsi` (board wiring) go in **separate
commits**. See the next section for why — this one is non-negotiable and is the
single most common thing that gets a series bounced.

---

## Why DTS is separate from driver code

- **DTS = Device Tree Source** — data, not code. It describes *what hardware is on
  this board and how it is wired* (which chips, at which register address / IRQ /
  GPIO / clock / regulator / bus address, what each pin does). The kernel reads it
  at boot. It is board-specific: "on the FP3 the WCD9335 is on SLIMbus, these are
  the mic-bias supplies, these the MBHC thresholds."
- **Driver (`.c`/`.h`) = the logic** that works on *any* board that has the chip.
  `wcd9335.c` knows how to drive the codec whether it sits in an FP3 or a
  DragonBoard.
- They must be separate commits because:
  1. **Different maintainers / trees.** Driver → ASoC (Mark Brown); DTS →
     qcom/SoC (`linux-arm-msm`). A mixed commit cannot go to both trees.
  2. **Different merge/backport cadence.** A driver fix may go to `stable`; the DTS
     change may not. Separable only if separate commits.
  3. **Bisect / readability.** A regression hunt is cleaner when a commit is either
     "the logic changed" or "the hardware description changed", not both.
  4. **Reuse.** The generic driver change helps other boards; the DTS helps only
     the FP3. Kept apart, the driver can be upstreamed on its own.

Rule of thumb: **`.c`/`.h` in one commit, `.dts`/`.dtsi` in another — never
together.**

---

## How finely to split the DTS commits

Separating DTS from driver is only half of it — the DTS changes themselves have a
granularity convention, and it depends on whether the board is new or existing:

- **New device (the `.dts` does not exist yet):** put all the working nodes into
  **one commit**, conventionally titled *"arm64: dts: qcom: <soc>-<board>: add …"*
  (an "initial dts"). You are not enabling one feature at a time; you are landing
  the board.
- **Existing device (the `.dts` is already in mainline) enabling new features:**
  add a **separate DTS commit per feature/subsystem** — one for audio, one for
  charger, one for camera, one for modem, and so on. Do **not** fold different
  subsystems' DTS wiring into a single commit.

The FP3 is the **existing-device** case: `sdm632-fairphone-fp3.dts` is already
upstream, so each subsystem enables its hardware through its **own** per-subsystem
DTS commit. Keep the **audio DTS commit and the modem DTS commit separate**, even
when unsure whether they could be combined — the per-feature split is the safe
default.

### Measured against mainline, not asserted

The rules above were checked against the actual commit history of qcom device
trees in `torvalds/linux`, not inferred from the FP3 alone. What the history
shows:

**The FP3's own upstream `.dts` history is the textbook case** — an initial commit
landing the board, then one commit per feature, in the settled naming form
`arm64: dts: qcom: sdm632-fairphone-fp3: <verb> <thing>`:

```
arm64: dts: qcom: sdm632: Add device tree for Fairphone 3   <- initial dts, one commit
arm64: dts: qcom: sdm632: fairphone-fp3: add touchscreen
arm64: dts: qcom: sdm632-fairphone-fp3: Add NFC
arm64: dts: qcom: sdm632-fairphone-fp3: Add notification LED
arm64: dts: qcom: sdm632-fairphone-fp3: Enable WiFi/Bluetooth
arm64: dts: qcom: sdm632-fairphone-fp3: Enable LPASS
arm64: dts: qcom: sdm632-fairphone-fp3: enable USB-C port handling
arm64: dts: qcom: sdm632-fairphone-fp3: Enable vibrator
arm64: dts: qcom: sdm632-fairphone-fp3: Enable modem
arm64: dts: qcom: sdm632-fairphone-fp3: Enable display and GPU
arm64: dts: qcom: sdm632-fairphone-fp3: Add camera fixed regulators
arm64: dts: qcom: sdm632-fairphone-fp3: Enable CCI and add EEPROM
```

**The canonical "add audio to an existing board" commit** is
`b7b734286856 ("arm64: dts: qcom: sdm845-oneplus-*: add audio devices")`: the
entire audio wiring for the OnePlus 6 and 6T — sound card, DAI links, codec,
speaker/headphone routing — as **one commit**, 266 added lines across three
`.dts`/`.dtsi` files, **zero driver files**. That is exactly the shape the audio
DTS commit should have.

Three refinements the FP3 history forces on the rule as stated above:

1. **A subsystem may legitimately span more than one DTS commit** when there are
   distinct logical steps. Camera took two — *"Add camera fixed regulators"* then
   *"Enable CCI and add EEPROM"*. So the rule is really **one logical step per
   commit**; "one per subsystem" is the common case, not a ceiling. Do not
   artificially weld two genuinely separate steps together to hit a count.
2. **Closely-related blocks may share a commit** when they are enabled by the same
   act — *"Enable display and GPU"*, *"Enable CCI and add EEPROM"*. The test is
   whether they are one hardware-enablement story, not whether they are one
   subsystem.
3. **Style and cleanup never ride along with functional changes.** They get their
   own commits: *"Move status properties last"*, *"Add newlines between regulator
   nodes"*. If a reviewer asks for reformatting, that is a separate patch.

**Verb convention** (visible throughout the history above): **"Enable X"** when the
node already exists in the SoC `.dtsi` and the board turns it on / wires it up;
**"Add X"** when the commit introduces a new node. The FP3 audio work is the former
— `Enable LPASS` already landed, so the WCD9335 commit follows that lineage.

Re-verify rather than trusting this snapshot; conventions drift. Note that the
local fork checkout is **shallow** (`git log` on a path returns a single commit),
so mine the history over the API instead:

```sh
# per-board dts history, straight from mainline
gh api "repos/torvalds/linux/commits?path=arch/arm64/boot/dts/qcom/<board>.dts&per_page=100" \
  --jq '.[] | .commit.message | split("\n")[0]'

# what did a given dts commit actually touch?
gh api repos/torvalds/linux/commits/<sha> \
  --jq '"files: \(.files|length) +\(.stats.additions)/-\(.stats.deletions)", (.files[].filename)'
```

Note this refines "reduce the number of commits" for DTS: it means *per logical
step*, not *everything in one*. Within the audio branch, all the audio `.dts`
wiring is a single commit unless it contains two genuinely separate enablement
steps; it must never absorb charger/camera/modem DTS.

---

## Worked example: the audio series (15 → 8 commits, one branch)

Verified against the branch, not recalled: the audio wip branch had exactly **15**
commits on top of its base, and three of them **mix** DTS with driver
code — each touches `arch/arm64/boot/dts/qcom/sdm632-fairphone-fp3.dts` *plus* a
driver file:

| commit | driver file it also touches |
|---|---|
| `81d06a36` "SLIMbus WCD9335 framer bring-up via QDSP6SS quirk + codec graft" | `drivers/remoteproc/qcom_q6v5_pas.c` |
| `eb2c18d7` "clear QDSP6SS framer quirk bit3 right before capability" | `drivers/slimbus/qcom-ngd-ctrl.c` |
| `ffef69f4` "apq8016_sbc: add SLIMbus backend support + FP3 WCD9335 card" | `sound/soc/qcom/apq8016_sbc.c` |

Reshaped as one `submit/audio` branch — **based on `sound/for-next`, not on
`7.1.3/main`**, since LKML is the destination — driver commits first, one
consolidated DTS commit last:

1. `remoteproc: qcom_q6v5_pas: apply QDSP6SS framer quirk for WCD9335 SLIMbus`
   — driver half of the framer bring-up.
2. `slimbus: ngd: clear the QDSP6SS framer quirk bit before capability exchange`
   — driver half of the NGD change.
3. `ASoC: qcom: apq8016_sbc: add SLIMbus backend, the FP3 WCD9335 card and the digital-mic widgets`
   — machine-driver: SLIMbus backend + FP3 card + DMIC widgets.
4. `ASoC: wcd9335: fix codec init (efuse sense state and MCLK_CFG)`
   — two init fixes squashed.
5. `ASoC: wcd9335: release the TX front-end hold after the ADC is up`
   — standalone capture bugfix; carries `Fixes:` (and `Cc: stable` on the LKML path).
6. `ASoC: wcd9335: take the mic bias voltage and DMIC clock rate from the DT`.
7. `ASoC: wcd9335: add MBHC headset jack detection`
   — the revived 2018 MBHC series adapted for the FP3.
8. `arm64: dts: qcom: sdm632-fairphone-fp3: wire up WCD9335 audio`
   — the single DTS commit: the `.dts` halves of the three mixed commits plus all
   the pure-DTS ones (framer/codec graft node, MCLK routing + pinmux, analog
   mic-bias supplies, DMIC wiring, MBHC button thresholds).

Result: **7 driver commits + 1 DTS commit**, one branch, nothing mixed.

---

## Splitting a mixed commit in practice

Don't fight `git` to bisect a mixed commit — rebuild it. Cherry-pick without
committing, drop the wrong-domain files from the index, commit the rest, and
gather all the DTS hunks into the final DTS commit:

```sh
git checkout -b submit/audio <base>            # sound/for-next for ASoC drivers

git cherry-pick -n <mixed-sha>                 # stage everything, don't commit
git restore --staged arch/arm64/boot/dts/qcom/sdm632-fairphone-fp3.dts
git checkout -- arch/arm64/boot/dts/qcom/sdm632-fairphone-fp3.dts   # driver-only left
git commit -s -m 'remoteproc: qcom_q6v5_pas: apply QDSP6SS framer quirk ...'
# ...repeat for the other driver commits...
# ...then apply every .dts change and make ONE dts commit at the end.
```

`git add -p` (stage by hunk, per domain) is the alternative when a single file
needs splitting.

---

## Rebasing the fork's work onto a newer base (worked, 7.0.9 → 7.1.3)

The concrete moves for porting a `wip/<old>/<category>` branch onto the current
integration base (e.g. `7.1.3/main`) and reshaping it into `submit/<new>/<category>`.
The surrounding bookkeeping — which branches to create, delete and push, in what
order — is in
[`docs/rolling-a-new-base.md`](https://github.com/llg179/fp3-pmaports/blob/main/docs/rolling-a-new-base.md);
what follows is only the git surgery:

- **The base is a SHA, not a tracking ref.** `msm8953-mainline` branch names
  contain a slash (`7.1.3/main`), so `git fetch origin '7.1.3/main'` leaves it in
  `FETCH_HEAD` — there is usually **no `origin/7.1.3/main` ref**. Resolve the SHA
  once (`git rev-parse FETCH_HEAD`) and branch from that. **Gotcha that bites:**
  `git checkout -b submit/x origin/7.1.3/main` *fails* ("not a commit"), and if you
  chained `cherry-pick`/`commit` after it in one script they run **on whatever
  branch you were already on** — you silently commit onto the wrong branch. Check
  `git branch --show-current` after a failed checkout.

- **Triage conflict risk before you start.** For each file the topic branch
  touches: `git diff --numstat <old-base> <new-base> -- <file>`. `0  0` means the
  file is identical across the bump → cherry-picks apply clean. A file **absent**
  in the new base (a new driver like `imx363.c`, `qcom_smbx.c`) is a clean *add*,
  no collision. Only the files with real drift need hand-resolution — in the 7.1.3
  bump that was just the two framer files (`qcom_q6v5_pas.c`, `qcom-ngd-ctrl.c`);
  everything else (`wcd9335.c`, `apq8016_sbc.c`, `q6voice-dai.c`, the `.dts`) was
  `0 0`.

- **"Base DTS identical" shortcut.** When the board `.dts` is `0 0` across the
  bump, you do **not** need to replay the DTS commits: take the final DTS wholesale
  from the topic branch and commit it as the one DTS commit —
  `git checkout <topic> -- arch/.../<board>.dts`. For an *integration* test build,
  take the combined DTS the same way from `integration/<base>`.

- **New-file driver, consolidated.** For a driver absent upstream, don't cherry-pick
  its nine discovery commits — take the final file(s) and make one commit:
  `git checkout <topic> -- drivers/media/i2c/imx363.c .../Kconfig .../Makefile`,
  then one `media: i2c: add … driver` commit. (`Kconfig`/`Makefile` apply clean when
  their base is `0 0`.)

- **Swap the trailer while reshaping.** Do the `Co-authored-by:` →
  `Assisted-by: Claude:claude-opus-4-8` swap in the same pass:
  `git log -1 --format=%B <c> | sed '/^Co-authored-by: Claude/d;/^Signed-off-by:/a Assisted-by: Claude:claude-opus-4-8'` → `git commit -F -`.

- **Fixing a non-tip commit** (e.g. a checkpatch/warning fix that belongs in commit
  1 of 8): no interactive rebase here. `git tag _bk <branch>`, `git reset --hard
  <base>`, cherry-pick commit 1 with `-n`, edit, commit; cherry-pick the rest;
  confirm `git diff --stat _bk HEAD` shows only your intended lines, then drop the
  tag. Reordering commits is the same move (cherry-pick in the target order; verify
  the tree is byte-identical to the backup).

### The two framer conflict resolutions (patterns to reuse)

- **`of_device_id` table (`qcom_q6v5_pas.c`).** The new base already had a
  `qcom,msm8953-adsp-pil` row (pointing at the generic resource) plus newer SoC
  rows and different brace spacing. Resolution: **keep the whole HEAD block** (its
  new rows + formatting), change only the one `.data =` to your quirk descriptor.
  Don't take "yours" wholesale — you'd drop the base's new entries.

- **Refactored `probe()` (`qcom-ngd-ctrl.c`).** The base had changed
  `platform_get_irq` to store in a new `int irq;` local. Two conflict hunks:
  (1) declarations — **keep both** (`int irq;` *and* your `u32 quirk_reg;`);
  (2) the body — keep HEAD's `irq = platform_get_irq(...)` handling and **insert
  your quirk block before it** (drop your base's `ret = platform_get_irq` variant,
  since HEAD now uses `irq` downstream). General rule: when the base refactored the
  surrounding code, adopt the base's version and re-insert your addition into it.

### checkpatch false positives seen on this hardware

Don't "fix" these — they are correct as-is:
- **`ENOTSUPP` in a machine driver** — `snd_soc_dai_set_channel_map()` returns
  `-ENOTSUPP`; the `if (ret && ret != -ENOTSUPP)` idiom must match it. `EOPNOTSUPP`
  would be wrong.
- **`slim217,...` "undocumented vendor"** — SLIMbus compatibles are `slimMFG,PID`
  (manufacturer id), not a vendor-prefix; checkpatch's heuristic doesn't know that.
- **"DT compatible … appears un-documented"** — real only in that a YAML binding is
  still owed (a genuine follow-up for LKML), not a code defect.

Trailing whitespace / space-before-tab in a reverse-engineered register table
*are* real (checkpatch ERRORs) — strip them (`sed -i 's/[ \t]*$//' ; sed -i
's/ \+\t/\t/g'`), plus `MODULE_LICENSE("GPL v2")`→`"GPL"`.

---

## The rebase-and-retest gate (do not skip before submitting)

The fork's work was built and verified on the **7.0.9** base. The submission
targets a *different, newer* base — `sound/for-next` for the driver patches, fresh
torvalds for the DTS — so the branch must be rebased across that bump, and a base
bump **can break things silently** (compiles clean, does not work). Before sending:

1. **Rebase** onto the real target base, resolving conflicts **commit by commit**.
2. **Rebuild** — catches API churn (compile errors).
3. **CONFIG check** — every symbol the build relies on must still exist on the new
   base; `olddefconfig` drops unknown symbols without a word (this is exactly the
   `DRM_PANEL_*_HX83112B` rename trap). A feature can vanish with zero build
   warnings.
4. **Functional test on device** — run `fp3-selftest`
   (`fp3-pmaports/tests/fp3-selftest`, with its `checks/` and `baseline/`). This is
   the only thing that catches the silent class: zeroed mic, dead DAPM route,
   missing MBHC IRQ, absent camera graph. Cross-ref the `fp3-kernel-test` skill for
   the deploy/capture loop.

Only a green functional run gates the submission — "it compiled" is not enough.
This matters more than usual here: `generated-content.rst` invites maintainers to
demand extra testing of tool-assisted work, so arriving with a measured result is
the difference between a review and a dismissal.

---

## Authorship and provenance

The kernel documents exactly how to acknowledge AI assistance. Verified in-tree,
with line numbers, not quoted from memory — **two** documents apply, both listed
in `Documentation/process/index.rst`:

| document | what it governs |
|---|---|
| `process/coding-assistants.rst` | the `Assisted-by:` trailer; AI must not sign off |
| `process/generated-content.rst` | what you must **disclose**, and maintainer discretion |
| `process/submitting-patches.rst` | §"Using Assisted-by:" (line 637) — the requirement |

`submitting-patches.rst:641` is the operative sentence: you "need to acknowledge
that use by adding an Assisted-by tag. Failure to do so **may impede the
acceptance of your work**."

### What `generated-content.rst` additionally requires

This is the half that is easy to miss, and it is the half that decides whether a
maintainer engages. It applies "when a meaningful amount of content in a kernel
contribution was not written by a person in the Signed-off-by chain". You are
expected to be transparent in the **cover letter** about:

- which tools were used;
- the prompts — verbatim if the code came from a short set of them, otherwise a
  summary of the prompts and the nature of the assistance;
- **which portions** of the contribution the tool affected;
- how the result was **tested**, and with what.

It also states plainly what you are signing up for: *"You are expected to
understand and to be able to defend everything you submit. If you are unable to do
so, then do not submit the resulting changes."* And maintainers explicitly may
**reject the series outright**, ask for extra testing, review it at lower
priority, or ask you to explain the code to prove you understand it. Budget for
that reaction rather than being surprised by it.

For the FP3 series the strongest disclosure is the **on-device evidence**: the
MBHC work was verified over 14 jack edges across 6 insert/remove cycles with no
drift, via `evtest --query event5 SW_HEADPHONE_INSERT`. Lead the testing paragraph
with that.

**The `Assisted-by:` trailer (kernel-required form).** Any commit that used an AI
coding assistant must carry, as a trailer:

```
Assisted-by: AGENT_NAME:MODEL_VERSION [TOOL1] [TOOL2]
```

- `AGENT_NAME` — the AI tool/framework; `MODEL_VERSION` — the specific model.
  The in-tree example is `Assisted-by: Claude:claude-3-opus coccinelle sparse`.
- `[TOOL1] [TOOL2]` — optional *specialised analysis* tools actually used
  (coccinelle, sparse, smatch, clang-tidy). **Basic tools (git, gcc, make,
  editors) are NOT listed.**
- **Name the model that actually did the work — do not hardcode one.** The FP3
  history spans several: the audio/MBHC work was done with Opus 4.8
  (`Assisted-by: Claude:claude-opus-4-8`), later sessions run Opus 5
  (`Assisted-by: Claude:claude-opus-5`). A commit reshaped today by a different
  model than the one that wrote it should name the model that produced the code
  being submitted. Check which model is running before writing the trailer rather
  than copying the string from this file.
- Append e.g. `sparse smatch` only if such a tool was actually run on the patch.

**The AI must NOT have a `Signed-off-by`.** Only a human can legally certify the
DCO. The human submitter reviews the AI-generated code, ensures licensing
compliance, adds *their own* `Signed-off-by`, and takes full responsibility.
Failure to acknowledge the assistance "may impede the acceptance of your work."

**So the trailer block for an upstream-bound commit is:**

```
Signed-off-by: Lajosházi, László Gergely <lajoshazilg@gmail.com>
Assisted-by: Claude:claude-opus-4-8
```

i.e. **replace** the fork's `Co-authored-by: Claude …` line with `Assisted-by:`.
`Co-authored-by:` is a GitHub convention, not a kernel trailer — and its kernel
counterpart `Co-developed-by:` is *worse*, not better: `submitting-patches.rst`
requires every `Co-developed-by:` to be **immediately followed by a
`Signed-off-by:` of that co-author**, which an AI cannot legally provide. So
`Co-developed-by: Claude …` is structurally invalid upstream. `Assisted-by:`
exists precisely to fill that gap: attribution without an authorship claim.

- **Fork commits (llg179/linux):** keep the fork rule — author
  `Lajosházi, László Gergely <lajoshazilg@gmail.com>` + `Signed-off-by:` +
  `Co-authored-by: Claude Opus 4.8 <noreply@anthropic.com>`, kernel comments in
  **English only**. That is the local convention (CLAUDE.md), unaffected.
- **Upstream submission (LKML):** swap `Co-authored-by:` → `Assisted-by:` naming
  the model actually used, and never let the AI carry a `Signed-off-by`. When
  rewriting the commits for the `submit/*` branch, do this swap as part of the same
  pass that splits the DTS out.

### Credit the work you build on, especially when it is not upstream yet

`Assisted-by:` covers the AI. It says nothing about the **humans** whose work a
patch reuses. The rule and the import/invention split are in
[§2b](#2b-split-the-import-from-the-invention-and-make-the-import-traceable);
this is the citation *form* for each of four situations:

| the source | how to cite it |
|---|---|
| an **in-tree** commit or driver you used as the skeleton | `commit e4802cb00bfe ("media: imx258: Add imx258 camera sensor driver")` — the standard 12-hex-plus-subject form. Keep the original copyright and `MODULE_AUTHOR` lines in the file, and say in the message that you did |
| a **posted but never merged** series you are reviving | name the author and the series in prose, plus `Link: https://lore.kernel.org/all/<message-id>/` to the cover letter. Verify the message-id resolves — patchwork's *"Series Link"* gives you the cover-letter id |
| a **downstream / vendor** tree (Qualcomm BSP, an OEM release) | name the exact file(s) — `msm8953-audio.dtsi`, `qpnp-smb5` — and `Link:` the published release the numbers were read out of |
| an **out-of-tree fork** driver you extend (msm8953-mainline, a Halium tree) | say plainly that the driver is not in mainline, name its authors, and link the commit in the tree that carries it |

Do **not** reach for `Co-developed-by:` to solve this: it requires a
`Signed-off-by:` from that person in the same patch, which you cannot produce for
someone who is not part of your submission. Prose plus `Link:` is the correct
tool.

Worked examples from this series, all four of them real omissions found by
auditing the branch before submission:

* `ASoC: wcd9335: add MBHC headset jack detection` said only "reviving the 2018
  series that was dropped before merge" — no name, no link. The series is
  **Srinivas Kandagatla's**, v3 of 2018-09-04, and `wcd9335.c` is
  *maintained by him*. Now: "based on the MBHC support in Srinivas Kandagatla's
  2018 WCD9335 series, which was posted together with the codec driver but
  dropped before that series was merged" +
  `Link: https://lore.kernel.org/all/20180904102500.30318-1-srinivas.kandagatla@linaro.org/`.
* `media: i2c: add Sony IMX363 image sensor driver` carries Intel's copyright
  because it is derived from `imx258.c`; the message now cites
  `commit e4802cb00bfe ("media: imx258: Add imx258 camera sensor driver")` and
  says which parts are new.
* `ASoC: qcom: apq8016_sbc: add SLIMbus backend …` follows the SLIMbus flow in
  `sound/soc/qcom/sdm845.c` — the code said so in a comment, the message did not.
* `arm64: dts: qcom: …: wire up WCD9335 audio` takes every address and value from
  Fairphone's published 4.9 sources; its camera and charger siblings said so and
  it did not. Now it does, with the GPL-release link.

An audit pass that surfaces the candidates cheaply, before the series goes out.
Read it as a **prompt list, not a verdict**: most hits will be legitimately your
own work, and the question to ask of each is only *"did any of this come from
somewhere else?"*

```sh
git log --format='%h %s' <base>..<branch> | while read h s; do
    git log -1 --format=%B "$h" \
      | grep -qiE 'Link:|Based on|Derived from|follows the|taken from|read out of|commit [0-9a-f]{12} \("' \
      || echo "no source cited: $h $s"
done
```

On the FP3 audio branch this prints 7 of 11 commits — and 6 of those 7 really are
original (a debounce found by measuring, a missing volume control, an init fix).
The one that was not is exactly the kind this catches: *"take the mic bias voltage
and DMIC clock rate from the DT"* reads its values out of Fairphone's downstream
`msm8953-audio.dtsi` and never said so.

**Audit the branches before submitting — some commits have no sign-off at all.**
The seven IMX363 camera commits on `integration/<base>` (`b00ba1f5`, `526d569e`,
`757b41e6`, `df906c4d`, `4beba115`, `1adc5540`, `0c5dd72e`) carry an **empty
trailer block**: no `Signed-off-by`, no attribution. Those are unsubmittable as-is,
independent of the AI question. Check every branch, not just the one being sent:

```sh
git log --format='%h|%s|%(trailers:key=Signed-off-by,valueonly,separator=;)|%(trailers:key=Assisted-by,valueonly,separator=;)' \
    <branch> ^origin/7.0.9/main
```

---

## Patch mechanics (the LKML email path)

These are the standard kernel mechanics the sources below spell out. Since LKML is
now the only open destination, all of them are mandatory — none are optional
GitHub-flow conveniences any more.

- **Base off a well-known point.** A stable or `-rc` tag on Linus' tree (driver
  patches on the subsystem `-next`). Never a random mid-tree commit.
- **`git commit -s`.** The `-s` adds *your* `Signed-off-by` (the DCO). Message in
  **imperative mood** ("add", not "added"), body wrapped at **~75 columns**. Add a
  `Fixes: <12-char-sha> ("subject")` tag when fixing a known commit, and `Cc:
  stable@vger.kernel.org` for a user-visible bugfix (e.g. the TX front-end hold).
- **DT is checked, not just compiled.** For device-tree work run the DT checks —
  `make dtbs_check` (and `make dt_binding_check` if you touch a binding). A commit
  that introduces DT warnings can be **reverted** (`maintainer-soc-clean-dts.rst`),
  so land it warning-free.
- **Bindings vs. DTS route differently.** A YAML **binding** doc
  (`Documentation/devicetree/bindings/…`) travels with the **driver** subsystem
  tree; the board **`.dts`** goes via the **SoC/qcom** tree. Same "don't mix"
  discipline, but know which of the two a given file is.
- **`scripts/checkpatch.pl --strict`** clean; **`scripts/get_maintainer.pl`** on
  the generated patch file to build the recipient set:
  ```sh
  git format-patch -o /tmp/pset <base>..submit/audio
  scripts/get_maintainer.pl /tmp/pset/0001-*.patch
  ```
- **Send with `git send-email`, inline — never as an attachment.** It applies the
  `[PATCH n/m]` subject prefix, the `---` separator and the trailers for you. A
  multi-patch series gets a `--cover-letter` (state the base and any
  driver→DTS dependency there).
- **`b4`** automates much of this (dependency tracking, checkpatch, formatting and
  sending) — worth using once the series grows.
- **Build in the pmOS chroot.** `pmbootstrap`'s `envkernel.sh` gives the
  reproducible cross-build the postmarketOS mainlining guide uses; the FP3 loop
  already builds via the `linux-fp3` package (cross-ref `fp3-kernel-test`).

---

## Pre-submit checklist

- [ ] Destination is **LKML** — msm8953-mainline will not merge AI-assisted work,
      pmOS bans it. No PR against `7.1.3/main`.
- [ ] Base is correct and fresh (driver → `sound/for-next`; DTS → fresh torvalds).
      Never `7.0.9/main`, never a stale mirror, never a shallow clone's idea of history.
- [ ] **One branch for the whole subsystem** (audio/camera/charger/modem), not sub-split.
- [ ] Commit count reduced; discovery steps consolidated; standalone bugfix kept apart.
- [ ] **No commit mixes `.dts`/`.dtsi` with `.c`/`.h`.**
- [ ] DTS split **per logical step**; no style/cleanup riding along with function.
- [ ] Rebased across the base bump; **rebuilt + CONFIG-checked + `fp3-selftest` green.**
- [ ] `scripts/checkpatch.pl --strict` clean; `scripts/get_maintainer.pl` used for
      the recipient set.
- [ ] DT work is **warning-free** (`make dtbs_check`, `make dt_binding_check` if a
      binding changed).
- [ ] Commits are `-s` signed, imperative-mood, body wrapped ~75 cols; `Fixes:`/`Cc:
      stable` on bugfixes.
- [ ] Human `Signed-off-by` on **every** commit — audit for the empty-trailer
      commits; **no `Signed-off-by` from the AI**; `Co-authored-by:` swapped to
      `Assisted-by:` naming the model that actually did the work.
- [ ] **Every borrowed piece is credited**: work taken from an unmerged series,
      a downstream tree, an out-of-tree fork or an in-tree driver used as a
      skeleton names its authors and carries a `Link:`/`commit …` reference.
- [ ] Cover letter carries the `generated-content.rst` disclosure: tools, prompts
      (or a summary), which portions were tool-affected, and how it was tested.
- [ ] Cover note states the base ("applies to sound/for-next").
- [ ] For a series with a driver→DTS dependency, the DTS commit/patch notes it.

---

## See also — the source material

This skill consolidates FP3-specific decisions on top of existing, authoritative
guides. When in doubt, these are the ground truth:

**The process (worked examples closest to this task)**
- postmarketOS Mainlining guide: <https://wiki.postmarketos.org/wiki/Mainlining>
- Per-SoC bring-ups (same Qualcomm shape as the FP3):
  <https://wiki.postmarketos.org/wiki/MSM8916_Mainlining>,
  <https://wiki.postmarketos.org/wiki/MSM8996_Mainlining>,
  <https://wiki.postmarketos.org/wiki/SDM845_Mainlining>
- msm8953-mainline kernel (points to the kernel docs, no repo-specific flow):
  <https://github.com/msm8953-mainline/linux>

**The authoritative in-tree docs (mandatory reading before v1)**
- Submitting patches — the essential guide:
  <https://docs.kernel.org/process/submitting-patches.html>
- Submit checklist: <https://docs.kernel.org/process/submit-checklist.html>
- DT binding submission:
  <https://docs.kernel.org/devicetree/bindings/submitting-patches.html>
- SoC DTS conventions (the "don't mix / warning-free / route by tree" rules):
  <https://docs.kernel.org/process/maintainer-soc-clean-dts.html>
- AI attribution (`Assisted-by:`):
  <https://docs.kernel.org/process/coding-assistants.html>
- Tool-generated content — the disclosure rules and maintainer discretion:
  <https://docs.kernel.org/process/generated-content.html>

**The policies that closed the other two doors**
- postmarketOS AI policy (total ban):
  <https://docs.postmarketos.org/policies-and-processes/development/ai-policy.html>
- msm8953-mainline maintainer statement, 2026-07-25:
  <https://github.com/msm8953-mainline/linux/issues/197>

**First-patch tutorials (informal but complete)**
- <https://opensource.com/article/18/8/first-linux-kernel-patch>
- <https://www.linaro.org/blog/becoming-a-kernel-developer-part1-posting-your-first-patch/>
- <https://nickdesaulniers.github.io/blog/2017/05/16/submitting-your-first-patch-to-the-linux-kernel-and-responding-to-feedback/>
