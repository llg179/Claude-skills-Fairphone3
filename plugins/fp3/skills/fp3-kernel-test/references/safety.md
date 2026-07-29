# fp3-kernel-test — Safety & measurement integrity (full text)

> Split out of `SKILL.md` for size; the SKILL body carries the headline list, this file the full mechanisms + worked examples.
>
> **This is the single home for brick-safety** — `fp3-porting-debug` points here
> rather than restating any of it. The numbered list is **append-only: never
> renumber it**, because other files cite these numbers. Prefer citing a rule by
> what it says; a number that silently shifts turns a correct reference into a
> wrong one.

## Safety constraints (the "why" matters — they define what you may measure)

These are not arbitrary rules; each is a class of action that hangs or bricks the
device, with the mechanism, so you can recognise *new* instances of the same class.

1. **One change per experiment.** A measurement only localises a fault if exactly
   one variable moved. Batching two edits means a pass/fail tells you nothing about
   which one mattered. Between runs, verify the previous result *and* reset the
   retry/boot state, so the next boot is clean. **Retry-count-0 hazard:** before any
   fastboot flash/boot — especially a *backgrounded* one — confirm `fastboot getvar
   slot-retry-count:a` is ≥ 1 (ideally 7). At count 0 the bootloader blocks `fastboot
   boot` and can **erase p28** (among other side effects), so any run started at count 0
   is an **invalid** result; reset with `fastboot reboot bootloader` → `fastboot
   set_active a` → re-check. Never launch a background fastboot task without a confirmed
   count ≥ 1.

2. **A kernel experiment must never be able to block boot.** The device is
   headless; if your code hard-waits, you lose the device to a hang and burn a
   recovery cycle. Mechanism: any unbounded `wait_for_completion`, blocking retry
   loop, or busy-wait on hardware that never responds will hang the boot thread.
   Method: instrument with a **single bounded wait + a read-only dump**, never a
   blocking loop. (Worked example: an early version bricked the test slot with a
   10×1s blocking capability-retry.) `fastboot set_active b` resets the slot.

3. **Never `sudo adb`.** It writes a root-owned adbkey that then locks *you* out of
   the oracle's adb. Use unprivileged `adb`, and get root *inside* the shell
   (`echo <pw> | sudo -S`). (`sudo fastboot` is fine — different transport.)

4. **Reading a register whose clock is gated hangs the bus — OR silently lies.** Two
   distinct failure modes, block-dependent: (a) an AXI/AHB read to a block whose clock is
   off never completes → bus hang → the SoC drops into crash-dump mode (this device shows
   USB `900e`) → physical power-cycle (worked example: idle LPASS/SLIMcc register reads =
   instant `900e`); (b) *some* wrapper blocks don't hang — they return a **uniform small
   constant for every offset** (worked example: the SLIMbus core wrapper `0x0c140000`
   returns `0x40`/`0x50` in *every* word when the NGD is runtime-suspended, no hang). Mode
   (b) is the dangerous one for *measurement* — it looks like a real read but the value is
   junk, so an idle snapshot silently misreads a suspended block (see rule 6). Method: only
   read a clock-gated block *while you have forced its clock on* — during playback, or via
   the **runtime-PM `echo on > .../power/control` re-trigger** (see the runtime-PM instrument
   below; on this device it cycles the framer FRM_STAT `0x40`↔`0x060d1901`), never at idle.
   Always check `power/runtime_status` before trusting a `/dev/mem` value.
   **Corollary — a block you've *proven* clocked responds at EVERY offset of its page; the hang
   risk is per-*block*, not per-*offset*.** Once a bounded-probe marker (e.g. `0xF00D` written by
   the cave, per rule 5) confirms the block is clocked on the side you're reading, a whole-page
   sweep of that block is safe: a clocked register-file returns a value (0 or otherwise) at every
   page offset — it only hangs if the *entire* block is gated. So don't refuse to read the wider
   offsets "in case one hangs", and — the measurement-integrity half — **don't misattribute a
   reboot during such a sweep to a per-offset cave hang when disk-full (rule 9) also explains it.**
   (Worked example, folyt.134: a FRS6 whole-page read of the framer block reboot-looped and was
   first blamed on "wider offsets hang the dead-side block"; the real cause was disk-full, the
   block was already proven clocked on the dead side by FRS2/128d's `0xF00D` marker, and the v2
   run read 16/16 offsets with no hang.)

