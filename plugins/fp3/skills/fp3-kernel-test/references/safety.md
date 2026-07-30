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

19. **☠️ Force-pushing a rewritten kernel branch can make the INSTALLED package
    un-rebuildable, and nothing complains until you try.** The `linux-fp3` APKBUILD
    fetches a GitHub source tarball of an exact `_commit`; GitHub serves that only while
    the commit is reachable from *some* ref. Rewriting the branch that commit sat on —
    a rebase of `integration/<base>` to correct a message, say — orphans it, and the next
    build 404s. This belongs with the brick-safety rules rather than the measurement ones
    because it removes a **way back**: the reproducible source of the kernel currently on
    the phone.

    Before any history rewrite of a published branch: tag the old tip, push the tag, and
    only then force-push. Then verify the pin, because reasoning about reachability is
    exactly the step that goes wrong (`git cat-file -e` still succeeds on an orphan while
    GitHub 404s it):

    ```sh
    git tag -a archive/<branch>-pre-<change> <old-tip> -m 'why this must stay reachable'
    git push fork refs/tags/archive/<branch>-pre-<change>
    git push --force-with-lease fork <branch>
    curl -sI -o /dev/null -w '%{http_code}\n' \
      "https://github.com/<user>/linux/archive/<pinned-sha>.tar.gz"   # 302, not 404
    ```

    Two corollaries. `--force-with-lease`, never bare `--force`, so a concurrent push is
    a conflict rather than a loss. And after such a rewrite the pinned commit is **no
    longer an ancestor of the branch**, so "N commits behind" stops being meaningful —
    say which lineage it is on instead, or the next person will compute a nonsense
    number.

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

## Measurement integrity — from the charger / JEITA bring-up

Four rules, one of them the most expensive kind: a wrong verdict that read as a
successful cross-check.

- **☠️☠️ Before saying "these two systems disagree", establish that BOTH of them are
  measuring.** The oracle's stock stack read `resistance_id 9843` from the battery-ID
  resistor; our device tree described a different pack. That looked like a two-sided
  conflict to resolve, and it was not one: the mainline side **never reads the battery
  ID at all** — the driver has no code for it and the node does not request the channel.
  The device-tree value was a *static assumption* from an earlier session, made by
  picking one of two vendor profiles without measuring. **A hardcoded constant is not a
  measurement; it merely looks like one, because it is a number.** The same applies to
  calibration tables, "values taken from downstream", and anything a previous session
  wrote down. Before you frame a disagreement, ask which side actually reads hardware.
  (The resolution here was cheap: the ADC channel was already described and exposed, so
  the mainline side could read `10.03 kΩ` against downstream's `9.843 kΩ` — two
  independent paths, same answer, and the device tree was simply wrong.)
- **The oracle is a source of CONFIGURATION, not only of signal — and that validates an
  encoding you derived from source.** When you have reverse-engineered a register layout
  out of a downstream driver, boot the oracle and read *the same registers it programs*.
  Here the hard JEITA thresholds and the soft-hot threshold came back byte-identical to
  what we had derived, which independently confirmed the big-endian hot-then-cold layout
  and the raw-code domain — and the one that did **not** match was a real bug in our
  device tree. This is cheaper and sharper than re-reading the source a second time.
- **A register field's width can be the design constraint, not the hardware's capability.**
  The JEITA compensation is six bits of 25 mA, so at most 1575 mA of reduction; that, not
  caution, is why a target current above ~2.175 A could not express the vendor's own
  600 mA cool-zone value. Before rounding a target number "to be safe", work out what the
  hardware can actually encode — the honest reason is usually more useful than the
  cautious one, and it tells you what the vendor did instead (here: compensate in
  software).
- **When a design question is "unit A or unit B in the interface", compute the difference
  instead of arguing it.** °C in the device tree with an in-driver conversion looked
  cleaner than raw ADC codes. Twenty lines of Python against the vendor's four
  characterised codes showed the generic conversion curve errs *outward* at every one of
  them (0.3–2.0 °C), widening each safety window the unsafe way — decision made, and as a
  by-product the agreement to within 2 °C confirmed the code domain the whole approach
  assumed.
