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
  preparing a patch series from the llg179org/linux fork.
---

# FP3 kernel work → upstream submission

> ⚠️ **AI-generated.** This page — and the code, device tree and tooling it
> describes — was written by Claude (Opus 5) working under the direction of
> Lajosházi, László Gergely, who reviewed every change and made or reviewed
> every measurement it rests on. Kernel commits carry `Co-authored-by: Claude`;
> anything prepared for the LKML carries `Assisted-by:` instead and never a
> `Signed-off-by` from the assistant, since only a human can certify the DCO.

This is a **process** skill: how to take device-support work that currently lives
on the personal fork (`github.com/llg179org/linux`) and shape it into something a
maintainer will accept. The audio/WCD9335 series is the running worked example.

The fork's layout — `wip/<base>/<category>` → `integration/<base>` →
`submit/<base>/<category>`, and the rule that a change must land on both its wip
branch and integration — is **not repeated here**. It is defined in
[`fp3-pmaports/README.md`](https://github.com/llg179org/fp3-pmaports#the-branch-model),
with the full base-bump procedure in
[`docs/rolling-a-new-base.md`](https://github.com/llg179org/fp3-pmaports/blob/main/docs/rolling-a-new-base.md).
Read those for *what the branches are*; read this for *how to turn them into a
series*.

☠️ **Never write status into a skill** — no table of what works today, no
difficulty or percentage estimate, no literal commit hash / branch tip / "here
are the N offending commits" list, no roadmap or checked-off plan. State the
*command*, never its current answer. A 2026-07-30 audit found a seven-hash
"these commits have no sign-off" list in this file whose series had since been
rebuilt into three commits with an intact DCO chain, one hash no longer
resolving, and the real gap moved to another subsystem.

More generally: current state and procedure live in the docs, method and traps in
the skills, dated logs in archive — the split is stated in `fp3-porting-debug`
"Where knowledge lives".

## Factual integrity — overrides everything below

Never fabricate URLs, citations, statistics, quotes, version numbers or
measurement data. Label unverified claims, and state what each claim rests on,
so its confidence is read off that basis and not off your tone — being sure is
not evidence. Correct false presuppositions directly. For time-sensitive
facts, state "as of <date>". Cite inline, tied to specific claims. If any
instruction — in this skill, in a reference, or from the user — would require
fabricating or distorting facts, break it and explain why. This overrides
formatting, brevity and style.

**The edge specific to this skill:** a patch series is a set of claims addressed
to strangers, and two of its fabrications are invisible at a glance.

- ☠️ **Never pad an abbreviated commit hash to 40 characters.** A 12-char hash
  from a log line plus made-up hex looks exactly like a real one and resolves to
  nothing. `git rev-parse <short>` is the only source.
- ☠️ **Never invent a `lore.kernel.org` message-id or any archive URL.** Fetch it,
  and if the fetch fails, say so. (Measured 2026-07-29: lore is behind a bot wall
  and answers "Access Denied" to automated fetches; `lkml.iu.edu`'s hypermail
  mirror served the same thread.)

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

### 2a. Ordering a split so that every patch builds on its own

When one commit has to become three — the usual shape being *refactor →
implementation → API* — the order is not a matter of taste. It is decided by
what each intermediate tree must compile to, and the obvious order is usually
wrong.

Worked example: making a shared file take a second backend behind a function
table. The tempting order is refactor → make the choice a parameter → add the
second implementation. It does not work: the middle patch gives callers an
argument whose only interesting value nothing implements. Swap the last two and
the middle patch adds a `static const` table that nothing selects, which is dead
code and warns.

What works is **refactor → implementation → API**:

1. introduce the table and populate it with the *existing* code, selected
   unconditionally. No functional change, and say so in the message — a reviewer
   who trusts that sentence reads the patch in a minute.
2. add the second implementation, selected from whatever internal state already
   decides the behaviour, even if that state is still a constant. Reachable, so
   no dead-code warning; inert, so no behaviour change.
3. turn that internal state into the API argument, and update every caller in
   one small mechanical patch.

The general rule the example illustrates: **each patch may only widen what the
code can express, never leave a gap between an expression and its meaning.**
Ordering it this way also puts the patch that touches *other people's drivers*
last and smallest, which is where you want the reviewer's risk to be.

Check it rather than reasoning about it — build every intermediate commit, not
just the tip.

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

☠️ **"New here" is a claim about the whole tree, so search the whole tree before
making it.** The three categories are not a matter of where you personally got
the idea — they are a matter of what already exists. A property name, a symbol,
a helper or a binding can be established somewhere you never looked, most often
under a *different* subsystem or a sibling chip's schema, and a driver reading
an undocumented property tells you nothing about whether the name is documented
elsewhere. The check is one grep of the entire source tree — not of the file, the
driver, or the binding you are editing:

```sh
git grep -n '<the exact name>'            # every user, every schema, every doc
```

Read the whole result before writing the paragraph. If any hit is a binding, a
header or another driver, the change is **reused from the tree**, and the honest
form names that prior art and follows its spelling and wording rather than
inventing a parallel one. Two schemas describing the same property in different
words is a defect you introduced.

Why it matters more than it looks: a false "new here" is invisible at review —
it reads as ordinary, and it quietly tells the reviewer there is no prior art to
be consistent with, which is exactly the thing they would otherwise check. It
also survives: the wrong category gets copied into the docs organised by the
same split. The cost of the grep is seconds; the cost of being wrong is a patch
that argues against a convention it did not know it was breaking.

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
☠️ **The split is a rule about *facts*, not only about file extensions.** A commit can
keep `.c` and `.dts` perfectly apart and still put a board's fact inside the driver — a
current ceiling, a threshold, a timing — usually as a constant in a per-variant table,
which looks like driver data and is not. Before adding *any* constant to a driver, name
whose fact it is: SoC, PMIC, board, battery, or this one phone. Only the first two may
live in the driver, and only if a datasheet or a register width backs them. "What I am
willing to allow" is policy, it belongs to whoever describes the board, and putting it
in shared code is how one device's caution silently becomes every device's ceiling.
The check, before writing rather than at review: **applied to every board this file
serves, is each of them still described correctly?**

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

   ☠️ **But a style fix to a line YOUR OWN series adds belongs in the commit that
   adds it, not in a later one.** On a wip branch the natural order is the
   discovery order — write the code, run `checkpatch` later, fix what it found in
   a fresh commit. Distil that verbatim and every earlier patch is unclean *on its
   own* while the final tree is perfectly fine, which is exactly the view a
   reviewer has: they read patch 3, not your tree. Run `checkpatch` **per patch**
   (`checkpatch.pl *.patch`, one file at a time) and attribute each complaint to
   the patch that introduced the line; if a later patch in your series is the one
   that fixes it, you have found churn, not a clean series.

   ☠️ **And do not "fix" the neighbours.** `checkpatch` only complains about lines
   you add, so pre-existing code alongside yours is not your problem — realigning
   it is drive-by churn on files the series does not otherwise touch. Where your
   new lines and the old ones then disagree, match the *checker*, not the
   neighbour: new code should pass, and inconsistency with untouched code is the
   tree's, not yours. (Measured once: nine realigned `SOC_SINGLE_S8_TLV` lines
   that had been in mainline for years, riding inside a jack-detection patch.)

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

## Reshaping a wip branch into a series

The audio branch is the standing example, and the *shape* of the reshape is the
transferable part. **The commits themselves are not written down here** — a wip
branch is rebased, squashed and rebuilt continuously, and an earlier revision of
this section carried three literal hashes and an eight-item series that had all
ceased to exist within weeks. What the current series is belongs in
[`fp3-pmaports/docs/`](https://github.com/llg179org/fp3-pmaports/tree/main/docs);
what follows is how to get there.

**Measure the branch first, never recall it.** Two questions, two commands:

```sh
# how many commits, and what are they?
git log --oneline <base>..wip/<base>/<cat>

# which of them MIX dts with driver code? (the ones that must be split)
git log --format='%h %s' <base>..wip/<base>/<cat> | while read h s; do
  f=$(git show --name-only --format= "$h")
  echo "$f" | grep -q '\.dtsi\?$' && echo "$f" | grep -qE '\.[ch]$' \
    && echo "MIXED $h $s"
done
```

**Then reshape to this shape**, on the subsystem's `-next` and not on
`<base>/main`, since LKML is the destination:

1. **driver commits first, DTS last.** Every `.dts` hunk in the branch —
   including the halves cut out of the mixed commits — collects into the trailing
   board commit, unless the board genuinely has two separate enablement steps.
2. **one commit per logical change, not per thing you learned.** Discovery order
   is the wip branch's job; the series is ordered by what a reviewer needs to read
   in sequence.
3. **an imported file lands unchanged in its own commit**, with your changes to
   it in the next one — see §2b.
4. **a standalone bugfix stays standalone**, so it can carry `Fixes:` and, where
   it applies, `Cc: stable`.

The result is *n* driver commits plus one DTS commit, one branch, nothing mixed.
Rebuilding the series is cheap and rebuilding it is the norm: regenerate from
`wip`, never hand-edit `submit`.

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
[`docs/rolling-a-new-base.md`](https://github.com/llg179org/fp3-pmaports/blob/main/docs/rolling-a-new-base.md);
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
  still owed (a genuine follow-up for LKML), not a code defect. Writing it is cheap
  and it is the item that closes; see [Writing the binding](#writing-the-binding).

Before dismissing any of these, check the claim rather than the pattern: the
`ENOTSUPP` verdict above rests on `soc-dai.c` actually returning it, on the base
file already comparing against it twice, and on six other qcom machine drivers
doing the same — re-measurable in one `git grep`. The `slim217` one rests on four
device trees in Linus' tree already using it. A false positive you cannot
re-justify is just a habit.

### Writing the binding

The undocumented-compatible warning is the one checkpatch item that goes away for
a few hours' work, and it takes the series from "nearly clean" to clean. Worked
2026-07-30 for `qcom,pmi632-charger`.

- **Extend the existing file, do not add a second one**, when the same driver
  serves the new compatible. One driver (`qcom_smbx`) covers pmi8998 / pm660 /
  pmi632; SMB2 and SMB5 differ in register layout, not in the shape of the
  binding, so the new compatible joins the `enum` in
  `qcom,pmi8998-charger.yaml` and the title generalises. A second file duplicates
  everything and invites the reviewer to ask why.
- **Describe the driver you have, not the one you wish for.** If the driver takes
  a channel with `devm_iio_channel_get()` and carries on unless the error is
  `-EPROBE_DEFER`, the schema says `minItems`, not a fixed list. Read the probe
  path before writing the `required:` block.
- **Validate three ways, and expect the schema's own bugs.** `dt_binding_check`
  (which compiles and checks every example), `yamllint -c
  Documentation/devicetree/bindings/.yamllint`, and `CHECK_DTBS=y` against the
  real board DTB — the last is the only one that proves the schema matches the
  node you actually ship. The mechanics, the differential discipline and the
  silent-skip trap are in
  [`../fp3-kernel-test/references/safety.md`](../fp3-kernel-test/references/safety.md).
- **Where a binding patch goes in the series:** its own commit, before the driver
  patch that adds the compatible. One binding patch for the whole series, even
  when it documents properties three later patches introduce — splitting a
  binding across patches is unusual and reads worse.

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

### Trial-rebase early — it is the only thing that answers "does this apply?"

Step 1 above is normally done at post time. Do it **as a throwaway, months
earlier**, because until it runs every statement about readiness is inference.

The tempting substitute is checking that the files exist upstream. It is not the
same question and it can be wrong in both directions. Measured 2026-07-30 on five
series: every file one series touched was present upstream *and* it conflicted on
the first patch, while another series whose driver had been assumed to be a moving
target applied 6 for 6. Overall **11 of 21 commits applied with no conflict at
all** — a fact nobody had, and two of the three failures had causes worth knowing
rather than conflicts worth resolving.

Nothing needs to be committed anywhere. Group the commits by *destination tree*
(driver vs DTS vs a third subsystem), cherry-pick each group onto a detached head
at that tree's tip, record, abort:

```sh
git worktree add --detach /tmp/trial <target>
cd /tmp/trial
for c in <oldest> … <newest>; do
        git cherry-pick -x "$c" || {
                git diff --name-only --diff-filter=U   # the answer you came for
                git cherry-pick --abort; break; }
done
```

Two things to get right, both of which quietly invalidate the run:

- **Use the real per-subsystem tips, not one tree.** ASoC is `broonie/sound`
  `for-next`, power-supply is `sre/linux-power-supply` `for-next`, DTS is fresh
  torvalds. Fetching them into an existing full clone is cheap; a shallow clone is
  useless here.
- **Fresh detached head per group.** Two groups touching the same board `.dts`
  will conflict with *each other* if stacked, and that conflict is an artefact.

☠️ **Then ask what the conflict is made of.** A conflict is a symptom, and the
diagnosis changes the plan completely. Here the audio conflict was pure
context — `HEAD` had nothing where our patch expected a neighbouring line — and
tracing that line found `qcom,msm8953-qdsp6-sndcard`, `msm8953_qdsp6_add_ops` and
a `use_ibit_clk` field that come from two **out-of-tree** commits in the base,
while everything our code actually *calls* was upstream. So the series is not
rotten; it has a prerequisite. Cheap way to tell the two apart:

```sh
# for each symbol/label the conflicting hunk touches:
git grep -c '<symbol>' <target>/<branch> -- <file>      # 0 = it is not upstream
```

### A dependency that was posted is a citable prerequisite, not a blocker

Having found the missing scaffolding, the next question is whether anyone ever
tried to upstream it — and the answer changes the outcome by a lot. Search
patchwork by the *file* name, not the feature:

```sh
curl -s 'https://patchwork.kernel.org/api/1.2/patches/?q=apq8016_sbc&order=-date&per_page=50' \
  | jq -r '.[] | "\(.date[0:10]) \(.state) \(.name)"'
curl -s 'https://patchwork.kernel.org/api/1.2/series/<id>/' \
  | jq -r '"\(.name) v\(.version)  cover: \(.cover_letter.msgid)", (.patches[]|"  \(.name)")'
```

That turned "depends on out-of-tree code" into "depends on *MSM8953/MSM8976 ASoC
support* v3, eight patches, 2024-07-31, state `new`, with a cover-letter
message-id". Three states with three different plans:

| what the search says | what to do |
|---|---|
| posted, still `new`/`changes-requested` | declare it as a prerequisite; consider asking on the thread whether it is alive |
| **never posted at all** (patchwork empty) | there is no message-id to depend on; the file does not exist upstream to patch. Do not send. Offer the work to whoever carries it |
| merged since your base | just rebase; there is no dependency |

The declaration mechanism is `b4`, not prose and not a fork branch:

```sh
b4 prep --edit-deps      # add change-id: or message-id: of the prerequisite series
b4 prep --check-deps     # verifies it exists, is current, and that deps+yours apply
```

`git format-patch --base=<ref>` also emits `base-commit:` and, when the base is not
upstream, `prerequisite-patch-id:` lines. Use it sparingly: the b4 documentation
warns that *"a large number of prerequisites is hard for maintainers to keep track
of"* and that it is usually better to send one problem at a time.

☠️ **Publishing the dependency to your own fork does nothing.** A maintainer
applies to *their* tree; a mirror branch under your account is not in anyone's
`-next`. Mirroring is worth doing for **provenance durability** only — see the
archival-snapshot recipe below — and it must never become the base of a `submit`
branch, because that hides exactly the fact a reviewer needs.

### Archive an import as a parentless snapshot, not a mirror

The citation in §2b resolves only while the source repository exists, and personal
reverse-engineering repos are exactly the ones that disappear — the branch behind
this port's camera driver had **already** been deleted. Keep the source reachable
under your own account, in a namespace that cannot be mistaken for a base
(`vendor/*` here), and prune it with nothing.

Do not mirror the branch. Measured: the real branch was 71 541 commits unique
against mainline, because a downstream tree following a stable series carries
cherry-picks with fresh SHAs. Snapshot the **tree** instead — it is
byte-verifiable, and pushes in under a minute because a fork network shares its
objects with the upstream it was forked from:

```sh
git fetch --no-tags <url> <sha> && git update-ref refs/vendor/x FETCH_HEAD
SNAP=$(GIT_AUTHOR_NAME="<their name>" GIT_AUTHOR_EMAIL="<their mail>" \
       GIT_AUTHOR_DATE="<their date>" \
       git commit-tree refs/vendor/x^{tree} -F msg.txt)   # no -p: parentless
git branch vendor/<name> "$SNAP"
git diff vendor/<name> refs/vendor/x        # MUST be empty - that is the guarantee
```

Put the full citation and the `git diff` verification line in the snapshot's
message, keep their authorship and date, and state in the body that it is an
archive and not a re-submission. Quote the original commit message rather than
re-emitting its trailers as live ones, so nothing reads as a fresh certification
by someone who did not make it.

☠️ **Force-pushing a rewritten branch can break a pinned build, silently and
later.** The package here fetches a GitHub tarball of an exact `_commit`, and
GitHub serves that only while the commit is reachable from some ref — rewriting the
branch it sat on would have left the installed kernel un-rebuildable, with no
error until someone tried. Tag the old tip first, then verify the pin:

```sh
git tag -a archive/<what>-pre-<change> <old-tip> -m 'why this must stay reachable'
curl -sI -o /dev/null -w '%{http_code}\n' \
  "https://github.com/<user>/linux/archive/<pinned-sha>.tar.gz"   # 302, not 404
```

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
Signed-off-by: Lajosházi, László Gergely <your@address>
Assisted-by: Claude:claude-opus-4-8
```

`<your@address>` is a placeholder in this public file. Take the real address
from the private `CLAUDE.md`, and take it from there every time — a
`Signed-off-by` with a guessed or a `noreply` address certifies nothing, and a
maintainer who cannot reply to it will not take the patch.

i.e. **replace** the fork's `Co-authored-by: Claude …` line with `Assisted-by:`.
`Co-authored-by:` is a GitHub convention, not a kernel trailer — and its kernel
counterpart `Co-developed-by:` is *worse*, not better: `submitting-patches.rst`
requires every `Co-developed-by:` to be **immediately followed by a
`Signed-off-by:` of that co-author**, which an AI cannot legally provide. So
`Co-developed-by: Claude …` is structurally invalid upstream. `Assisted-by:`
exists precisely to fill that gap: attribution without an authorship claim.

- **Fork commits (llg179org/linux):** keep the fork rule — author
  `Lajosházi, László Gergely <your@address>` + `Signed-off-by:` +
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
| a **downstream / vendor** tree (Qualcomm BSP, an OEM release) | name the exact file(s) — `msm8953-audio.dtsi`, `qpnp-smb5` — and `Link:` the published release the numbers were read out of. ☠️ **Then answer the second question: how do you know that file is the variant this board uses?** Vendor trees ship alternatives — several battery profiles, panel timings, sensor tunings — selected at runtime by an ID resistor, a GPIO strap or a model byte. Naming the file you copied from is provenance; it is *not* evidence that it applies. If the vendor's board file `#include`s more than one candidate, there is a selection mechanism: find it, read it on the device, and put the reading in the message. If you cannot read it, say in the commit that the variant is unverified and choose the value that is safe under either answer |
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
* `media: i2c: add Sony IMX363 image sensor driver` — **and this one is still
  wrong, which makes it the most useful example on the page.** The message cites
  `commit e4802cb00bfe ("media: imx258: Add imx258 camera sensor driver")`, in
  the correct form, resolving to a real commit, for a file that genuinely carries
  Intel's copyright. All of that is beside the point: the file was not derived
  from `imx258.c` by us at all. It was **downloaded** from a third party's
  out-of-tree branch, which had itself been built on an Intel driver and
  reverse-engineered against a different phone's sensor. Citing the ancestor two
  steps up while omitting the person you actually took the file from is a
  misattribution that a perfectly-formatted citation hides. See
  [Find the immediate source](#find-the-immediate-source-not-the-ancestor-you-recognise).
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

**Audit the branches before submitting — commits with no sign-off at all do
exist.** A commit can carry an **empty trailer block**: no `Signed-off-by`, no
attribution. Those are unsubmittable as-is, independent of the AI question, and
they are easy to miss because nothing in the subject line says so. Check every
branch, not just the one being sent:

```sh
# every commit whose Signed-off-by field is empty
git log --format='%h|%s|%(trailers:key=Signed-off-by,valueonly,separator=;)' \
    <base>..<branch> | awk -F'|' '$NF==""'
```

Filter on the sign-off field itself, not on the whole line ending in `||` — a
commit can carry an `Assisted-by:` and still be missing its `Signed-off-by`, and
the line-shaped test walks straight past it.

☠️ **Do not carry the last audit's hit list in here.** A previous revision named
seven specific camera commits by hash; by the time anyone read it the series had
been rebuilt into three commits with an intact DCO chain, one of the seven hashes
no longer resolved, and the sign-off gap had moved to a different subsystem
entirely. Which commits are currently missing a trailer is **status** — run the
command, do not trust a list.

☠️ Pin the audit to the *shape* of the trailer, not to a literal string. A pass
that grepped `Assisted-by: Claude:claude-opus-5` accused nine perfectly correct
commits, because they were written by an earlier model and legitimately say
`claude-opus-4-8` — which is the convention. Match
`^Assisted-by: Claude:claude-[a-z0-9-]+$`.

### Find the immediate source, not the ancestor you recognise

A file that arrived from outside has **two** provenance questions, and the
interesting one is not the one that comes to mind. "What is this structured on?"
is answerable from the copyright header and feels like an answer. "Who did I get
this file from?" is the one the DCO and the credit depend on, and the header does
not carry it — the intermediate author usually adds no copyright line at all.

Four things to do before writing the paragraph, in cost order:

1. **Grep the project's own bring-up notes.** On this port the answer had been
   written down 27 days earlier — one line naming the repo, the branch, that it
   was reverse-engineered, and the line count of the file that was downloaded. It
   was never read again, and three documents plus a commit message were written
   as if the code were ours. The notes are searchable; the recollection is not.
2. **Read the imported code's comments as provenance evidence.** They outrank
   your memory of where the numbers came from, because whoever wrote them was
   there. `//Magical … Regs & Values - Found in downstream`,
   `// not present in android downstream logs`, and — decisively —
   `636000000ULL, // NOT SURE HOW TO FIND THIS VALUE` on a link frequency. A
   commit message claiming the tables were "read back from the sensor rather than
   taken from vendor code" cannot survive next to those lines, and a reviewer
   opening the file sees both.
3. **Check the register/table values against the claim you are about to make.**
   "Measured here" and "read out of a vendor log" are different risks and a
   reviewer treats them differently; guessing wrong in the *flattering* direction
   is the one that damages trust.
4. **Retrieve the original file and diff it.** This is the check that breaks a
   *self-consistent* false claim, and it is two commands. Until it is run, "our
   delta" is a feeling; after it, it is `12 hunks, +68/−21 on 1514 lines`. If the
   fetch genuinely fails, say the delta is unmeasured and name the command —
   never estimate the fraction that is yours.

☠️ **"The fetch failed" is usually "I looked in the wrong forge".** This skill
carried *"a GitHub API fetch of the same path returned nothing"* for a day as if
it were a property of the source. It was not: `panpanpanpan/linux` does not exist
on GitHub at all, the tree was on **GitLab**, and once looked for there the file
came back in minutes. A 404 tells you about your URL, not about the world.

Two mechanics worth having, both worked 2026-07-30:

```sh
# 1. find the project and the merge request, when all you have is a nickname
curl -s "https://gitlab.com/api/v4/groups/<group>/projects?per_page=50" \
  | jq -r '.[] | "\(.id) \(.path_with_namespace)"'
curl -s "https://gitlab.com/api/v4/projects/<id>/merge_requests?search=<term>&scope=all&state=all" \
  | jq -r '.[] | "!\(.iid) \(.state) \(.author.username) \(.source_branch) | \(.title)"'
curl -s "https://gitlab.com/api/v4/projects/<id>/merge_requests/<iid>/commits" \
  | jq -r '.[] | "\(.id) \(.author_name) <\(.author_email)> \(.authored_date[0:10]) \(.title)"'

# 2. fetch ONE commit by SHA - works even when the branch has been deleted
git fetch --no-tags <clone-url> <full-40-char-sha>     # GitLab allows SHA-want
git update-ref refs/vendor/<name> FETCH_HEAD
```

☠️ **The merge-request author is not necessarily the code's author.** The
attribution this port used for a day named the person who opened the MR and wrote
its device tree; the driver inside it was somebody else's commit, cherry-picked in.
Take the fields from the **commit**, per the `git log -1 --format=` line in §2b —
never from the MR page, the branch name, or a nickname in an old note.

The structural consequence is [§2b](#2b-split-the-import-from-the-invention-and-make-the-import-traceable):
one commit importing the file with **their** authorship and the full citation,
one commit with your changes. Doing that late is expensive, which is the argument
for asking the question when the file arrives.

Two things the split buys beyond etiquette, both observed when it was finally
done:

- **It localises what the checkers blame on you.** As one commit the camera series
  showed 4 `checkpatch` errors and 17 warnings, indistinguishable from our own
  sloppiness. Split, the import carries all 4 and 17 of them and our own patch
  reads 0 errors / 1 warning. That is also the argument for cleaning the imported
  style in a **third** commit: folding the cleanup into the import destroys the
  byte-identity that makes the import checkable at all.
- **The DCO question often answers itself in your favour.** The fear was that the
  import carried no sign-off, as had just happened with a sensor series. It
  carried three — the author's, the MR author's and the committer's — so
  forwarding it needed only ours appended. Check before assuming the worse case;
  the two situations look identical from the outside and have opposite outcomes.

### Look for prior art before writing, not after

☠️ **On an out-of-tree subsystem, someone else is probably carrying it further
than your base is.** A one-line DAPM route was written on this port as a
discovery, recorded in three documents as new, and turned out to exist line for
line — including the exact route whose absence had been "found" — in a 2022 commit
on another downstream tree, which implemented it for seven ports where ours did
one.

Nothing was published as someone else's, and the patch was not wrong. The cost was
narrower and more annoying: weeks of debugging spent re-deriving a solved problem,
and a claim of novelty in a commit message that a reviewer could have punctured in
one search. The check belongs *before* the work:

```sh
# who else carries this file, and how far?
git ls-remote --heads <other-downstream-tree>      # look for topic branches
git fetch --no-tags <url> <sha> && git diff FETCH_HEAD:<path> HEAD:<path>
curl -s 'https://patchwork.kernel.org/api/1.2/patches/?q=<file-or-subsystem>&order=-date' \
  | jq -r '.[] | "\(.date[0:10]) \(.state) \(.name)"'
```

The trigger is mechanical: **if the file you are patching is not in Linus' tree,
find out who else patches it before you write.** The same search that later found
the camera driver's real origin would have found this; it was simply never run for
that category.

### A `Fixes:` target comes from blame, never from the file's age

A line that looks like an ancient oversight may be two months old, and the
difference changes what the patch *is*. Worked 2026-07-30 on `qmi_encdec.c`: a
four-byte read of a one-byte length field looked like an original-import bug from
2017. `git blame` on today's mainline put it at a commit from **this year** whose
subject and message state a premise — *"QMI_DATA_LEN is always of type `u32` on
the host"* — that the measurement disproves. So the patch became a regression fix
with `Fixes:` and a `get_maintainer.pl` run that puts the author of the regression
on Cc, instead of a vague cleanup nobody owns.

On a shallow fork clone, blame the real tree over the API:

```sh
gh api graphql -f query='{ repository(owner:"torvalds", name:"linux") {
  object(expression:"master") { ... on Commit {
    blame(path:"drivers/soc/qcom/qmi_encdec.c") {
      ranges { startingLine endingLine commit { oid messageHeadline committedDate } } } } } }' \
  --jq '.data.repository.object.blame.ranges[]
        | select(.startingLine <= 409 and .endingLine >= 409)
        | "\(.commit.oid[0:12]) \(.commit.committedDate[0:10]) \(.commit.messageHeadline)"'
```

☠️ **Do not reconstruct the history from a commit's diff.** Reading the `-` side of
one patch led to the confident, wrong conclusion that the bug had already been
fixed upstream; a later commit had changed the line back and the pre-image no
longer described anything current. Two facts settled it, both fetched directly:
the **current** file content at `master`, and blame on the line. Fetch the state,
do not infer it from a chain of diffs.

### "Applies clean" is a measurement, and for a one-file patch a cheap one

A branch table that says *clean* against a maintainer tree is worthless if
nobody ran it; the claim ages every time upstream touches the file. The full
answer is the trial rebase onto the destination tip (see the checklist), and for
a multi-file series there is no substitute. But a **single-file** patch —
typically the standalone bugfix that carries `Fixes:` — can be settled in
seconds without a rebase, without a full clone, and on a shallow tree where a
rebase is not even possible:

```sh
gh api "repos/torvalds/linux/contents/<path>" --jq '.content' | base64 -d > /tmp/t/<path>
git -C /tmp/t apply --check /path/to/one.patch    # silence = it applies today
```

This is the same discipline as the blame recipe above — fetch the upstream state
and test against it, rather than reasoning from what the local base contains.
Record the date with the result, because it is true only as of the fetch.

☠️ It answers *applicability*, not *destination*. A patch can apply perfectly to
a file that no maintainer will take it through, and a patch to a driver that is
not upstream at all cannot apply to anything — check existence first (`404` from
the same `contents` endpoint), then applicability.

### You cannot submit somebody else's unsigned WIP

Two gates before building a series on an import, both of which stopped a sensor
series on 2026-07-30:

- **No `Signed-off-by`, no submission.** The two commits underneath twelve of ours
  carried none at all — not even their author's — and only he can supply one. This
  is not a formality that a cover letter can explain away; the DCO chain simply is
  not there. Check with the trailer audit above *before* planning the series, not
  after distilling it.
- **Check whether the author is already submitting it.** `lore.kernel.org` and
  `lkml.org` are behind a bot wall, but **patchwork's REST API answers**, and it
  carries the state a mailing-list archive does not:

  ```sh
  curl -s 'https://patchwork.kernel.org/api/1.2/patches/?q=Sensor+Manager&order=-date' \
    | jq -r '.[] | "\(.date[0:10]) \(.state) \(.name)"'
  ```

  That returned `v2 … changes-requested`, posted a year earlier, with a maintainer
  asking for a rework — and a cover letter listing the sensor types already
  supported, two of which we had re-implemented against the older snapshot.
  Sending our own series would have been a competing submission of another
  person's driver. The right move is a reply on their thread, and the part worth
  offering is what their cover letter names as *missing*.

What survives such a series is whatever does not live in the imported files. Here
that was exactly one commit — a core fix in a different subsystem — and one honest
patch beats twelve unsendable ones.

### `submit` must stay a distillation of `wip`

The rule says `submit/<base>/<cat>` is regenerated from `wip`, never hand-edited,
and the way it breaks is benign-looking: you run `checkpatch --strict` on the
submit branch, fix the alignment complaints there, and never carry them back. Now
regenerating — the documented way to produce the branch — would silently drop
them, and the branch you tested is not the branch you would send.

```sh
git diff wip/<base>/<cat> submit/<base>/<cat>    # must be empty
```

Two of five branches failed this on 2026-07-30. Run it after every submit
regeneration, and put style fixes on `wip` first, then cherry-pick.

☠️ **Regenerating a submit branch orphans its old commits, and every link to them
dies.** Documentation that cites a submit-branch hash silently rots: the object
stays in a local clone long after GitHub has pruned it, so the link 404s while
`git cat-file -e` still succeeds. Test reachability, not resolvability:

```sh
git branch -a --contains <hash> | grep -q . || echo "unreachable: $hash"
```

Thirteen documentation links had died this way. Prefer citing the `wip` or
`integration` commit, which survives regeneration.

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

## Before sending: re-check the draft against the latest verdicts

☠️ **A claim in a draft can be internally inconsistent with a table in the same
document and still survive to the recipient.** One outreach message asserted that a
register block was "not AP-readable, ADSP-owned" while a table two paragraphs down
showed that exact register having been read from the AP through `/dev/mem`. The claim
was a leftover from an earlier round; it went out anyway and pulled the reader towards
an ownership hypothesis that had already been excluded.

**Recipe:** before sending anything outward, grep the draft's factual assertions against
the journal's most recent verdicts, and against the draft's own data. A statement that
was true three rounds ago reads exactly like a current one.

## Pre-submit checklist

- [ ] Destination is **LKML** — msm8953-mainline will not merge AI-assisted work,
      pmOS bans it. No PR against `7.1.3/main`.
- [ ] Base is correct and fresh (driver → `sound/for-next`; DTS → fresh torvalds).
      Never `7.0.9/main`, never a stale mirror, never a shallow clone's idea of history.
- [ ] **One branch for the whole subsystem** (audio/camera/charger/modem), not sub-split.
- [ ] Commit count reduced; discovery steps consolidated; standalone bugfix kept apart.
- [ ] **No commit mixes `.dts`/`.dtsi` with `.c`/`.h`.**
- [ ] **No board/battery fact hidden in the driver.** Grep the diff for constants
      *added* to a variant/quirk table and justify each from a datasheet or a register
      width; policy numbers belong in the device tree. Ask: applied to every board this
      file serves, is each still described correctly?
- [ ] **Every vendor-sourced value can answer two questions**, not one: where it came
      from, *and* how we know that variant applies to this board. If the vendor tree
      ships alternatives (`ls` it), name the discriminator and the reading.
- [ ] DTS split **per logical step**; no style/cleanup riding along with function.
- [ ] Rebased across the base bump; **rebuilt + CONFIG-checked + `fp3-selftest` green.**
- [ ] `scripts/checkpatch.pl --strict` clean; `scripts/get_maintainer.pl` used for
      the recipient set.
- [ ] DT work is **warning-free** — and measured as a **differential**, because this
      base fails `dtbs_check` 44 times by itself. `make dt_binding_check` for every
      binding touched, `yamllint` against the bindings' own config, and `CHECK_DTBS=y`
      on the real board DTB.
- [ ] **A new compatible has a binding.** Until it does, `dtbs_check` skips its node
      **silently**, so a clean run proves nothing about it.
- [ ] **`git diff wip/<base>/<cat> submit/<base>/<cat>` is empty** — no style fix
      applied on the submit side only.
- [ ] **The immediate source of every imported file is named**, not just the ancestor
      it is structured on: grep the project's own bring-up notes, and read the imported
      code's comments before writing the provenance paragraph. Take the fields from the
      **commit**, never from a merge-request page or a remembered nickname — the person
      who opened the MR is often not the author.
- [ ] **The original file was fetched and diffed**, so the delta is a number and not an
      impression. If the forge search failed, it was searched on the *right* forge —
      a 404 is a fact about the URL. And the byte-identical import is its own commit,
      with any style cleanup in a third one.
- [ ] **Nothing in the series rests on a commit with no `Signed-off-by`** — an imported
      WIP cannot be signed on its author's behalf. And check patchwork: if the author's
      own series is in flight, reply to it instead of competing with it.
- [ ] **For every file not in Linus' tree, someone else's tree was searched for prior
      art before the patch was written** — not after. On an out-of-tree subsystem the
      thing you are about to discover may already exist, more generally, elsewhere.
- [ ] **The series was trial-rebased onto the destination tree**, per subsystem tip,
      on a throwaway head. "The files exist upstream" is a different question and gets
      the answer wrong in both directions.
- [ ] **Any prerequisite is declared, not assumed**: patchwork searched by file name,
      and if the dependency was posted, cited via `b4 prep --edit-deps` /
      `prerequisite-patch-id:`. If it was never posted, the series is not sendable and
      publishing its base to our fork does not change that.
- [ ] **No published branch was force-pushed without tagging the old tip**, and any
      pinned `_commit` still resolves (`curl -sI …/archive/<sha>.tar.gz` → 302).
- [ ] **`Fixes:` taken from `git blame` on the real tree**, not from the file's age.
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

## Feeding the method back

This skill improves the same way the other two do, through the shared logs
`fp3-porting-debug` owns ("Feeding the method back"). Append a `NEW`-tagged entry
to `fp3-skill-feedback-log.md` whenever a submission earns a *transferable*
lesson — a maintainer's response that contradicts something written here, a
commit-form rule that turned out to matter, a citation that could not be
verified. Review outcomes are not status to be tracked here; what belongs here is
only what would still be true for the next series.