5. **Never read an *unverified* physical address from the AP.** A firewalled or
   unmapped PA hangs the NoC and wedges the whole device (ping+ssh dead → USB drop →
   at best a watchdog reboot that leaves a dirty rootfs → boot-loop; at worst a
   physical power-cycle). This is a hardware memory-protection unit (XPU/NoC), *not*
   just STRICT_DEVMEM, so it fires on any protected address — the remoteproc DDR
   carveout is only the best-known one. Method: read **only** an address you have
   independently confirmed is AP-mapped and safe; **never scan a list of candidate
   PAs** hoping one is right — the first firewalled hit wedges you before you learn
   anything. To exfiltrate from the co-processor use a **shared** region both sides
   may touch — SMEM, or an HWIO scratch reg — never its private carveout. (Worked
   examples: carveout `0x8d600000–0x8e6fffff` from `/proc/iomem` `…remoteproc adsp@…`
   is fatal; and a "probe several candidate SMEM bases" scan that included one
   firewalled PA wedged the device even though the *proven* base `0x86300000` alone
   read fine — the speculative extras did the damage.)
   **The carveout is not forever-unreadable — read it the *legitimate* way, via the remoteproc
   coredump, never `/dev/mem`.** The one safe path to the co-processor's private DDR is the kernel's
   own devcoredump (`echo enabled > …/coredump` + `echo 1 > …/crash` → ELF at
   `/sys/class/devcoredump/devcdN/data`), which reads it through the remoteproc driver's mapping, not a
   raw AP poke. So "I need the carveout contents" is a coredump task, not a `/dev/mem` task — see the
   coredump instrument in `SKILL.md`. (Worked example: the full 16.98 MB ADSP dump that the rule-5
   `/dev/mem` read of `0x8d600000-0x8e6fffff` would have wedged on, obtained safely via coredump.)

6. **Know your `/dev/mem` reader.** On a hardened ARM64 kernel `dd`/`busybox devmem`
   silently return empty (STRICT_DEVMEM read-path); a Python `mmap` reader works.
   So "the register reads 0" can be a *tooling* artifact — confirm your reader can
   read a known-nonzero register first. Reading MMIO that *is* clocked (e.g. the
   NGD control block during activity) is safe any time. **Second artifact class — the
   runtime-suspended block:** a `/dev/mem` read that returns the *same constant in every
   word* (e.g. `0x40`/`0x50` across FRM_CFG, FRM_STAT, NGD_CFG alike) is almost never real
   hardware — it's a runtime-PM-suspended block returning its unclocked constant (rule 4b).
   The tell is uniformity across registers that should differ; the fix is to read
   `power/runtime_status` and force-resume (`echo on > .../power/control`) before re-reading,
   not to trust or "diff" the constant. (Worked example: an idle FRM_STAT read showed `0x40`
   and looked like a dead framer, but the block was merely autosuspended; a forced resume
   restored `0x060d1901`.)

7. **Never force an unclean reboot on a healthy system.** The rootfs here is a
   nested loop image; an unclean shutdown dirties it and the next boot's fsck hangs
   (ping-alive, ports-closed). Plain `reboot` only; `--force`/sysrq are for an
   *already*-wedged device.