- **☠️ `pgrep -f <pattern>` matches its own command line, exactly like `pkill -f`.** An
  `until ! pgrep -f 'foo'; do sleep 30; done` waiter **never exits**, because the pattern
  is in the shell command running the loop — and it presents to the user as "something is
  still running" when nothing is. Wait on the artifact instead
  (`until [ -f <output> ]; do …`), or `pgrep -x <name>`.

## Provenance integrity — the values you WRITE are claims too

Everything above governs the values you *read*. Nothing governed the values a patch
*introduces*, and that is where this method failed hardest: a battery profile was
chosen out of a vendor tree that shipped two of them, the wrong one, and it survived
review because it was impeccably cited. These rules close that hole.

- **☠️☠️ Provenance is not applicability.** *"Read out of `<vendor file>`"* answers
  **where a number came from**. It does not answer **whether it applies to this
  board**, and the citation discipline makes a wrong value look *more* trustworthy,
  not less. Every provenance line for a vendor-sourced constant needs a second half:
  *and here is how we know this is the variant this hardware uses.* Without that
  second half the value is a guess wearing a citation.
- **☠️ When the vendor ships more than one candidate, choosing between them is a
  MEASUREMENT, not a lookup.** Name the discriminator the vendor itself uses, read
  it, and put the reading in the commit message next to the value. (Worked example:
  Fairphone ships two 3000 mAh packs — different Arima part numbers, 2.0 A vs 2.7 A,
  JEITA cool band at 15 vs 20 °C — told apart by a battery-ID resistor, 10 kΩ vs
  50 kΩ. Picking one without reading that resistor produced a device tree that was
  wrong by 5 °C in the unsafe direction, cited flawlessly to the wrong file.)
- **Before copying a value out of a vendor tree, `ls` its directory for siblings.**
  One `ls` answers "is there a choice here at all". If there is more than one
  candidate for the same subsystem, there is a selection mechanism in the vendor
  code — find it before you copy anything. Grep the board's include chain too: a
  vendor board file that pulls in *several* profiles is telling you outright that
  the hardware varies.
- **If the discriminator cannot be read, say so and take the conservative branch.**
  A value you could not verify is a guess; mark it as one in the commit and in the
  docs, and where the alternatives differ in a direction that matters (current,
  temperature limit, voltage), pick the one that is safe under *either* answer
  rather than the one that is right under your favourite.
- **Step 0 applies to a constant, not only to an experiment.** Before writing a
  number into a driver or a device tree, answer the same four questions: what do I
  believe, what single value expresses it, **what signal on this device confirms the
  value belongs here**, and what reading would tell me it does not. If there is no
  such signal, that is the finding — write it down instead of the number.

## Layer integrity — whose fact is this?

The provenance rules above catch a value **copied** from the wrong place. They do not
catch a value you **invent** and put at the wrong layer, which is the same failure with
no citation to give it away. Both happened in one session; the invented one was worse,
because it landed in code shared by every device the driver serves.

- **☠️☠️ Before writing any constant, name whose fact it is.** SoC / PMIC / board /
  battery / *this one phone*. Then put it there, and nowhere else. **A driver serving N
  devices may only contain facts that are true of all N.** (Worked example: a
  fast-charge ceiling of 2 A was added to a per-PMIC variant table. 2 A is not a fact
  about the PMI632 — the chip is rated 3 A — it is a fact about the battery in one
  Fairphone. Every other PMI632 board would have been silently held to it.)
- **☠️ A safety limit is not a hardware limit, and the variant table is only for
  hardware limits.** "What this chip can do" is a datasheet number and belongs in the
  driver; "what I am willing to allow" is policy and belongs to whoever describes the
  board. Putting policy in the driver looks responsible and is how one device's caution
  becomes every device's ceiling. When you catch yourself writing a bound, ask which of
  the two it is; if you cannot point at a datasheet or a register width, it is policy.
