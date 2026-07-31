# Runtime outputs → `generated/`

> ⚠️ **AI-generated.** This page — and the code, device tree and tooling it
> describes — was written by Claude (Opus 5) working under the direction of
> Lajosházi, László Gergely, who reviewed every change and made or reviewed
> every measurement it rests on. Kernel commits carry `Co-authored-by: Claude`;
> anything prepared for the LKML carries `Assisted-by:` instead and never a
> `Signed-off-by` from the assistant, since only a human can certify the DCO.

`generated/` is a symlink → `/tmp` (re-pointable). **All runtime-generated files
(signed `.mbn`s, dumps, staged readers, logs) live under `/tmp` = `generated/`** — the
skill's `scripts/` dir stays source-only, nothing generated is committed here.

- Host-side scripts: write under **`$GEN`** (exported by `fp3-env.sh` = this dir's
  `generated` symlink). Portable: re-point `generated` and every `$GEN` write follows.
- Existing scripts already write to `/tmp/...`, which **is** `generated/` — so the outcome
  holds without rewriting them. New/edited scripts should prefer `$GEN` over literal `/tmp`.
- ☠️ Do **not** blanket-rewrite `/tmp` → `$GEN` across all scripts: many `/tmp` paths are
  **device-side** (inside `ssh '…'`) or in `.py` (`open('/tmp/…')`, not shell `${GEN}`) —
  those must stay literal `/tmp`. Migrate host-side output paths case by case (a good
  skill-feedback-log follow-up item).