8. **The flash vehicle itself fails in ways that silently invalidate the run — verify
   the kernel actually changed before you measure.** Three distinct failure modes, all
   observed in one night: (a) `pmb flasher flash_rootfs` can abort mid-way (exit 7 when
   `apk add android-tools` in the native chroot hits a repo/dependency error) — this is
   *not* a device fault, but the device then boots the **old** kernel, so any result is
   invalid because your change was never flashed. **Always confirm `uname -v` shows the
   new build date/`_p`-suffix before trusting a measurement.** (b) A host `fastboot flash
   <part> <multi-GB image>` can hit a **D-state stall** — the process wedges at ~0 CPU,
   blocked on the first USB bulk transfer, and must be killed; the partial write **corrupts
   the slot**. The fix is a fresh USB enumeration (physical power-cycle) followed by a
   **chunked sparse flash: `fastboot -S 256M flash …`** (worked example: 8/8 chunks,
   finished ~150s, where the un-chunked transfer stalled indefinitely). (c) `fastboot
   getvar max-download-size` can itself **wedge the fastboot command channel** — subsequent
   `getvar`/`reboot` then hang (rc=143); only a physical power-cycle clears a hung fastboot
   pipe (host USB-reset is forbidden — rule in the porting-debug skill; `/mnt` is on USB
   too). Note this is the *max-download-size* query specifically; the `slot-retry-count`
   getvar in rule 1 is safe and required.

9. **A campaign of cold-boot deploys can fill the tiny loop-rootfs and cause a reboot-loop —
   cap the journal and gate on free space.** The pmOS rootfs (`/dev/loop0p2`) is only ~2.4 GB.
   Each cold-boot experiment logs a full boot; over a night of many reboots the **systemd
   journal balloons** (observed: 289 MB) and crosses the disk to 100% full → the next boot
   fails / **reboot-loops** (the USB gadget *flaps*: `ip` shows the host iface up, but the
   device stops responding to ping and sshd never settles — looks exactly like a wedge, and is
   easy to misread as "my cave bricked it"). The tell that it's disk-not-cave: the on-disk
   firmware is still stock (your patch may never even have deployed), and `df` reads 100% once
   you get in. **Diagnosis + fix (all from a caught SSH window):** `df -h /`; `journalctl
   --disk-usage`; `journalctl --vacuum-size=40M` (frees the bulk); then cap it persistently so
   it can't refill: write `/etc/systemd/journald.conf.d/cap.conf` with `[Journal]\nSystemMaxUse=40M`
   and `systemctl restart systemd-journald`. **Guardrail for every cold-boot deploy script:**
   before the reboot, `journalctl --vacuum-size=30M` and a `df` free-space gate (abort if
   <~80 MB free). **Free space is necessary but not sufficient — also gate on a *clean*
   rootfs.** A dirty loop-rootfs from any prior unclean shutdown hangs the *next* boot's fsck
   regardless of free space (rule 7), so a cold boot after a crashed/wedged prior cycle
   reboot-loops even with plenty of disk. Before relying on a cold boot: only ever clean-`reboot`
   (never `--force`/sysrq on a healthy system, rule 7), and if the previous cycle *did* end
   uncleanly (crash-loop, forced power-cycle, unexpected fastboot fallback), `e2fsck -fy` the
   inner rootfs from the other slot first (recovery section) instead of trusting the next boot.
   (`/tmp` is tmpfs/RAM — the accumulating signed `.mbn`s there are *not* the cause; the journal
   is. Recovery from a full loop-rootfs needs a physical power-cycle if it won't respond, per
   rule 7's fsck-hang class.)
   **The loop is NOT cold-boot-specific — an *SSR-reload* measurement campaign triggers the same
   disk-full reboot-loop.** Even with zero cold reboots, (a) the journal still grows on every SSR
   iteration, and (b) every unexpected reset (SSR/link flakiness) leaves the rootfs dirty, so the
   *next* boot's fsck plus the tight free space combine into the same ~4 s watchdog-reset loop.
   So **free disk headroom *before* a dead-side firmware campaign — journal-vacuum to ~270M+ free,
   don't merely `df`-gate** (worked example, folyt.134: 210M/91%-full → reboot-loop after the FRS6
   SSR campaign; vacuuming the journal to 272M free made the boot stable). **And the diagnostic
   corollary: "reboot-loop that persists *after* you restored the stock firmware" ⇒ the firmware is
   NOT the fault — look at the disk/rootfs.** Restoring stock `adsp.mbn` alone did *not* clear the
   folyt.134 loop; freeing disk did. (An ADSP fault can't stop the AP booting anyway — rule 10 /
   recovery.md.)