- **☠️ Moving a hardcoded value is not removing it.** A change whose point is "let the
  device tree decide" and which then adds a *new* constant to bound what the device tree
  may ask for has not removed the hardcode — it has renamed it, and the commit message
  will honestly describe the improvement while shipping the same defect one layer over.
  Read your own diff for constants introduced, not only for constants deleted.
- **☠️ Convenience of access silently decides the layer, and the symptom is a
  description that cannot express reality.** Battery properties were put on the
  *charger* node because that is the node the driver already had a `struct device` for.
  The tell: with them there, a board **cannot** describe two batteries — and this board
  ships two. If a property sits on node X but describes Y, it is misplaced, however
  convenient X is; reach Y properly (`fwnode_find_reference()`, a phandle, a child node)
  instead of moving the data to where the code happens to be standing.
- **The upstream test, applied before writing rather than at submission:** *if this
  patch were applied to every board the file serves, would each of them still be
  described correctly?* One question, and it catches all of the above.

## Reading a failure — three rules that each cost a wrong diagnosis

- **☠️ The loudest error message is not necessarily *the* error.** Three lines arrived
  together: `qmi_encode: Invalid data length` → `-22` → `Buffering request failed:
  0x501`. The `0x501` was the eloquent one, and a ready-made plausible story attached
  itself to it ("this is an on-change sensor, so it does not support buffering") which
  would have led to writing a whole second QMI protocol path. In fact `0x501` was the
  *teardown's* answer **after** the failure; the real fault was the `-22` two lines
  above. **Recipe:** on a multi-line eruption, reconstruct the **causal order** first —
  which call follows which in the code — and only then interpret any code.
- **★ Error codes layer per phase; always go looking for the NEXT error.** The sequence
  here ran `-18` (not all services present) → `-2` (present, but on one port only) →
  no error at all (per-port). Each step removed one class of failure and **revealed
  another**; stopping at the first clean-looking line would have looked like success.
  Find the cheapest success/failure indicator in the trace — here it was one argument
  of the closing message, `[0]` versus `[1]` — and watch that rather than the noise.
- **★ Independent confirmation is worth a great deal, and the DIFFERENCE is the
  finding.** A hand-built request and an upstream implementation agreed on the service
  id, the version, the instance and the group ids; what they did **not** agree on was
  the missing piece — `SNS_REG_GROUP_MSG_ID = 0x4`, the request itself. So when a
  working implementation turns up, do not simply adopt it: **diff it against your own
  model**, because the delta is precisely the hole in your hypothesis.

## Writing to a register that may not be yours

- **☠️ A write that hangs uninterruptibly can be invisible to every "is something
  stuck" check.** The symptom was not an SPMI timeout, and `ps -eo stat` showed no
  task in D state, yet every call froze. Three recipes:
  1. **Issue the writing ioctl from a separate, disposable process** (`sudo timeout N
     python3 …`, plus an `alarm()` inside the script) and accept that the process may
     survive as a zombie — the point is that your session does not go with it.
  2. **On a write-type experiment, restore the device tree as the FIRST step after
     seeing the failure**, before the reboot, so the next boot is clean even if the
     shutdown itself wedges.
  3. **"Reads work, writes hang" is a strong signal that the register is owned by TZ or
     by a co-processor**, not that your access is malformed.

## Absence of evidence, and evidence that is not evidence

