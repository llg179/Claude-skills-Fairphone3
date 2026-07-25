---
name: msm8953-mainline-pr
description: >-
  How to turn the FP3 (MSM8953/SDM632) local kernel work — the fp3-integration
  topic branches: audio/wcd9335, camera/imx363, charger/smb2, voice — into a
  clean submission for the msm8953-mainline project (github.com/msm8953-mainline/linux),
  and how the same work would later go upstream to LKML. Encodes the maintainer
  guidance received on the msm8953-mainline Matrix channel: one branch per
  subsystem (not sub-split), few well-formed commits, and never mix DTS with
  driver code. Use whenever preparing a pull request or patch series from the
  llg179/linux fork.
---

# msm8953-mainline pull-request preparation

This is a **process** skill: how to take device-support work that currently lives
on the personal fork (`github.com/llg179/linux`, the `fp3-7.0.9-*` topic branches
and `fp3-integration`) and shape it into something a maintainer will accept —
either as a **pull request to the msm8953-mainline project** or, later, as a
**patch series to LKML**. The audio/WCD9335 series is the running worked example;
its exact commit SHAs age, so treat them as illustrations of the *shape*, not as
current fact.

The whole point: the fork's topic branches are ordered by *discovery* (one commit
per thing you learned, DTS and driver interleaved). Upstream wants them ordered by
*logic* (few commits, each one self-contained, DTS and driver never in the same
commit). This skill is the translation.

---

## Know the versioning before you pick a base

A recurring trap: the `msm8953-mainline` branch names look like a private version
scheme, but they are **real torvalds versions**.

- Linus bumped the major after 6.19 → `7.0` → `7.1`. So `Linux 7.1.3` is a **real
  mainline stable release** (tagged 2026-07-04), not a relabel.
- `msm8953-mainline` names each integration branch after the **real mainline base
  it sits on**: `7.0.9/main` is built on torvalds `7.0.9`, `7.1.3/main` on torvalds
  `7.1.3`. The Makefile `VERSION/PATCHLEVEL/SUBLEVEL` in those branches is the
  genuine upstream one.
- Verify, don't assume, which is newest: fetch the branch and check. As of this
  writing `7.1.3/main` is the newest integration branch (≈232 device commits on
  top of torvalds 7.1.3).

Verification one-liner (from a checkout of the fork with `origin` =
msm8953-mainline):

```sh
git fetch origin '7.1.3/main'
git show FETCH_HEAD:Makefile | head -4 | grep -E 'VERSION|PATCHLEVEL|SUBLEVEL'
# is a known-good mirror an ancestor? proves it is the same linear torvalds line:
git merge-base --is-ancestor <torvalds-mirror-ref> FETCH_HEAD && echo "linear torvalds"
```

**Watch for a stale mirror.** A local `fork/master` (or any personal torvalds
mirror) may be frozen at an old release (e.g. 6.19) while upstream has moved on to
7.1.x. Re-sync it before using it as a base — never rebase onto a stale mirror.

---

## Two destinations, two rule-sets

Decide first *where* the work is going, because it changes the base and the AI
handling. Do not guess — the msm8953-mainline maintainers will tell you on the
Matrix channel which they want.

### A. Pull request to msm8953-mainline (the near-term, easier path)

- It is a **GitHub PR** against the project's current integration branch.
- **Base = the target branch itself**, e.g. `origin/7.1.3/main`. (Not
  `sound/for-next`, not a bare torvalds tag — a PR merges into that branch, so you
  branch from it.)
- **No AI ban.** This is *not* postmarketOS. AI-assisted code is fine here, and the
  `Co-authored-by: Claude …` trailer can stay exactly as-is. None of the LKML AI
  disclosure machinery is needed.
- This is the recommended first target: it gets the work into the community
  integration tree that the `linux-fp3-709` package can then track, without the
  months-long LKML review cycle.

### B. Patch series to LKML / the subsystem maintainer (the eventual, harder path)