10. **A single cold-boot "did not come back → fastboot" is often a TRANSIENT retry-fallback, not
    your cave bricking the device — power-cycle and retry once before concluding.** A backgrounded
    cold-boot deploy whose `waitup` expires and lands the device at lk2nd fastboot looks alarming,
    but lk2nd falls back to fastboot after a few slow/failed boot attempts (retry-counter), which a
    merely-slow boot or one transient hiccup can trigger. The disciplined recovery is: `fastboot
    set_active <slot>` (resets the retry state) → reboot → wait patiently. **The decisive test that
    it wasn't the cave: if the OS then boots with the caved firmware still on disk and
    `remoteproc*/state` reads `running`, the cave is harmless** (an ADSP fault would show
    `crashed`/`offline`, and an ADSP fault does not stop the AP from booting anyway). Only after a
    *reproducible* no-boot that clears when you restore stock should you blame the cave. (Worked
    example: a CBCR-read cave's first cold boot expired to fastboot and was written up as "probably
    wedged the SoC"; a power-cycle booted pmOS fine with the same cave, `remoteproc2=running`, and
    the stash was intact — the no-boot was a transient, the cave was fine.) Corollary: don't escalate
    to "restore-from-the-other-slot" recovery until this cheap retry is exhausted.

11. **A firmware cave that hooks a FREQUENTLY-called function can stall the co-processor's SSR
    bring-up → the `echo start` blocks → reboot.** A cave adds ~10-15 instructions per call; on a
    hot path that per-call overhead accumulates enough to stall the co-processor's re-init, so
    the bring-up never completes: the `echo start > …/remoteproc2/state` sysfs write **blocks**
    (the remoteproc stays wedged), the on-device runner times out, and the device warm-reboots to
    fastboot. This is distinct from rule 2 (blocking the AP boot) — here the *cave itself* is fine
    but its cumulative cost wedges the *co-processor's* SSR. **Before hooking a function, estimate
    its call frequency statically — a generic HAL/accessor (e.g. a register-write primitive with
    many callsites) is hot.** Mitigations: (a) hook a more specific, rarer point instead; (b) make
    the cave's *first* instruction an ultra-cheap filter (1-2 insns), doing the expensive work only
    on a match; (c) always run `echo start` backgrounded with a timeout-guard on-device (`nohup` +
    poll a done-file) so a hung bring-up can't wedge the whole measurement session. **Recovery
    (remoteproc-wedge, no cold-cycle): restore stock firmware to disk, then a graceful `systemctl
    reboot`** — the systemd shutdown-timeout carries past the wedged remoteproc, the device drops to
    fastboot, and **lk2nd auto-continues** a fresh pmOS boot on the stock firmware (~1 min). Do NOT
    force an unclean reboot (rule 7). Post-reboot SMEM is re-allocated, so a pre-reboot SMEM stash at
    a fixed AP address is now garbage — don't trust it. (Worked example, folyt.152: the FWT1
    write-tracer hooked the framer register-write HAL `0xf04bfe54`, assumed rare; it fires often
    enough that the cave overhead stalled the ADSP SSR — `echo start` blocked, 2-min timeout, warm
    reboot to fastboot; the graceful-`systemctl reboot` recipe recovered it first try.)

12. **☠️☠️ Never update the pmOS kernel with `pmb flasher flash_kernel` on this lk2nd+extlinux device — it
    OVERWRITES lk2nd on the `boot` partition → "stuck at the Fairphone logo" (the kernel never even starts).**
    The FP3 pmOS boot chain is XBL→ABL→**lk2nd (flashed on the `boot` partition)**→**extlinux** (which loads
    the real kernel from the pmOS boot sub-partition — `system_b` is a nested MBR: p1=ext2 `pmOS_boot`=/boot,
    p2=ext4 `pmOS_root`=/). `deviceinfo` has `generate_extlinux_config="true"` + a `lk2nd-msm8953` dep + a
    *separate* `flasher flash_lk2nd`. `pmb flasher flash_kernel` `fastboot flash boot`s a ~25 MB raw boot.img
    over the 342 KB lk2nd → ABL can't boot it → **stuck at the Fairphone logo.** ⚠️ THIS MISLEADS: every fresh
    build hangs IDENTICALLY regardless of content (camera/baseline/config all the same), so it looks like a
    kernel/DT/config bug when the FLASH METHOD is the fault. **Diagnosis key: ask the user WHAT IS ON SCREEN —
    "Fairphone logo" = kernel never started = boot-image/bootloader problem, NOT kernel content** (contrast: a
    kernel that boots then panics reaches further). **Recovery:** `pmb flasher flash_lk2nd` restores lk2nd →
    extlinux boots the (old) kernel already on loop1p1 → pmOS comes up (first try, ping ~12 s). **Correct
    kernel update:** install the kernel `.apk` INTO THE ROOTFS — `pmb sideload linux-…` OR ssh + `apk add
    --allow-untrusted` (updates /boot on loop1p1 + extlinux + modules), OR a full `pmb install`. `flash_kernel`
    is only for raw-boot.img devices (no lk2nd). (Cost of the lesson: ~half a day + 5 physical fastboot
    recoveries spent debugging kernel *content* instead of the flash method.)

