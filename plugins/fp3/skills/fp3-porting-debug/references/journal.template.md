# FP3 SLIMbus/ADSP debug journal

> ⚠️ **AI-generated.** This page — and the code, device tree and tooling it
> describes — was written by Claude (Opus 5) working under the direction of
> Lajosházi, László Gergely, who reviewed every change and made or reviewed
> every measurement it rests on. Kernel commits carry `Co-authored-by: Claude`;
> anything prepared for the LKML carries `Assisted-by:` instead and never a
> `Signed-off-by` from the assistant, since only a human can certify the DCO.

Running hypothesis→test→verdict record for the FP3 audio/SLIMbus bring-up (and any other
co-processor fault). **Append one entry per experiment; never rewrite history** — a wrong
verdict earns a *follow-up* entry, not an edit. This is *what was tried*, so the next session
(after a context reset) extends the search instead of repeating it.

Entry format:

### <YYYY-MM-DD> folyt.<N> — <short title>
- **Hypothesis:** what you believe is wrong.
- **Change / probe + deploy vehicle:** the single change; how it was deployed (hot-swap `.ko` / rootfs flash / SSR-reload / cold boot).
- **Signal + where (pass/fail declared in advance):** which register / log line / sysfs node, and the value that means "worked".
- **Result:** the measured value(s) — both sides if it is a differential.
- **Verdict:** what it exonerates or points into; label the evidence HARD (register-level live differential) vs SOFT (source / single-log-line / one-slot), honestly.

---
<!-- entries below; append at the end -->