- Sent by **email** (`git send-email`), plain-text patches, to the subsystem lists.
- **Base per subsystem:** driver/machine patches on the subsystem's `-next`
  (for ASoC that is Mark Brown's `sound/for-next`); DTS patches on fresh torvalds
  mainline (routed to `linux-arm-msm` + the qcom DT maintainers via
  `get_maintainer.pl`).
- **AI provenance becomes a live question.** The kernel has no blanket ban, but
  `Signed-off-by` is the DCO legal certification, and a machine `Co-authored-by`
  trailer is contentious (an AI cannot certify the DCO). Do **not** carry the
  trailer over blindly. Ask the subsystem/maintainer for the expected disclosure
  form (a cover-letter paragraph vs. a trailer) and **verify the exact current
  convention against the live kernel docs** before sending v1 — do not trust
  second-hand notes about specific trailer names or doc filenames.

Both destinations share the three shaping rules below.

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

**Verify the current convention** rather than trusting this note: read the commit
history of comparable mainline device trees (other qcom boards under
`arch/arm64/boot/dts/qcom/`) and match how they granularise `.dts` changes.

```sh
# how do other qcom boards split their dts commits?
git log --oneline -- arch/arm64/boot/dts/qcom/ | grep -iE 'dts.*(audio|charger|camera|modem|codec)'
git log --oneline -- arch/arm64/boot/dts/qcom/<some-other-board>.dts   # one board's dts history
```

Note this refines "reduce the number of commits" for DTS: it means *per feature*,
not *everything in one*. The two rules meet at **one DTS commit per subsystem** —
which is exactly what "one branch per subsystem" already implies. Within the audio
branch, therefore, all the audio `.dts` wiring is a single commit; it simply must
not absorb charger/camera/modem DTS.

---

## Worked example: the audio series (15 → 8 commits, one branch)

The `fp3-7.0.9-audio` branch had 15 discovery-ordered commits, three of which
**mixed** DTS and driver (`81d06a36` touched `qcom_q6v5_pas.c` *and* the FP3
`.dts`; `eb2c18d7` touched `slimbus/ngd` *and* the `.dts`; `ffef69f4` touched
`apq8016_sbc.c` *and* the `.dts`). Reshaped onto `origin/7.1.3/main` as one
`submit/audio` branch, driver commits first, one consolidated DTS commit last:

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
git checkout -b submit/audio origin/7.1.3/main

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

## The rebase-and-retest gate (do not skip before a PR)

The fork's work was built and verified on the **7.0.9** base. A PR targets
**7.1.3/main**, so the branch must be rebased across that base bump — and a base
bump **can break things silently** (compiles clean, does not work). Before opening
the PR:

1. **Rebase** onto `origin/7.1.3/main`, resolving conflicts **commit by commit**.
2. **Rebuild** — catches API churn (compile errors).
3. **CONFIG check** — every symbol the build relies on must still exist in 7.1.3;
   `olddefconfig` drops unknown symbols without a word (this is exactly the
   `DRM_PANEL_*_HX83112B` rename trap). A feature can vanish with zero build
   warnings.
4. **Functional test on device** — run `fp3-selftest` (the regression suite in
   `fp3-pmaports/tests`). This is the only thing that catches the silent class:
   zeroed mic, dead DAPM route, missing MBHC IRQ, absent camera graph. Cross-ref
   the `fp3-kernel-test` skill for the deploy/capture loop.

Only a green functional run gates the PR — "it compiled" is not enough.

---

## Authorship and provenance

- Every commit keeps the fork's authorship rule: author
  `Lajosházi, László Gergely <lajoshazilg@gmail.com>` + `Signed-off-by:`, kernel
  comments in **English only**.
- **msm8953-mainline PR:** keep the `Co-authored-by: Claude Opus 4.8
  <noreply@anthropic.com>` trailer — no AI ban there.
- **LKML path:** revisit the trailer and disclosure form with the maintainer
  first (see destination B); verify the current convention against live kernel
  docs before v1.

---

## Pre-submit checklist

- [ ] Destination chosen (msm8953-mainline PR vs LKML) — confirmed with the channel.
- [ ] Base is correct and fresh (PR → `origin/7.1.3/main`; LKML driver →
      `sound/for-next`, DTS → fresh torvalds). Never `7.0.9/main`, never a stale mirror.
- [ ] **One branch for the whole subsystem** (audio/camera/charger/modem), not sub-split.
- [ ] Commit count reduced; discovery steps consolidated; standalone bugfix kept apart.
- [ ] **No commit mixes `.dts`/`.dtsi` with `.c`/`.h`.**
- [ ] Rebased across the base bump; **rebuilt + CONFIG-checked + `fp3-selftest` green.**
- [ ] `scripts/checkpatch.pl --strict` clean; `scripts/get_maintainer.pl` used for
      the recipient set (LKML) or the PR targets the right branch (msm8953-mainline).
- [ ] Authorship + `Signed-off-by` on every commit; AI trailer handled per destination.
- [ ] Cover note states the base ("based on 7.1.3/main" / "applies to sound/for-next").
- [ ] For a series with a driver→DTS dependency, the DTS commit/patch notes it.