13. **NEW RISK CLASS: an *environmental* change (pinmux / GPIO output / clock-vote) COMBINED with a
    co-processor SSR can wedge the whole device — the "one change per experiment" rule applies to environment,
    not just code.** Re-muxing a PMIC pad (`pinmux-select` pm8953 gpio1→func1 + a gpio-chardev OUTPUT request)
    was harmless alone (measured 20 s, nothing), and an ADSP SSR was harmless alone (baseline OK) — but the
    TWO TOGETHER drove the device into ~2 min of NETDEV-watchdog transmit-timeouts, then a reboot. Mitigating:
    the reboot was clean (the gadget re-enumerated with a new MAC, pmOS booted) — but on an unattended night
    this is exactly the risk to avoid. Never combine an environmental poke with an SSR on the first try;
    change one thing, measure, then the next.

14. **☠️ A boot-armed diag/capture systemd oneshot that runs `Before=basic.target` and blocks HANGS THE BOOT.**
    A `Type=oneshot` service ordered `Before=basic.target` that launches a long/blocking op (here a
    `DIAG_IOCTL_SWITCH_LOGGING`→MEMORY_DEVICE_MODE that pinned the diag driver in D-state) **blocks
    `basic.target` → `adbd`/UI never come up → splash-hang, ~150 s+ no recovery** (even the systemd timeout
    can't kill a D-state python). This is distinct from the disk-full/dirty-fs reboot-loop (rules 7/9) — here
    a boot *service* blocks, not the fs. If you MUST capture at boot: (a) NOT `Before=basic.target` (use
    `After=multi-user.target` or a separate late target); (b) make it time-boxed + SIGKILL-able; (c) better,
    avoid boot-armed diag entirely — it rarely pays off. Recovery for the UT case was a cross-slot overlay
    edit (see recovery.md, the UT `/etc`-on-writable-overlay note).

---

15. **☠️ An MMIO sampler DIES when the block's clock goes away under it — never read
    co-processor MMIO across an SSR stop-window.** A sampler polling a QDSP6SS register
    *and* debugfs at 20 ms intervals vanished without a trace during a controlled ADSP SSR:
    no output, no process, no log entry. That is easily misread as "the measurement found
    nothing" — it found nothing because it was dead. `echo stop > .../remoteproc2/state`
    gates the block's clock, so the read is rule 4 in disguise. The *same* sampler with the
    MMIO removed (debugfs/genpd only) ran clean end to end. Recipe: to sample around an SSR,
    either drop the co-processor MMIO entirely, or read it only in the window **after**
    `echo start`. debugfs/sysfs sampling is SSR-safe.

16. **☠️ A zero-length DT boolean can hang the kernel UNINTERRUPTIBLY — put the timeout in
    the INSTRUMENT, not just around the shell.** `allow-set-time` on `rtc-pm8xxx` looks free
    ("if the hardware refuses, the write errors"); on this board the set-time path never
    returns, and **neither an outer `timeout 20` nor a Python `signal.alarm()` breaks it**.
    `dmesg` stays silent (no SPMI timeout) and `ps -eo stat` shows no D-state task, so every
    "is anything stuck?" check reads negative while every call hangs. Recipes: (a) call the
    writing ioctl in a **separate, disposable process** and accept that it may linger;
    (b) on a write-type experiment **revert the DTB first**, before the reboot, so the next
    boot is clean even if shutdown wedges on the stuck task; (c) a **"reads fine, writes
    hang" asymmetry is a strong hint the register is owned by TZ or a co-processor**.

17. **☠️ `postmarketos-mkinitfs` REGENERATES `/boot/extlinux/extlinux.conf` and DROPS
    hand-added fallback entries.** Every `apk add linux-fp3` leaves a single `label`, so a
    recovery path set up beforehand is silently gone. If the recovery plan is a saved boot
    set (`vmlinuz-fallback` + its dtb), rewrite `extlinux.conf` **after** the package
    install and immediately before the reboot — otherwise you believe you have a way back
    and you do not.

18. **☠️ A downstream ADSP-SSR on the Ubuntu Touch oracle defaults to
    `restart_level=SYSTEM` — one ADSP crash REBOOTS THE WHOLE PHONE. Set it `RELATED`
    first.** This rule protects the *oracle*, which is worth as much as the device: the
    entire differential method depends on one slot that still works.

    Recon: `/sys/bus/msm_subsys/devices/subsysN/{name,restart_level,state,crash_count}`
    (adsp = subsys2 as measured on this UT build). The clean debugfs trigger
    (`/sys/kernel/debug/msm_subsys/adsp`) is **absent** on that kernel; `/dev/subsys_adsp`
    (243,2) exists but its char-device restart ioctl semantics are uncertain — do **not**
    fire an uncertain ioctl at the working oracle's ADSP. The mainline NGD runtime-PM
    re-trigger reports `unsupported` there (downstream driver).

    If you must SSR: set `restart_level=RELATED` (contained, auto-recovery), drain the
    rings at T0 (a read *is* a drain), trigger, capture, then restore `SYSTEM` — and
    verify `crash_count=0` to confirm it never actually fired.

## Measurement integrity (don't report soft evidence as hard — the anti-patterns that fake progress)

Distinct from the brick-safety constraints above: those protect the *device*, these
protect the *measurement*. A run that trips one of these produces **confirmation
theater** — output that looks like progress but localises nothing. (Every one of these
was committed in a single session, three tasks in a row, each written up as "HARD" until
a red-team caught it. Run the checklist before and after each experiment.)

- **Never substitute static/source analysis for the live measurement a question demands.**
  If the plan calls for a live ftrace / register read / two-sided diff, then a source
  grep, an ELF header, or one dmesg line is **not** it — that is the exact soft evidence
  the method warns against. If the live measurement isn't feasible now (other slot / risk
  / user presence), the task is **BLOCKED**, not "FAIL" and not "done".
