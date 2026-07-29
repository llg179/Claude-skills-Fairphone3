# Archive — dated records, not method

Nothing in this directory is instruction. These are **live investigation logs and
chronologies** kept as a historical record: what was tried, in what order, and
what was believed at the time. They contain superseded verdicts stacked on top of
each other, because that is how they were written — an entry may be flatly
contradicted by a later one in the same file.

**Do not read these to learn how to do something.** The method they produced has
been folded into the skills; the outcome they produced is written up properly in
[`fp3-pmaports/docs/`](https://github.com/llg179/fp3-pmaports/tree/main/docs).
Read them for one question only: *was X already tried, and what happened?*

| file | what it records | where the settled version lives |
|---|---|---|
| `slimbus-audio-context.md` | the SLIMbus/WCD9335 audio investigation, `folyt.` entries through the framer wall coming down | [`docs/audio/bringup/`](https://github.com/llg179/fp3-pmaports/tree/main/docs/audio/bringup) for the story, [`docs/audio/`](https://github.com/llg179/fp3-pmaports/tree/main/docs/audio) for how audio works today |
| `slimbus-audio-tracker.md` | the runtime-trigger sub-investigation, appended live as it ran | same |
| `boot-debug-log.md` | ramdisk / USB-gadget / boot bring-up chronology, June–July 2026, plus the Sailfish component notes it grew out of | the Sailfish track is still live — see `../sailfish-components.md` and `../pmos-bringup.md` |

Two things worth knowing before mining them:

- **`slimbus-audio-context.md` §7 is a full component address map** for this SoC
  (register bases per block, firmware build ID). That is durable data, not a dated
  claim, and it is the main reason to open the file at all.
- **The framer pokes these logs argue for were removed on 2026-07-29**, after
  measurement showed the codec comes up without them. Anything here that reads as
  "the poke is required" is superseded by
  [`docs/audio/bringup/qdsp6ss-framer-poke.md`](https://github.com/llg179/fp3-pmaports/blob/main/docs/audio/bringup/qdsp6ss-framer-poke.md).

> **AI-generated.** Written by Claude (Opus 5) under the direction of
> Lajosházi, László Gergely. The archived files themselves were written during
> the sessions they describe, and are left exactly as they were.