- **☠️ "No error message" is not "no problem" — a clean log proves nothing until you
  have shown the channel would report that class of event at all.** Four logs were
  clean here (TZ log, ADSP F3, dmesg, SMEM) and not one of them had ever been tested
  against a *known* violation, so the silence excluded nothing. What did exclude
  something was a **positive** signal: the ADSP's own F3 trace showing `Hardware reset
  successful`, which proves it can reach the register at all. And the specific trap:
  **a silent physical gap** — a missing bus-drive or pad grant — looks exactly like a
  frame-sync timeout and logs *nothing*, so "the log is clean" cannot rule it out.
  Prefer a positive "the operation succeeded" marker over any amount of quiet.
- **☠️ A source comment, or a comment in a device tree, is not evidence — and must not
  reopen a lead that a live measurement closed.** One mainline DTS comment ("this PD
  frames the bus") reopened a question that a golden-side measurement had already
  answered the other way months earlier. A comment describes intent or aspiration, and
  sometimes an intent that was never implemented; the running device describes fact.
- **When capturing a co-processor trace, take the full histogram and the init band, not
  only your filtered hits.** The subsystem's own boot sequence comes free with the
  capture and is worth more than the filter: an init trace with timestamps shows every
  step *before* the one you care about closing cleanly, which is how you learn the fault
  is pointlike rather than environmental. A filtered capture cannot tell you that.

## Validating what you wrote, not only what the hardware did

Schema and style checkers are instruments too, and they mislead in their own ways.
All of the below is from writing and validating a device-tree binding, 2026-07-30.

- **☠️☠️ Run `dtbs_check` as a DIFFERENTIAL, exactly like every other measurement.**
  The msm8953-mainline 7.1.3 base fails it **44 times on its own** (`opp-avg-kBps`,
  `qfprom`, `gcc` power-domains, `rpm-proc`), so an absolute count says nothing
  about your work, and a first look at the output reads like a catastrophe you
  caused. Build the DTB with the base's board files, build it again with yours,
  sort both error lists and `comm -13` them. On this port that turned "51 errors"
  into **six that are ours**, and the difference is the whole finding.
  ```sh
  pip install dtschema yamllint      # needs swig, libfdt-dev, python3-dev first
  make ARCH=arm64 CC=gcc HOSTCC=gcc CHECK_DTBS=y qcom/<board>.dtb
  make ARCH=arm64 CC=gcc HOSTCC=gcc dt_binding_check DT_SCHEMA_FILES=<path>.yaml
  ```
  ☠️ Remove the `.dtb` between runs or `make` will not re-check it, and you will
  compare a stale result against a fresh one — which reads as "my change fixed
  everything".
- **☠️☠️ A node whose `compatible` nothing documents is SKIPPED SILENTLY.** It is
  not reported as unchecked; it simply produces no output. So a clean `dtbs_check`
  is **not** evidence that a node was validated — it may mean the schema never
  looked. On this port the charger node passed cleanly for weeks for exactly that
  reason, and the six new properties on it only became visible once the binding
  existed. Before believing a clean run, confirm a binding matches the node.
- **The checker finds bugs in your schema, not only in the tree.** `minItems`
  without `maxItems` makes dtschema infer `maxItems == minItems`, so a
  deliberately open-ended array fails with *"is too long"* — in your own new
  binding. Never hand-review a schema you have not run.
- **Take a unit suffix from the authority, not from the neighbouring property.**
  The canonical list is `property-units.yaml` inside the installed `dtschema`;
  `-ohms` is plural, `-microamp` and `-percent` are singular. A wrong suffix is
  invisible because the type check simply does not apply.
- **☠️ A checker's POSITIVE needs validating too, not only its null result.** The
  companion to "a null grep is not proof of absence": three checks written on the
  same day each accused long-standing, correct work, and all three were the
  checker's fault — a trailer audit grepping one hard-coded model name while older
  commits legitimately name an older model; a "dangling hash" pass matching the
  date inside a `lore.kernel.org` URL; an anchor checker whose slug algorithm
  collapsed repeated spaces (GitHub does not) and then stripped underscores
  (GitHub keeps them), so it took **three** runs before "0 broken links" meant
  anything. When a fresh check reports a defect in work that has been in use,
  suspect the check first and run it against a known-good case.
- **☠️☠️ A trap written down in this file was re-introduced the same week.** The
  anchor checker above was rewritten from scratch a few days later and stripped
  underscores **again** — same tool, same bug, same single false positive, in a
  session that had itself authored the warning. Prose in a skill does not protect
  a rewrite; only something that fails does. So when a checker's bug is worth
  recording, put the guard **where the code is**: the offending line now reads
  ```python
  text = re.sub(r'[*~]', '', text)   # NOT _ : GitHub keeps it (this bug bit twice)
  ```
  and better still, give any homemade checker a **known-positive and a
  known-negative fixture** so a rewrite that breaks it says so on the first run.
  The general form: a lesson that lives only in documentation protects the reader,
  not the next author — and those are often the same person.