- **Label by evidence strength, honestly.** A register-level *live differential* is hard;
  static / source / single-log-line / one-slot is soft, no matter how confident the prose
  reads. "Two source trees" is still source-reading. Write soft as soft.
- **Never close an avenue on wrong-layer evidence.** Before writing "X is excluded",
  confirm the signal actually measures X and not a same-named neighbour (e.g. an AP-side
  notifier *registration* is not the co-processor-internal protection *domain*).
- **One-sided is not a differential.** The whole method is oracle-vs-SUT on the *same*
  layer. One slot (or one disk image) read alone is half a measurement — don't issue a
  verdict from it.
- **A register that differs working-vs-broken may be an OUTPUT (a marker), not a lever —
  prove which before claiming an AP-side fix or "the environment differs".** A two-sided
  register delta (oracle value ≠ SUT value) is a real *marker*, but it can be a value the
  co-processor *writes* from its own divergent internal state, not an independent input you
  can set. Test causality by forcing the oracle's value *at the causally-relevant time* and
  watching two things: does the co-processor **overwrite** your write, and does the
  **behaviour** change? If it overwrites and nothing changes, the register is a
  symptom/marker, not the lever. Method to force a *boot-time-once* value: a **bounded**
  burst-write in the remoteproc `.start` path (after `auth_and_reset`, before
  `wait_for_start`) with a **pre/post readback** DBG line — `pre` tells you who set it
  (0 ⇒ neither TZ-at-auth nor a strap; the co-processor sets it during its own boot), and a
  later live read tells you if the co-processor overwrote your value. (Worked example:
  QDSP6SS `0xc20002c` differed UT `0x103` ↔ pmOS `0x10b` and tracked framer-up-vs-dead
  perfectly, *looked* like the AP lever — but a cold-boot force read `pre=0`, the ADSP
  re-wrote its own value after the 200 ms AP burst, and the framer stayed dead ⇒ the bit is
  ADSP-authored output, a marker, not a settable cause. The *logical* constraint still
  bites: identical firmware + different output ⇒ the co-processor read a different *input*;
  the real environmental difference is upstream, and the marker is only its first measurable
  trace. Don't over-claim the marker as the mechanism.)
- **Disprove a hypothesised "lever" *offline* before you build an experiment on it — especially if
  the branch tests a bit of a pointer/aligned value.** If a firmware branch gates on
  `tstbit(memw(ctx+N), #k)`, compute the *structural* value of that bit before calling the field a
  working-vs-dead differentiator. A pointer's low bits are usually a fixed tag (SBO/`std::function`
  inline-vs-heap marker), so the tested bit is structurally constant on both sides and **cannot**
  differ — a whole cave campaign avoided by 5 minutes of coredump reading. (Worked example, folyt.147:
  "ctx+0xe08 bit0 = send-transport selector, may differ working↔dead" collapsed when the coredump
  showed ctx+0xe08 is an object pointer `0xf0954aa0` whose bit0 only tags callable storage → always 0.)
