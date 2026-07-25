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
- **No AI ban.** This is *not* postmarketOS — AI-assisted code is fine here. Since
  the project tracks mainline, still use the kernel-standard `Assisted-by:` tag
  (not `Co-authored-by:`) and keep the AI off `Signed-off-by` — see "Authorship and
  provenance". If the maintainer explicitly says plain `Co-authored-by` is fine for
  the PR, follow them; otherwise the mainline form is the safe default.
- This is the recommended first target: it gets the work into the community
  integration tree that the `linux-fp3-709` package can then track, without the
  months-long LKML review cycle.

### B. Patch series to LKML / the subsystem maintainer (the eventual, harder path)

- Sent by **email** (`git send-email`), plain-text patches, to the subsystem lists.
- **Base per subsystem:** driver/machine patches on the subsystem's `-next`
  (for ASoC that is Mark Brown's `sound/for-next`); DTS patches on fresh torvalds
  mainline (routed to `linux-arm-msm` + the qcom DT maintainers via
  `get_maintainer.pl`).
- **AI provenance is a documented requirement, not an open question.** The kernel
  has a standard (see the "Authorship and provenance" section below): replace the
  `Co-authored-by: Claude …` trailer with an `Assisted-by:` tag, and the AI must
  **not** carry a `Signed-off-by`. Only the human submitter signs off and certifies
  the DCO. Failure to acknowledge the assistance "may impede the acceptance of your
  work" (`submitting-patches.rst`).

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

The kernel documents exactly how to acknowledge AI assistance — this is verified
against the 7.1.3 tree, not a guess: `Documentation/process/coding-assistants.rst`
and the "Using Assisted-by:" section of `Documentation/process/submitting-patches.rst`.

**The `Assisted-by:` trailer (kernel-required form).** Any commit that used an AI
coding assistant must carry, as a trailer:

```
Assisted-by: AGENT_NAME:MODEL_VERSION [TOOL1] [TOOL2]
```

- `AGENT_NAME` — the AI tool/framework; `MODEL_VERSION` — the specific model.
- `[TOOL1] [TOOL2]` — optional *specialised analysis* tools actually used
  (coccinelle, sparse, smatch, clang-tidy). **Basic tools (git, gcc, make,
  editors) are NOT listed.**
- For this project the tag is:

  ```
  Assisted-by: Claude:claude-opus-4-8
  ```

  (append e.g. `sparse smatch` only if such a tool was actually run on the patch).

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

- **Fork commits (llg179/linux):** keep the fork rule — author
  `Lajosházi, László Gergely <lajoshazilg@gmail.com>` + `Signed-off-by:` +
  `Co-authored-by: Claude Opus 4.8 <noreply@anthropic.com>`, kernel comments in
  **English only**. That is the local convention (CLAUDE.md), unaffected.
- **Upstream submission (LKML, and any msm8953-mainline PR that follows kernel
  norms):** swap `Co-authored-by:` → `Assisted-by: Claude:claude-opus-4-8`, and
  never let the AI carry a `Signed-off-by`. When rewriting the commits for the
  `submit/*` branch, do this swap as part of the same pass that splits the DTS out.
- If a maintainer explicitly says the plain `Co-authored-by` is fine for their PR,
  that is their call — but `Assisted-by:` is the mainline-correct form and is safe
  to adopt everywhere upstream-bound.

---

## Patch mechanics (the LKML email path)

These are the standard kernel mechanics the sources below spell out; on the
msm8953-mainline **PR** path most are handled by GitHub, but adopt them anyway —
they are what makes a series reviewable, and they are mandatory the moment you go
to LKML.

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
  git format-patch -o /tmp/pset origin/7.1.3/main..submit/audio
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
  already builds via the `linux-fp3-709` package (cross-ref `fp3-kernel-test`).

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
- [ ] DT work is **warning-free** (`make dtbs_check`, `make dt_binding_check` if a
      binding changed).
- [ ] Commits are `-s` signed, imperative-mood, body wrapped ~75 cols; `Fixes:`/`Cc:
      stable` on bugfixes.
- [ ] Human `Signed-off-by` on every commit; **no `Signed-off-by` from the AI**;
      `Co-authored-by:` swapped to `Assisted-by: Claude:claude-opus-4-8` for upstream.
- [ ] Cover note states the base ("based on 7.1.3/main" / "applies to sound/for-next").
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

**First-patch tutorials (informal but complete)**
- <https://opensource.com/article/18/8/first-linux-kernel-patch>
- <https://www.linaro.org/blog/becoming-a-kernel-developer-part1-posting-your-first-patch/>
- <https://nickdesaulniers.github.io/blog/2017/05/16/submitting-your-first-patch-to-the-linux-kernel-and-responding-to-feedback/>