- **A "force/bypass" cave can force the WRONG lever — a force-negative is conclusive only if the
  forced state reproduces the real-success *content*, not just flips a branch condition.** Skipping an
  error-dispatch by forcing a status word to the success value simulates "no error" *without* the real
  response data, so downstream success-handlers can return early — *before* reaching the effect you
  were testing for. Label such a negative **WEAK/INCONCLUSIVE** when the input data it depends on is
  absent; a force-cave proves something only when the forced state is content-faithful to real success,
  not merely branch-faithful. (Worked example, folyt.150: FSF1 forced `ctx+0xe54=0` (success path); the
  framer FS stayed 0 — but with no real capability-response data the success-handlers could bail before
  any frame-trigger, so the negative was weak, not a disproof.)
- **A register read at a mid-operation capture point can be identical working-vs-broken and
  still look like the smoking gun — the oracle control is what disproves it.** When you splice
  *inside* a bring-up function and read a status register, the value you catch is a *snapshot at
  that instant*, not the settled state. It may be a transient the working side also passes
  through. Always run the identical splice on the oracle before concluding. (Worked example:
  a cave spliced at the framer-clock RCGR enable's UPDATE-poll read `CMD_RCGR=0x80000000`
  (bit31 ROOT_OFF=1) on the dead side — read as "the clock root never turns on = the fault."
  The UT oracle, framer *alive*, showed the **byte-identical** `0x80000000` at the same point,
  killing the conclusion: ROOT_OFF=1 there is transient/normal. Worse, `CMD` had `ROOT_EN`
  (bit1) = 0, meaning this RCG is **not root-gated at all** — it gates at the *branch clock
  (CBCR)*, a different register the splice never captured. Two lessons: (1) the oracle control
  saved a false localization; (2) read the *right register at the right time* — the branch CBCR
  at steady state, not the RCGR mid-enable. The RCGR only sets the rate (src-sel/div), which was
  identical both sides.)
- **Every measurement must have a real path to PASS.** State, in advance, the concrete
  live result that would *break* the current frame. If the planned probe cannot return
  one even in principle, it is theater — redesign before running. N-of-N "confirmations"
  of the standing frame is a **tell** that the probes were too weak, not a reward.
- **A null `ls | grep X` is NOT proof that X is absent — until you've validated the grep pattern
  against the REAL name and cross-checked with a second signal.** A whole (wrong) "pd-mapper is
  missing → that's the root cause" chain was built on `ls /sys/bus/auxiliary/devices/ | grep pdm`
  being empty — but the device is named `pd-mapper` (with a dash), not `pdm`; a second grep with the
  wrong driver-dir name "confirmed" the false negative. The correct query showed
  `qcom_common.pd-mapper.0/.2` present AND bound (`qrtr-lookup`: servreg-locator 0x40 registered).
  **Rule: before asserting "no X" from a negative search, (1) list the full set RAW and read the
  actual names, (2) validate the pattern against at least one known-positive, (3) cross-check with a
  DIFFERENT signal (here `qrtr-lookup`, `readlink .../driver`).** Especially load-bearing in fast/
  overnight autonomous runs, where an early false negative steers hours the wrong way. (Contrast: the
  Bert-reframe "the framer CAN come up" stayed correct throughout because it was EXTERNAL data (LKML),
  not my own grep.)
- **Don't drop the inconvenient finding to keep a clean verdict; don't argue backward from
  the conclusion you want; don't write the "HARD / closed" journal or memory entry before
  the measurement exists.** And beware the wrapper-vs-inner exit code: a build/deploy wrapper can
  report `exit 0` while the real work FAILED inside (worked example: a `pmb build` wrapper task exited
  0 but the kernel build failed `BUILD_RC=3` on an unrelated `modpost wcslen [cifs.ko]` link error) —
  always check the inner tool's own success signal (`BUILD_RC`, the produced apk exists), never the
  outer wrapper's exit alone, before recording "built/deployed".

---

## Measurement integrity — from the QMI / sensor bring-up

- **Confirm on the oracle that an endpoint is the RIGHT one before reverse-engineering its
  protocol.** A night went into the framing of a QRTR port that the oracle later showed
  behaves identically on the *working* system — the service being hunted lived on another
  node with another instance. The measurement was sound; the target was not.
- **A content-independent echo means a wrong or stub endpoint, not a wrong framing.** If
  16 zero bytes come back verbatim, no parser is involved. Control it by sending the same
  message to the neighbouring ports on the same node, which answer with proper QMI errors.
- **Verify the PROCESS, not the service label.** An Android `ctl.stop` sat at `stopping`
  while the daemon ignored SIGTERM and kept running, which silently invalidated the A/B
  built on top of it.
- **After two or three indirect exclusions that still do not separate "never started" from
  "started and failed", change instrument rather than generating another hypothesis.**
  Indirect tests are cheap, but they saturate.
- **☠️ A hand-built co-processor probe leaves state behind, and not only in the subsystem
  you are probing.** After a session of hand-built QMI requests the sensor stopped answering
  *and* the SLIMbus codec became unreachable — all audio died; a reboot restored both. Never
  interleave probing and measurement: reboot between them, and never measure an unrelated
  subsystem in a boot where you have been probing.
- **☠️ One positive among many negatives is the signal, not the noise.** Sampling a
  short-lived event (a ringtone stream) two seconds after triggering it produced `0` again
  and again, and a whole diagnosis plus a workaround unit got built on those zeros. A single
  earlier run had shown `1`. For events, subscribe (`pactl subscribe`, `udevadm monitor`, an
  IRQ counter) — never snapshot.
- **☠️ A buffer-only IIO device cannot be `cat`-ed, and a wrong record size looks *partly*
  right.** The record here is **24 bytes** (3 × s32 + 4 pad + s64 timestamp); reading 32
  makes every third line plausible, which is far more dangerous than reading nothing.
- **☠️ The IIO device index moves between boots** when devices register as a co-processor
  enumeration completes. Match on `name`, never on `iio:deviceN`.
- **☠️ Measuring a user-session service over ssh is a trap.** Hand-set
  `DBUS_SESSION_BUS_ADDRESS`/`XDG_RUNTIME_DIR` can point at a session that has since been
  replaced; take them from the running session (`loginctl`, `systemctl --user
  show-environment`) or you will diagnose a dead session as a broken daemon.
- **☠️ Your own cleanup can destroy the evidence.** `journalctl --vacuum-size`, run to free
  space, left one line per older boot; a later cross-boot comparison then showed a *perfect*
  correlation that was purely missing data. Before comparing boots, check each still has a
  plausible line count (`journalctl -b -N -k | wc -l`).
- **☠️ `pkill -f <pattern>` matches your own command line** and killed the ssh session
  running it. Use `pkill -x <name>`.
