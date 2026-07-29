---
name: fp3-kernel-test
description: >-
  Method for running a one-change kernel/firmware experiment on the Fairphone 3
  (MSM8953/SDM632) dual-slot dev device and measuring the result on-device: how
  to form a testable hypothesis, pick the lightest deploy vehicle, capture the
  signal, and interpret it — plus the safety constraints and recovery moves that
  keep the loop fast and brick-safe. Use whenever iterating on the FP3 linux-fp3
  kernel or the ADSP firmware (SLIMbus/audio/remoteproc bring-up). The SLIMbus
  framer work is the running worked-example; treat its specific numbers as
  illustrations, not current fact.
---

# FP3 kernel/firmware experiment cycle

This is a **method** skill: how to ask a hardware question on the FP3 and get a
trustworthy answer, one change at a time, without bricking the loop. The concrete
addresses, register values and conclusions in here come from the WCD9326/SLIMbus
bring-up and are kept as **worked examples** — they show the shape of a good
measurement, but they age. Re-measure before you rely on any specific number.

The prize you are always working toward is a **differential measurement**: the
same probe on a known-good reference and on the system under test, so the *delta*
localises the fault. On this device the reference is built in (dual-slot), which
is why almost every technique below has a "golden side" and a "test side".

---

## The mental model: two slots, one oracle

The device holds two OSes on A/B slots, and that is the whole reason the debugging
works:

- **`slot_a` = the oracle.** An OS where the feature *works* (here Ubuntu Touch,
  Halium, kernel 4.9.x — the SLIMbus framer comes up, audio plays). Its job is to
  answer "what does the working system do/measure here?"
- **`slot_b` = the system under test.** The OS you are trying to fix (here
  postmarketOS mainline). Its job is to answer "what does the broken system
  do/measure here?"

Every diagnosis is: probe the same thing on both, diff. When you cannot probe the
oracle directly (no debug node), you fall back to capturing it once into a
**golden trace file** and diffing against that. Keep those traces; a fresh capture
costs a reboot.

`fastboot set_active a|b` chooses which slot boots. This is also your master
reset: it clears the "unbootable"/retry state on a slot you just broke.

### Environment substrate (verify, don't trust — names drift)
- SoC MSM8953/SDM632. Disposable dev phone (a *separate* FP3 is the daily driver,
  so flashing/bricking this one is acceptable).
- One password everywhere (this device: `$FP3_PW`). SSH non-interactively with
  `sshpass -p <pw> ssh -o PreferredAuthentications=password -o PubkeyAuthentication=no
  fp3@$FP3_DEV_IP`; on-device root needs a tty for sudo → pipe the password:
  `echo <pw> | sudo -S <cmd>`. ☠️ **The `[sudo] password for …:` prompt has no trailing
  newline, so it prepends to your first stdout line** — a filter like `2>&1 | grep -v
  '^\[sudo\]'` then deletes that whole line *including your output*, and the command looks
  like it produced nothing (but `rc=0`). Fix: send the prompt to `/dev/null` —
  `echo <pw> | sudo -S sh -c '…' 2>/dev/null` — instead of grep-filtering it. Stabilise the
  host↔device CDC-NCM link to a fixed iface name + static host IP once (method under
  "Reading the device state") so reconnects are deterministic; optional wrapper scripts
  (`fp3-ssh`, `fp3-link`) are just shorthand for those steps.
- Kernel source tree is a detached checkout whose `origin` is upstream
  (msm8953-mainline / torvalds) — **never push to `origin`.** Publishing the FP3
  work goes ONLY to the user's personal fork remote (`github.com/llg179/linux`,
  branch `fp3-7.0.9-audio`); commit as the user (author `Lajosházi, László Gergely`,
  `Signed-off-by:` + `Co-authored-by: Claude …`), English comments only, no
  Hungarian in code. ☠️ On the live-USB network a `git push` over SSH port 22
  hangs/`unexpected disconnect while reading sideband packet` even though
  `ssh -T git@github.com` and `git ls-remote` are instant and the pack is tiny —
  it's a port-22 upload stall, not auth/size. Fix: push via
  `ssh://git@ssh.github.com:443/llg179/linux.git` (`git remote set-url` the fork to
  the 443 endpoint once). Example local tree path `$FP3_PMOS/bert-repro`.
- Build system is pmbootstrap via a wrapper (`cd $FP3_PMOS && ./pmb …`).
  A `--src` build stamps an apk version `_pYYYYMMDDHHMMSS`; a plain upstream
  version string means your DT/source edits are **not** in the image.
- **★ Neither OS needs a human at the phone any more, and the wrappers do the healing.**
  `fp3-ssh 'cmd'` (pmOS) and `ut-ssh 'cmd'` (Ubuntu Touch: USB, then WiFi, then UT's
  usb-moded rescue sshd) authenticate by key — no password, no `sshpass` — and retry with
  a neighbour flush when the link is mid-reconnect. Verified by rebooting each OS with
  nothing touched on the phone: pmOS back in 39 s, UT in 76 s over WiFi. The full recipe,
  and the measured proof that a replug **cannot** be emulated from the host, is under
  "Unattended access" in the repository README; the files to deploy are in
  `fp3-porting-debug/scripts/unattended/`.
- Helper scripts live in `fp3-porting-debug/scripts/`. The skill maintains **two logs** in the project
  root — bootstrap each **create-if-absent** (if missing, create it by copying the template
  verbatim; else append, never overwrite):
  - **Investigation journal** → `FP3-slim-debug-journal.md` (template
    `fp3-porting-debug/references/journal.template.md`). **Append every experiment + result** —
    the loop is long and context resets; the journal is how the next session knows what has
    already been ruled out.
  - **Skill-feedback log** → `fp3-skill-feedback-log.md` (template
    `fp3-porting-debug/references/skill-feedback-log.template.md`). When a run earns a
    *transferable* lesson (a new safety class, a measurement-integrity trap, a better recipe,
    or a correction to a claim in this skill / its `references/`), append an entry tagged with
    its target + status `NEW` — the raw material for the next revision of these skills.
    (Full convention: `fp3-porting-debug` "Feeding the method back".)

---

## Safety & measurement integrity (headlines — full text in `references/safety.md`)

Two rule classes; read the full mechanisms + worked examples in
[`references/safety.md`](references/safety.md) **before** an experiment.

**Brick-safety (protect the device):**
1. **One change per experiment;** confirm `slot-retry-count` ≥ 1 before any fastboot flash/boot (count 0 → invalid run, can erase p28).
2. **A kernel experiment must never block boot** — bounded wait + read-only dump, never a blocking/retry loop.
3. **Never `sudo adb`** (writes a root adbkey that locks you out); `sudo fastboot` is fine.
4. **Reading a clock-gated register hangs the bus** (→ `900e`) *or* returns a uniform junk constant — read only while the block's clock is forced on.
5. **Never read an unverified PA from the AP** (XPU/NoC wedge); never scan candidate PAs; exfil via SMEM, not the carveout.
6. **Know your `/dev/mem` reader** — `dd`/`devmem` lie on hardened kernels (use Python `mmap`); a same-constant-every-word read = suspended block.
7. **Never force an unclean reboot on a healthy system** (dirties the loop-rootfs → next boot's fsck hangs).
8. **The flash vehicle can silently invalidate a run** — verify `uname -v` shows the new build first; chunked `-S 256M` sparse flash; avoid `getvar max-download-size`.
9. **A cold-boot deploy campaign fills the ~2.4 GB loop-rootfs → reboot-loop** — gate on journal-cap + `df` free space **and** a clean rootfs (fsck from the other slot after any unclean cycle).
10. **A single cold-boot "no-boot → fastboot" is usually a transient retry-fallback** — `set_active` + retry once; `remoteproc*/state=running` with the cave on disk = cave harmless.
11. **A cave hooking a FREQUENTLY-called function stalls the co-processor SSR** (per-call overhead → `echo start` blocks → warm-reboot to fastboot) — estimate call frequency before hooking; ultra-cheap first-instruction filter on a hot path; recover with a graceful `systemctl reboot` (lk2nd auto-continues).
12. **☠️☠️ Never `pmb flasher flash_kernel` on pmOS — it overwrites lk2nd → "stuck at Fairphone logo"** (kernel never starts). Update the kernel INTO the rootfs (`pmb sideload` / `apk add --allow-untrusted` / full `pmb install`); recover with `pmb flasher flash_lk2nd`. Diagnosis key: "Fairphone logo on screen" = bootloader/boot-image, not kernel content.
13. **An environmental change (pinmux/GPIO/clock-vote) + a concurrent SSR can wedge the device** — "one change per experiment" applies to environment too; never combine a pad/GPIO poke with an SSR on the first try.
14. **A boot-armed diag/capture systemd oneshot `Before=basic.target` hangs the boot** — never block `basic.target`; prefer `After=multi-user.target`, time-box + SIGKILL-able, or avoid boot-armed diag.
15. **☠️ An MMIO sampler DIES when the block's clock goes away under it — never read co-processor MMIO across an SSR stop-window.** A sampler polling a QDSP6SS register *and* debugfs at 20 ms vanished without a trace during a controlled ADSP SSR (no output, no process, no log — easily misread as "the measurement found nothing"); `echo stop > .../remoteproc2/state` gates the block's clock, so the read is safety-rule-4. The *same* sampler with the MMIO removed (debugfs/genpd only) ran clean end-to-end. Recipe: to sample around an SSR, either drop the co-processor MMIO entirely or read it only in the window **after** `echo start`. debugfs/sysfs sampling is SSR-safe.
16. **☠️ A zero-length DT boolean can hang the kernel UNINTERRUPTIBLY — put the timeout in the INSTRUMENT, not just around the shell.** `allow-set-time` on `rtc-pm8xxx` looks free ("if the hardware refuses, the write errors"); on this board the set-time path never returns, and **neither an outer `timeout 20` nor a Python `signal.alarm()` breaks it** — `dmesg` stays silent (no SPMI timeout) and `ps -eo stat` shows no D-state task, so the usual "is anything stuck?" checks all read negative while every call hangs. Recipes: (a) call the writing ioctl in a **separate, disposable process** and accept that it may linger; (b) on a write-type experiment **revert the DTB FIRST**, before the reboot, so the next boot is clean even if shutdown wedges on the stuck task; (c) an **"reads fine, writes hang" asymmetry is a strong hint the register is owned by TZ or a co-processor**.
17. **☠️ `postmarketos-mkinitfs` REGENERATES `/boot/extlinux/extlinux.conf` and DROPS hand-added fallback entries.** Every `apk add linux-fp3` leaves a single `label`, so a recovery path you set up beforehand is silently gone. If your recovery plan is a saved boot set (`vmlinuz-r0bak` + its dtb), rewrite `extlinux.conf` **after** the package install and immediately before the reboot — otherwise you believe you have a way back and you do not.

**Measurement integrity (protect the measurement — confirmation-theater anti-patterns):**
never substitute static/source analysis for a live measurement (if it isn't feasible now the task is **BLOCKED**, not "done"); label by evidence strength (register-level live differential = hard; source / single-log-line / one-slot = soft); never close an avenue on wrong-layer evidence; **one-sided is not a differential**; a differing register may be an OUTPUT (marker), not a lever — prove causality; **disprove a hypothesised lever offline before building on it** (a branch on a pointer/aligned-value bit is structurally constant — compute it); a **force/bypass cave can force the WRONG lever** (a force-negative is conclusive only if the forced state is content-faithful to real success, else WEAK); a mid-operation snapshot can read identical working-vs-broken (always run the oracle control); every measurement must have a real path to PASS; don't drop the inconvenient finding to keep a clean verdict; **confirm on the oracle that an endpoint is the RIGHT one before reverse-engineering its protocol** (a night went into the framing of a QRTR port that the oracle later showed behaves identically on the *working* system — the service being hunted lived on another node with another instance: the measurement was sound, the target was not); **a content-independent echo means a wrong or stub endpoint, not a wrong framing** (if 16 zero bytes come back verbatim, no parser is involved — control it by sending the same message to the neighbouring ports on the same node, which answer with proper QMI errors); **verify the PROCESS, not the service label** (an Android `ctl.stop` sat at `stopping` while the daemon happily ignored SIGTERM and kept running, which silently invalidated the A/B built on it); and **after two or three indirect exclusions that still do not separate "never started" from "started and failed", change instrument rather than generating another hypothesis** — indirect tests are cheap but they saturate.

**Measurement integrity — additions from the sensor bring-up:**

- **☠️ A hand-built co-processor probe leaves state behind, and not only in the
  subsystem you are probing.** After a session of hand-built QMI requests the
  sensor stopped answering *and* the SLIMbus codec became unreachable, i.e. all
  audio died — a reboot restored both. Never interleave probing and measurement:
  reboot between them, and never measure an unrelated subsystem in a boot where
  you have been probing.
- **☠️ One positive among many negatives is the signal, not the noise.** Sampling
  a short-lived event (a ringtone stream) once, two seconds after triggering it,
  produced `0` again and again — and a whole diagnosis plus a workaround unit got
  built on those zeros. A single earlier run had shown `1`. For events, subscribe
  (`pactl subscribe`, `udevadm monitor`, an IRQ counter), never snapshot.
- **☠️ A buffer-only IIO device cannot be `cat`-ed, and a wrong record size looks
  *partly* right.** The record here is **24 bytes** (3 × s32 + 4 pad + s64
  timestamp); reading 32 makes every third line plausible, which is far more
  dangerous than reading nothing.
- **☠️ The IIO device index moves between boots** when devices are registered as a
  co-processor enumeration completes. Match on `name`, never on `iio:deviceN`.
- **☠️ Measuring a user-session service over ssh is a trap.** Hand-set
  `DBUS_SESSION_BUS_ADDRESS`/`XDG_RUNTIME_DIR` can point at a session that has
  since been replaced; take them from the running session (`loginctl`,
  `systemctl --user show-environment`) or you will diagnose a dead session as a
  broken daemon.
- **☠️ Your own cleanup can destroy the evidence.** `journalctl --vacuum-size` run
  to free space left one line per older boot; a later cross-boot comparison then
  showed a *perfect* correlation that was purely missing data. Before comparing
  boots, check each still has a plausible line count (`journalctl -b -N -k | wc -l`).
- **☠️ `pkill -f <pattern>` matches your own command line** and killed the ssh
  session running it. Use `pkill -x <name>`.


## The loop: hypothesis → single change → deploy → measure → interpret

### Step 0 — Write the hypothesis as a measurement
Before editing anything, state four things (in the journal):
1. **Hypothesis** — what you believe is wrong.
2. **The single change** that would fix/test it.
3. **The signal** you will read, and *where* (which register/log line/sysfs node).
4. **Pass vs fail**, in advance — what value means "worked".

If you cannot name the signal, you are not ready to build; go find an instrument
first (see the Instruments section). Mark every code experiment with a
grep-able breadcrumb (`dev_info(dev, "DBG …")`) so the capture can *prove the code
path ran* — otherwise a null result is ambiguous between "hypothesis wrong" and
"code didn't execute".

### Step 1 — Choose the lightest deploy vehicle that carries the change
This is the biggest lever on iteration speed. Match the vehicle to the blast
radius of your edit:

- **One loadable module changed → hot-swap the `.ko` (fastest, ~2 min, no flash).**
  How: build, confirm the module's **vermagic matches the running kernel**
  (`modinfo | grep vermagic` on both — version + SMP/preempt flags must be
  identical or `insmod` refuses it), `scp` it over, back it up, copy into
  `/lib/modules/$(uname -r)/…`, `depmod`, then `reboot` (clean, so the module loads
  through the full probe path). Why it's safe: nothing on-disk except one file
  changes; if it's wrong you just restore the backup. (Worked example: the SLIMbus
  fix touches only `slim-qcom-ngd-ctrl.ko`; hot-swap beat a full flash every time.)
  - **☠️ `rmmod`+`modprobe` reloads the code but does NOT re-run the co-processor bring-up past
    the boot's FIRST cycle.** The first reload's `.probe()` re-runs the full path (worked once on
    `slim_qcom_ngd_ctrl`, ~15 s, needs `lsmod` used-by=0), but a *second* reload gives no new
    PDR/SSR callback — `.probe()` runs yet `power_up` does not, so the log goes "silent" and is
    easily mistaken for a negative result. For a repeatable full bring-up trigger use an **ADSP SSR**
    (`echo stop; echo start > /sys/class/remoteproc/remoteproc2/state`, ~15 s) instead, and always
    confirm your measured code path actually RAN (DBG breadcrumb), not merely that the deploy succeeded.
  - **★ Need a NEW instrument (a diagnostic driver) on the ORACLE? Build it as a
    standalone external module — do NOT rebuild the oracle's `Image`.** The oracle
    UT boot.img is a *prebuilt-Image repack*, so its tree was never compiled end-to-end
    from source; a full `make Image` walks into unrelated missing-header walls
    (`btfm_slim.h`, `kgsl_trace.h`, `msm_camera_tz_util.h`, techpack
    `-Werror=misleading-indentation`) that have nothing to do with your change and
    cost hours. `make -C <tree> M=<extdir> modules` compiles just your one `.c` against
    the configured tree and side-steps every one of those. Requirements: the tree's
    `.config` must match the running kernel (`CONFIG_MODULE_FORCE_LOAD=y`, no
    `MODULE_SIG_FORCE`); a module with **no** `Module.symvers`/CRCs still loads on a
    plain vermagic match (`insmod` worked); any symbol you call must be `EXPORT_SYMBOL`
    in the oracle (e.g. `subsys_notif_register_notifier`). (Worked example folyt.141:
    `framer_mmio_dump.ko` — a debugfs MMIO snapshotter — hot-loaded on UT in minutes
    after the from-source `Image` build proved a rabbit hole; its manual trigger read
    byte-identical to `/dev/mem`. Source in `fp3-porting-debug/scripts/framer_mmio_dump.c`.)
- **★ Only the device tree changed → rebuild just the DTB, copy to `/boot`, reboot
  (fastest for DT work, ~2 min, NO kernel build, NO flash).** extlinux loads the
  `fdt` separately from the kernel Image, so a DT-only edit never needs a rootfs
  flash or even a `make Image`. DTC is arch-independent (cpp+dtc), so on the host:
  `make ARCH=arm64 CC=gcc HOSTCC=gcc qcom/<board>.dtb` (seconds), then `scp` it to
  `/boot/<board>.dtb` (back up the old one first), `sync`, reboot. Verify the change
  took with the on-device ground truth for that subsystem (e.g. pinmux via
  `/sys/kernel/debug/pinctrl/*/pinmux-pins`, clocks via `/sys/kernel/debug/clk/*`),
  and confirm the deployed DTB md5 matches the one your committed source compiles to.
  (Worked example folyt.208: 4-5 DTB iterations in one session localised the WCD9335
  MCLK `func1` pinmux — each cycle ~2 min, vs a ~45 min apk build.)
  - **☠️ Once the change also lives in a package, deploy the DTB from the BUILT PACKAGE,
    not from your source tree.** The host `make …dtb` writes into the tree, and that file
    goes stale the moment you rebase, cherry-pick or let the package apply patches — you
    then flash a DTB that does not correspond to the kernel you installed. Symptom: the
    driver loads, the node is simply absent, and you debug a device tree that was never
    deployed. (Cost this once: after cherry-picking the camera series onto the audio branch
    the copied DTB was the pre-cherry-pick one, so `imx363` never probed and the media graph
    stayed empty.) Extract it from the apk (`boot/dtbs/qcom/<board>.dtb`) whenever the
    package is the thing you built, and keep the source-tree `make` for pure DT iterations.
- **Kernel image / built-in (`=y`) code changed → full rootfs flash** (see below;
  slow, must run backgrounded).
- **ADSP firmware changed → SSR-reload** (see the firmware section; ~2 s, no
  reboot).
- **A systemd unit is a deploy vehicle too — and ☠️ `ExecStart` EATS your shell variables.**
  systemd expands `$i` itself and hands the shell an empty string, so a retry loop's guard
  (`while [ $i -lt 30 ]`) silently breaks while the unit still reports success — the failure
  only shows up on the day the retry is actually needed. Write `$$i`, and **make the unit
  print the counter** so the log distinguishes the two (`rndis up after 0 tries` is right,
  `rndis up after  tries` means systemd ate it).
- **An in-tree DRIVER built as a module (`CONFIG_*=m`) → hot-swap the `.ko`, same as
  the SLIMbus case** — confirm `=m` first (`zcat /proc/config.gz | grep CONFIG_…`),
  build the kernel pkg, extract the `.ko` from the apk, vermagic-match the *running*
  kernel exactly, replace on-disk in `/lib/modules/…/` (keep a `.bak`), `depmod`,
  reboot. (Worked example 07-21: the `imx363` sensor driver A/B'd this way — swap in
  another dev's driver, or your own variant, in one build+reboot, no full flash.)

### Step 1a — camera / userspace bring-up (a second track, off the SLIMbus one)
Bringing a peripheral up *in userspace* (libcamera/pipewire/an app) adds its own
method traps, all learned 07-21 on the FP3 rear camera:
- **On-device runner scripts die when the SSH session closes** if the user isn't
  lingering (the systemd `--user` session tears down on last-logout, killing the
  `nohup`'d child → empty result log, process gone). Run the harness **foreground**
  (keep SSH open; a <2-min run fits the Bash cap) or `loginctl enable-linger`. This
  is distinct from the "persist output to a synced file" lesson — there the *output*
  was lost; here the *process itself* is killed.
  - **☠️ `setsid` does NOT save it** (confirmed 07-26): the process stays in the user's
    systemd slice, so a `setsid nohup` runner dies on logout with the exact same
    signature — empty log, no process, no result file. Only **foreground with the SSH
    session held open** (a ~30 s SSR measurement fits comfortably) or
    `loginctl enable-linger` actually works. Corollary: a long-running sampler that
    writes its file **only at the end** loses everything when killed — write
    incrementally, or keep the run short and foreground.
  - **☠️ `echo pw | sudo -S <cmd> … </dev/null &` — the `</dev/null` OVERRIDES the stdin
    carrying the password.** Sole symptom is one line in the log:
    `sudo: Authentication required but not attempted`, and the runner never starts. Put
    the redirect on the *inner* command (`sudo -S sh -c 'runner </dev/null &'`), never on
    `sudo` itself. This is the most common silent failure of the detached-runner recipe.
  - **☠️ `scp` can deliver a silently corrupted file.** A clean 25-line ASCII `.py`
    arrived containing null bytes → `SyntaxError: source code cannot contain null bytes`.
    Transfer small scripts with `base64 -w0` + `base64 -d` and verify with `md5sum` on
    both ends — otherwise a transfer bug masquerades as "the measurement returned nothing".
  - **☠️ A "wait for the result file" loop MATCHES THE PREVIOUS RUN'S FILE.**
    `until test -f out.txt` / `grep -q DONE out.txt` succeeds instantly against a stale
    file and you read the old measurement as new. Always `rm` the target file before
    waiting, and have the runner delete it at start.
- **`/tmp` is tmpfs → a script pushed before a reboot is gone after it.** Push
  on-device runners AFTER the reboot, or stage them on the rootfs (`/root`, `/home`).
- **For a user-facing reliability A/B, a passive `dmesg` detector beats a synthetic
  harness on this flaky-RNDIS device.** Clear dmesg, let the USER do N real cold
  launches (the faithful path: portal→pipewire→CAMSS), then read dmesg for the
  failure signature. Only short SSH commands (clear/read) — robust against the link
  drops that kill long harness sessions. And a synthetic harness that grabs the one
  camera **CONFLICTS with the user's concurrent app test** (both contend for the
  single device) → coordinate: one or the other, never both.
- **A userspace *config* can silently break the whole pipeline** — a libcamera
  `configuration.yaml` (`software_isp.mode: cpu`) BROKE camera enumeration entirely
  (`no camera found`), not just the debayer. Bisect userspace config with a config-OFF
  test before chasing the driver. (And note the env-var you assume maps to it may not:
  `LIBCAMERA_SOFTISP_MODE` is NOT read for that option — the code reads the config file.)
- **Disk-full aborts an `apk` upgrade mid-way → a half-upgraded stack → a mysterious
  crash.** A SIGBUS in `libpipewire-module-metadata.so` was a version skew:
  `pipewire` reached 1.6.8 but `gst-plugin-pipewire` stuck at 1.6.7 (disk-full killed
  its fetch). `apk info -v | grep <pkg>` is the consistency check; complete the
  upgrade to fix. (Also: `apk add --force-broken-world` REMOVES a pkg to resolve an
  unsatisfiable dep instead of installing it — with network it fetches the dep
  instead; without it, extract the `.apk` and lay files down manually as a stopgap.)
- **Powering a rail that has no driver, and talking to CCI-I2C from userspace** (used
  to bring up the AF VCM): a `regulator-fixed` with `gpio = <&tlmm N …>` is toggled
  by poking that TLMM GPIO high via `/dev/mem` (CFG `0x1000000+0x1000*N` OE bit9, IO
  `+4` bit1) — no driver needed. CCI-I2C (`/dev/i2c-3`, `Qualcomm-CCI`): Python
  `I2C_RDWR` combined write+read; use `I2C_SLAVE_FORCE`/RDWR to reach a DT-claimed
  address, and **chunk reads ≤12 B** — the CCI caps read length (256 B → `EOPNOTSUPP`).
  (Worked example: found the rear sensor at 0x1a not 0x10, dumped the module EEPROM
  @0x50, and drove the dw9714-class VCM @0x0c through a focus sweep, all via `/dev/mem`
  + `/dev/i2c-3`, no kernel changes.)
- **Userspace *audio* (pulseaudio UCM) has its own traps, learned 07-24 bringing the WCD9335 up
  through pulse (full detail in `llg179/fp3-pmaports/userspace-audio/README.md`):**
  (a) **Validate "works" with the REAL audio server, not raw `aplay`/`arecord`** — apps go through
  pulseaudio (or pipewire-pulse; `apk info -e` decides which), whose UCM layer behaves nothing like raw
  ALSA. (b) **pulse's UCM wrapper `_ucm0001.hw:CARD,N` may resolve only for PCM device 0** on a qcom
  card (`Unknown PCM …,1` while `aplay -D hw:0,1` works); any capture/2nd-playback SectionDevice on a
  non-0 device then poisons the whole card → `auto_null`. Fix: **multiplex every playback onto device 0**
  (pick the output with the ADSP front-end mixer, not the PCM number) and **expose capture as a raw
  `module-alsa-source hw:0,N` from a pulse drop-in, not a UCM device.** (c) **A q6asm front-end opens
  only once routed** (else `EINVAL`), and pulse runs only the **verb** EnableSequence at profile-probe →
  the verb must leave a valid default backend route. (d) **Re-cset-ing the codec input mux mid-stream
  goes silent** (the ADC power sequence, which releases the TX-hold, doesn't re-run) → switch the route
  only while the capture is idle (pulse suspends `module-alsa-source` between uses). (e) **Isolated
  profile-probe without wrecking the live session:** throwaway `pulseaudio -n … load-module
  module-alsa-card device_id=0 use_ucm=yes` + `kill -STOP`/`-CONT` (never `kill`) the greeter pulse.
  (f) **MBHC headset jack detection — mainline WCD9335 ships none; now SOLVED on the FP3** (branch
  `wcd9335-mbhc`; ported from the dropped 2018 Kandagatla series then re-worked to this codec's behaviour).
  Four transferable lessons, each of which cost a build cycle:
  - **The codec must own its jack.** The generic qcom machine driver (`apq8016_sbc`) hands its jack only to
    codecs on an *MI2S* link, so a SLIMbus WCD9335 never gets one via `.set_jack` (prove it: a `dev_info` in
    the codec's set_jack never fires) and every report goes to a NULL jack. Fix: create the jack in the
    **codec's** component probe (`snd_soc_card_jack_new(component->card, …)`). You then get **two**
    `Fairphone 3 Headset Jack` evdev nodes — the codec's (created first in component probe, lower `eventN`)
    is the live one; the machine driver's is dead. Test with `evtest --query /dev/input/eventN EV_SW
    SW_HEADPHONE_INSERT` (rc 10 = inserted, 0 = out), not the numid 70/71 controls (those are the dead jack).
  - **A status register read *inside* the IRQ handler can be the transient value.** `ANA_MBHC_RESULT_3`
    bit 3 (unplugged) reads its settling value 0 for the whole active-detection window after the edge — so a
    removal looks identical to an insertion and the jack sticks "inserted"; `msleep(400)` was not enough. The
    same register read in *steady state* (via debugfs, or at init) is reliable. Lesson: don't trust a volatile
    detection register sampled at the edge; drive direction from a **software state** flipped per IRQ and
    **seeded once at init** from the settled read.
  - **Edge-triggered detect blocks often detect one direction at a time.** WCD9335 `MECH_DETECT_TYPE` must be
    re-armed (written) on *every* edge or the opposite transition (in practice, every removal) never fires an
    IRQ at all — the jack silently sticks on the first insertion. Watch `/proc/interrupts` count: if it stops
    incrementing after one direction, you dropped the re-arm.
  - Verified by watching the evdev `SW_*` state track physical plug/unplug across many cycles with no drift;
    boot-with-headset-plugged handled by the init seed.
- **Voice-CALL audio on mainline qcom (msm8953/msm8916/sdm845…) is a SOLVED but not-upstreamed problem —
  don't reimplement it.** The pieces: (1) the **q6voice kernel patches** (Stephan Gerhold's msm8916 set:
  q6mvm+q6cvp+q6cvs+q6voice-dai) — `q6voice_path_start` creates a **passive/modem-controlled MVM + a CVP**
  (which binds the codec AFE Tx/Rx ports) and sends `START_VOICE`; it does **not** create a CVS session, and
  `q6cvs.c` being a ~36-line APR-registration is **normal** (same shape as q6cvp.c/q6mvm.c), NOT a stub bug —
  during a call the modem takes control of LPASS and owns the vocoder stream. (2) The **`q6voiced` userspace
  daemon** (`apk add q6voiced`; config `/usr/share/q6voiced/q6voiced.conf` → `q6voice_card`/`q6voice_device`
  for the voice PCM, e.g. hw:0,4=VoiceMMode1) — it opens/closes that PCM on call start/end. It listens on
  **both** `org.ofono.VoiceCallManager` **and** `org.freedesktop.ModemManager1.Call` dbus signals (check with
  `strings`), so on a ModemManager device you do **not** need oFono. (3) The **codec voice route** (earpiece/
  speaker downlink + mic uplink mixers) must be set — normally by a UCM "Voice Call" verb via callaudiod, and
  it must be set **before** q6voiced opens the PCM (same route-before-open EINVAL trap as media q6asm FEs).
  Opening the voice PCM by hand (`aplay`/`arecord`) is the wrong tool: it xruns/EINVALs — the FE only needs
  open+prepare (no data transfer), which q6voiced does correctly. Reference: postmarketOS q6voice(d) project
  + pmaports MR !1233. **The modem side also needs `soc-qcom-msm8953-modem` (pulls `tqftpserv` — the modem's
  EFS/NV access over QMI); enable `tqftpserv`+`rmtfs`, and REBOOT so the modem boots with EFS access** (a
  modem that came up without it won't pick up voice/NV config until restarted). ⚠️ **FP3 status (corrected
  2026-07-25): the modem↔LPASS bridge DOES work — proven live.** An earlier "both directions silent, bridge
  doesn't carry audio" conclusion was WRONG: it only ever tested the **earpiece** downlink (SLIMBUS_0_RX,
  through the WCD9335). Routing voice to the **speaker** instead (`QUIN_MI2S_RX Voice Mixer VoiceMMode1 1` →
  the AW8898 amp on MI2S, *not* the codec) put the far end's audio out the loudspeaker. The real gap is
  narrower and AP-side: **q6voice opens the AFE port via the CVP directly and never triggers the WCD9335's
  SLIMbus DAI** the way media DPCM does (`.hw_params` on the codec backend), so *anything through the codec*
  (earpiece SLIMBUS_0_RX, every mic SLIMBUS_0_TX) is silent in-call while the MI2S speaker works standalone.
  The CVP binds whichever Voice Mixer was set **last** (`q6voice-dai.c` `q6voice_set_port(…, mc->reg)`).
  Mic-path idea (untested end-to-end): co-open the media capture (`hw:0,1` → SLIMBUS_0_TX ↔ AIF1_CAP DPCM)
  during the call to power the codec Tx chain the CVP reads. Two traps that invalidated hours of testing:
  (a) **a second session running the audio selftest/`hwtest` contends for the one sound card** — during a
  live call, only ONE session may touch it; (b) login re-runs the HiFi UCM verb, ZEROing the codec downlink
  muxes — re-apply the voice route AFTER the call goes active.

### Step 2 — Build
☠️ **A kernel version bump can silently DROP config symbols, and the build stays green.**
Kconfig symbols get renamed upstream; `olddefconfig` discards a name it no longer knows
**without a word**, so a config carried forward from an older kernel quietly stops building
whatever that symbol selected. There is no warning, no error, and the package looks normal —
the failure only appears on the device as a missing feature. (Cost this a full session: the
FP3 panel driver was `CONFIG_DRM_PANEL_FAIRPHONE_FP3_HX83112B` up to 6.13 and
`CONFIG_DRM_PANEL_HIMAX_HX83112B` after it. With the stale name the panel module was never
built; `/dev/dri` did not exist and the compositor looped 73 times on
`phoc-wlroots-CRITICAL: Found 0 GPUs, cannot create backend` — which reads like a GPU or DRM
bug, not a config typo.)
- After any kernel bump, **verify the symbols you depend on still exist**:
  `grep -c '^config <SYMBOL>$' <tree>/**/Kconfig`, or simply check the module you expect
  actually appears in the built package (`tar tzf …apk | grep <module>.ko`).
- Better: assert on the *artifact*, not the config. A one-line "is the .ko in the package"
  check catches every rename, every dropped dependency, and every `olddefconfig` surprise.
- The generic lesson: **a green build is not evidence that your change is in the binary.**
  Whatever you rely on, confirm it exists in the output before you spend time on the device.
- **★ The artifact gate works for a DT change too, and needs no `dtc`.** The host often
  has no `dtc`, which tempts you to skip the check on exactly the edit most likely to go
  missing. A ~25-line FDT walker (read `magic`/`off_struct`/`off_strings` from the header,
  then loop `FDT_BEGIN_NODE`/`FDT_PROP`/`FDT_END_NODE` tokens) prints one node's properties
  straight out of the DTB **extracted from the built package**, proving the property is
  there *before* you flash — e.g. `required-opps = <0x5e>` under `remoteproc@c200000`.
  The driver-side twin is `strings <module>.ko | grep '<your dev_info string>'` run on
  **both** the old and the new package: the old one is the positive control that proves
  the grep would fire at all. Close the loop after install with `md5sum` of the deployed
  DTB against the package's copy.

🐢 **The kernel build silently bypasses ccache → every build is a full ~30-min recompile, even for a
one-line module change.** `cache_ccache_$ARCH/` exists and looks used, but the chroot's `/etc/abuild.conf`
ships `#USE_CCACHE=1` **commented out** (Alpine default), so abuild never prepends `/usr/lib/ccache/bin` to
`PATH` and the make calls the real `/usr/bin/aarch64-…-gcc`, not the ccache wrapper. Worse, **`--force`
zaps and recreates the buildroot every run**, resetting that file — and `--force` overrides `--lax`, so
`--lax --force` still zaps. Diagnose in seconds from a running compile: the parent of a `cc1` process
(`awk '{print $4}' /proc/<cc1-pid>/stat` → that pid's cmdline) is `/usr/bin/…gcc` when bypassed vs
`/usr/lib/ccache/bin/…` when active; and `cache_ccache_$ARCH/*/stats` mtimes are stale. **To actually use
it:** (1) uncomment `USE_CCACHE=1` in `work/chroot_native/etc/abuild.conf`; (2) set `hash_dir = false` +
`base_dir = /home/pmos` in `cache_ccache_$ARCH/ccache.conf` (each `_commit` builds in a different
`linux-<commit>` dir, so the default path-hash misses every file); (3) build with **`--lax` and *no*
`--force`** — and bump `pkgrel` to a value not yet in the work repo so `--lax` still rebuilds it without a
zap. First such build repopulates (slow); subsequent ones are cache-hit-dominated (~2–5 min). See the
[[feedback_pmbootstrap_ccache]] memory. (An env/SSD reshuffle can also orphan a previously-warm cache.)

```bash
rm -rf /tmp/pmbootstrap-local-source-copy
touch <edited-file>            # force pmb to see the change
cd $FP3_PMOS && ./pmb build --src $FP3_PMOS/linux-fp3 linux-postmarketos-qcom-msm8953
```
☠️ **`--src` wants an ABSOLUTE path.** `./pmb build --src src/linux-fp3 …` fails (`Invalid path specified
for --src`) — the wrapper does *not* resolve it relative to its own cwd. Always
`--src $FP3_PMOS/linux-fp3`. And **a mid-build `pkill` (e.g. aborting a broken-DT run to keep ccache)
leaves stuck bind-mounts** in `work/chroot_native/…` (dev, dev/shm, dev/pts, mnt/pmaports, ccache, apk/keys)
→ the next build's zap fails `umount exit 32`, and `pmb shutdown` alone often doesn't clear them → after a
mid-build kill it is MANDATORY to `sudo pkill -9 -f 'pmbootstrap|chroot_native|abuild'` then explicit
`sudo umount -l` deepest-first on every `chroot_native` mount before rebuilding (ccache on sdb2 survives the
zap, so the rebuild is still fast).
If the build dies zapping buildroots (`umount … exit 32`), the cause is **stale
chroot mounts** from an interrupted run. Method to clear any pmb wedge: `./pmb
shutdown`, then lazy-umount every leftover mount:
```bash
for m in $(mount | grep chroot_native | awk '{print $3}' | sort -r); do echo <pw> | sudo -S umount -l "$m"; done
```
(Same class of failure shows up as a stale `work/tmp/apk_progress_fifo` blocking
`pmb flasher` — `pmb shutdown` + `rm` the fifo. Whenever pmb fails *instantly*,
suspect leftover state from the last run, not your change.)

**Build- and deploy-time traps that point at the wrong culprit:**

- **☠️ Never pad an abbreviated commit hash.** `_commit` needs all 40 characters;
  extending the 12 from `git log --oneline` by guessing gives a GitHub 404 during
  `checksum` that reads like a failed push. Take it from `git rev-parse`, or
  better `git ls-remote fork <branch>`, which also proves the push landed.
- **☠️ Never run a second pmbootstrap command while a build is running.** They
  share `/home/pmos/build` in the chroot, so a `checksum` issued mid-build deletes
  the running build's source tree and it dies with
  `fatal error: ./include/linux/compiler-version.h: No such file or directory` —
  an error that points squarely at the kernel source and not at you.
- **☠️ `apk add` ending in `1 error` is usually the phone having no route to the
  repositories**, not a bad package (`DNS: transient error`); the local apk still
  installs, `apk list -I` proves it. It matters because a deploy script with
  `set -e` stops right there and silently skips everything after — in one case the
  whole extlinux fix-up, leaving no fallback entry, no `panic=10` and no menu
  timeout on the next boot. Verify the file, do not assume the script finished.
- **☠️ The device fills up at ~30 MB per kernel apk.** On a 2.4 GB rootfs a day of
  iteration reaches 99% and the phone raises a low-disk notification long before
  anything visibly breaks. Clean `/home/*/*.apk` and `/var/cache/apk` between
  rounds — and see the journal-vacuum warning above before reaching for it.

### Step 3 — Deploy the heavy vehicle (flash) without tripping the Bash cap
**The #1 operational gotcha:** the Bash tool hard-kills at 10 min. `pmb install`
(rootfs regen) alone exceeds that, and a foreground kill mid-flash can strand the
device at a bootloader splash. **Method: run the whole install→flash→boot→capture
chain detached, poll the log.**
```bash
nohup ./fp3-porting-debug/scripts/test-slim-kernel.sh > $FP3_PMOS/slimtest-run.log 2>&1 &
# then, in a SEPARATE call (foreground sleep is blocked — use a background until-loop):
until grep -qE "DONE ->|ERROR:|Traceback" $FP3_PMOS/slimtest-run.log; do sleep 15; done
```
Hygiene the chain must do (do it manually if driving stages by hand): `pmb
shutdown` + umount-loop before `pmb install`; `ssh-keygen -R <ip>` (or
`UserKnownHostsFile=/dev/null`) before the first post-flash SSH, since the rootfs
regen changes the host key. `pmb build` alone (~8 min) fits one foreground call.

### Step 4 — Read the result as your pre-declared measurement
Compare against the pass/fail you wrote in Step 0. Express both as concrete
signals so the answer is unambiguous. (Worked example, framer bring-up:
**pass** = NGD `INT_STAT != 0` *and* the codec's `Failed to get logical address`
line is gone *and* `/sys/bus/slimbus/devices/` shows a codec laddr; **fail/baseline**
= `capability exchange timed-out`, NGD `STATUS=0x40c CFG=0x0 INT_STAT=0x0`, no
soundcard.) A result that matches neither is usually "code didn't run" — check
your DBG breadcrumb.

### Step 4h — Human-in-the-loop physical tests: strict handshake, never a timer
Some signals only exist while a human performs a physical act you cannot script:
plug/unplug the 3.5 mm jack, press a headset button, insert/remove the SIM,
connect the charger, speak into the mic, listen on the speaker, place/answer a
call. For these, **a read is only meaningful against a *confirmed* physical
state.** Discipline (learned the hard way — a timing-window test produced hours
of invalid data because the human was multitasking and an edited chat message
desynced us):

- **One action at a time, then wait for the human's explicit "done".** Never
  "plug in sometime in the next 30 s" and sample on a timer — the human
  multitasks; the window and your reads will not line up, and you will draw a
  confident wrong conclusion. Say exactly one action, stop, and read *only after*
  they confirm it is complete.
- **☠️ Wait for their "go" as well, not only their "done" — and never start the
  capture in the same message that explains it.** Twice in one session a timed
  read was launched together with the instructions, so the window opened while
  the human was still reading; one run produced 14 of 15 empty samples and an
  hour went into explaining a "wedged sensor" that was an empty room. The human
  said it plainly: *"if I have to test, wait until I type something."* Post the
  instruction, stop, and start only on their reply.
- **Baseline first.** Capture the instrument in the known starting state (jack
  out) before any action, so the A/B delta is unambiguous.
- **Re-confirm the physical state before interpreting** — a late or edited
  message can retroactively invalidate a read. If a reading is surprising, the
  first hypothesis is "we were out of sync", not "the hardware is broken".
- **Keep a monotonic ledger** the human cannot desync you on: an edge counter
  (`/proc/interrupts`) or a **volatile** status register that tracks the physical
  state live (find one — cached regmap values show the last *written* value, not
  the pin; only `volatile_reg` entries read through to hardware). One IRQ /
  status-flip per confirmed action = clean; a mismatch = you are desynced, redo.
- **Separate "HW detects it" from "the stack reports it".** The edge firing +
  the volatile status flipping proves the *hardware* path; the userspace surface
  (jack kcontrol, input `SW_*`, `evtest --query`) not moving despite that proves
  the *report* is lost downstream (e.g. a NULL jack pointer, or set_jack wired to
  the wrong codec). Read both every step so you know which half is broken.

---

## Building & deploying a base-bumped kernel (envkernel + parallel package)

When the change is a whole new base (e.g. porting the FP3 tree from 7.0.9 to
7.1.3), the deploy vehicle is heavier than a hot-swapped `.ko`. Two build paths:

### Fast compile-check with `envkernel` (no device, catches your edits)

`pmbootstrap`'s `helpers/envkernel.sh`, sourced from the kernel dir, wraps `make`
so it cross-builds inside the chroot (out-of-tree in `.output/`). Setup gotchas
that cost real time:

- **pmbootstrap must find its config.** It reads
  `${XDG_CONFIG_HOME:-~/.config}/pmbootstrap_v3.cfg`; if the real config lives
  elsewhere (`/mnt/1TB/pmos/pmbootstrap_v3.cfg`), symlink it there or envkernel
  triggers a fresh `pmbootstrap init` and dies.
- **`.output/` is owned by the chroot user (`pmos`)** — you can't `cp` a config
  into it from the host (permission denied → `olddefconfig` silently falls back to
  `arch/.../defconfig`). Place it *through* the chroot:
  `pmbootstrap -q chroot --user -- cp /mnt/linux/fp3.config /mnt/linux/.output/.config`.
  (Put the file in the source tree first so it's visible at `/mnt/linux/...`.)
- **The source tree must be clean of a stray `.config`** or the `outputmakefile`
  target errors — with `O=.output` the config lives in `.output`, never the srcdir.
- **The DTB target doubles its path** (`make …/qcom/foo.dtb` → "No rule … dts/arch/
  arm64/…"). Use **`make dtbs`** instead — it builds the board DTB and validates
  the DTS.
- **Targeted objects = fast feedback.** `make drivers/x/y.o sound/.../z.o` compiles
  just your changed files (after a one-time scripts/headers build); a clean `.o`
  proves your conflict resolutions. A full `make Image modules` (≈30 min, envkernel
  forces `CCACHE_DISABLE=1`) is only needed to catch link/modpost and to flash.
- Enable a symbol the config lacks: `scripts/config --file .output/.config -m
  CONFIG_FOO` (through the chroot), then `make olddefconfig`.

### Config-migration gate (silent-feature-loss trap)

`olddefconfig` migrates the old config to the new base and **drops unknown symbols
without a word** (the `DRM_PANEL_*_HX83112B` rename is the canonical case → no
display). After the bump, re-apply the package's `prepare()` enables and **verify
the critical symbols survived**: panel, `SND_SOC_WCD9335`, `SND_SOC_AW8898`,
`VIDEO_IMX363`, `CHARGER_QCOM_SMB2`, `SLIM_QCOM_NGD_CTRL`, `QCOM_Q6V5_PAS`,
`SND_SOC_QDSP6_Q6VOICE_DAI`. A `grep` of `.output/.config` is the gate, not "it
built".

### Flashable build = a parallel package (don't disturb the daily driver)

To get a bootable image with a **matching initramfs** (a bare `Image` copy won't
mount the rootfs), build a package — but as a *second* one so the working kernel
stays installed. Copy `linux-fp3-709` → `linux-fp3-713`, bump `_flavor`,
`_commit` (the pushed integration SHA), `pkgver`; rename `config-$_flavor`; then
`pmbootstrap checksum linux-fp3-713` (needs the commit pushed first — 404 trap)
and `pmbootstrap build linux-fp3-713`.

### Base-bump device deploy, brick-safe

- **Free the rootfs first.** slot_b sits near 100%; `/var/cache/apk` is often
  ~200 MB of reclaimable cache (`rm -rf /var/cache/apk/*`, `journalctl
  --vacuum-size=4M`) — new modules (~40 MB) won't fit otherwise, and 100 % also
  kills the graphical session.
- **Back up the working boot set** before touching it: copy `/boot/{vmlinuz,
  initramfs,<board>.dtb}` and `extlinux.conf` to `*-709recovery`. The rootfs and
  these copies surviving = recoverable, not bricked.
- **Deploy the new kernel as separate `-713` files** + a **second extlinux entry**,
  leaving the 7.0.9 entry the default. Install the new modules, regenerate the
  initramfs on-device (`mkinitfs` for the new release), then to test flip
  `default` to the 713 entry and reboot.
- **Revert-on-success.** The only way to test unattended is to make 713 the default
  for that boot; there is **no auto-fallback** on this bootloader. So the moment SSH
  returns, flip `default` back to 7.0.9 — a later power-cycle then recovers on its
  own. If SSH never returns, 713 didn't boot; recovery needs the `*-709recovery`
  set restored (physical/next session), so only spend a paid/unattended flash when
  the compile + config-gate are green.

---

## The instruments: what each measures, how to read it, how to read it

Pick the instrument that answers your Step-0 signal question. For each: the
question it answers, the how, and how to interpret — with example values.

### MMIO registers via `/dev/mem` (the ground truth of a HW block's state)
- **Answers:** is the block configured/clocked/interrupting the way software
  thinks? Registers don't lie the way logs can.
- **How:** Python `mmap` reader (not `dd`/`devmem`, rule 6). Get the block's base
  from the DT/`/proc/iomem`; read control/status/int registers. Only touch a block
  you know is clocked (rule 4).
- **Interpret:** compare the *written* value to the *read-back*. A write that
  doesn't latch (reads back 0 after you set it) means the block's clock/framer is
  dead — the write is being dropped. (Worked example: NGD `@0xc141000`, CFG+0x0 /
  STATUS+0x4 / INT_STAT+0x14. Golden-active: `CFG=0x7 STATUS=0x000d040e
  INT_EN=0xbe000000`. Test-side: all-zero / `0x40c` — writes don't latch ⇒ the
  co-processor never framed the bus.)
- **☠️ "reads back 0" can be a HARDWARE SELF-CLEARING bit, not a dropped write — measure the DECAY
  TIME before concluding, and always run a positive control on a side-effect-free neighbour.** Some
  enable bits clear themselves in hardware within <100 ms if a precondition isn't met (worked example:
  `NGD_CFG.ENABLE` at `0x0c141000+0x00` falls back to 0 in <100 ms if the bus isn't framed). A "read it
  back a second later" check then sees `0x0` and looks like a dropped write / driver bug — a false lead
  that stood for years. Method: **write + immediate readback in the SAME instruction stream**, then
  sample at 100 ms intervals to see the decay; and write a known value to an adjacent no-side-effect
  register (`NGD_INT_EN` ← `0xfe000000` LANDS) to prove writes reach the block at all. Once identified,
  a self-clearing bit becomes a FREE proxy marker ("does it hold? ⇒ the bus clock is running"). (A
  resting two-sided diff cannot exclude such a self-clearing pulse either — see the porting-debug §3
  caveat; only a live same-instruction capture sees it.)
- **★ Before you build a firmware CAVE to read a co-processor-internal peripheral register,
  check whether the AP already maps the *same physical block* — a `/dev/mem` read is far cheaper
  than a cave.** A register the co-processor addresses in *its own* local view (e.g. an LPASS block
  the ADSP sees at `0xeeXXXXXX`) is usually the **same physical hardware** the AP maps at a different
  aperture — and the two addresses **share the low offset**. On this SoC LPASS_ADSP `0xee000000` and
  LPASS_AP `0x0c000000` alias the same LPASS, so the ADSP's framer `0xee140000` **is** AP-physical
  `0x0c140000` — which the NGD driver already maps (`/proc/iomem`: `0c140000-0c16bfff c140000.slim-ngd`,
  176 KB, covering `+0x600`). Method: find the AP driver's reg region in `/proc/iomem` that shares your
  target's low offset; if it covers the offset, **force the block's clock on** (runtime-PM
  `echo on > .../<dev>/power/control`, rule 4) and Python-`mmap` `/dev/mem` at the AP base + offset.
  (Worked example, folyt.139: AP `0xc140000+{0x000,0x600,0x604,0x610,0x020}` read **byte-identical** to
  what the FRS1/6 firmware caves captured at ADSP `0xee140000+…` — the whole MMIO-cave apparatus was
  unnecessary for the framer registers; caves are only needed for a register with **no** AP aperture,
  or for a value at a specific *code* instant.) **Two caveats:** (1) the AP aperture may cover only part
  of the co-processor's register map — a *sibling* block (a PHY/pad) can live in a *different* AP region
  (or none), so re-check `/proc/iomem` per block. **But the alias often covers more than the one driver
  region** — the LPASS_AP window is a whole-LPASS alias, so the framer's *clock controller* (ADSP
  `0xee000000` → AP `0x0c000000`, framer RCGR/CBCR at `+0x12004/+0x12014`) reads from the **same**
  `/dev/mem` alias, even though no AP driver maps it in `/proc/iomem`. Try the aliased base directly
  before assuming "no aperture". **Consequence (folyt.142): the entire two-sided framer+clock
  differential needs NO flash, NO SSR, NO slot-swap** — just `dump_lpass_regions.py` (auto force-resumes
  the NGD, reads both regions) on each slot at steady state, then `diff_lpass_regions.py`. That diff
  proved the whole LPASS clock-controller (`0x14000`) functionally byte-identical UT↔pmOS (PLL
  `L_VAL=0x20`, `USER_CTL=0x0022830f`, RCGR `CFG=0x509`, CBCR=1; the only differing word `0xc001024`
  = `PLL_TEST_CTL_U`, benign) → **C1 clock definitively excluded** with a clean live differential, no
  device round-trip. (2) The
  runtime-PM force-resume **perturbs** the block — resuming the NGD drove the framer's dynamic markers
  (`+0x200/+0x400`) from their idle `0` to activity values while the real state bit (`FS`, `+0x604`)
  stayed `0`; stable *config* registers don't move, but read *dynamic* ones knowing the resume drives them.

### dmesg signatures (the driver's own narrative — fast, but interpret carefully)
- **Answers:** which code paths ran and how far the handshake got.
- **How:** grep for the subsystem + your DBG breadcrumbs.
- **Interpret:** a *timeout* line tells you where the handshake stalled, not why.
  Cross-check the claim against a register (a driver can log "OK" and still have
  the HW silent). Treat logs as pointers to a register/state to verify.

### Enumeration sysfs (did the bus actually come up?)
- **Answers:** did the downstream device get discovered / addressed?
- **How/interpret:** presence of a device dir + an assigned address = the bus
  reached that stage. (Worked example: `/sys/bus/slimbus/devices/<laddr>` and a
  populated `/proc/asound/cards` = framer up; a device dir with *no* `laddr` =
  discovered but never addressed = framer down.)

### QMI/QRTR census (who is talking to the co-processor)
- **Answers:** is the remote service present, on which node, and are requests
  getting responses?
- **★ Start with the two-sided SERVICE INVENTORY, before touching any endpoint.**
  Downstream/UT: `cat /sys/kernel/debug/msm_ipc_router/dump_servers`. Mainline:
  `qrtr-lookup`. Two commands, and the diff localises the gap by itself.
  ☠️ **The instance field is PACKED: `version | (instance << 8)`** — a raw `0x3201`
  means *version 1, instance 50*, and the two tools print raw vs decoded columns
  differently, so an undecoded comparison is meaningless. (Worked example 07-28: the
  oracle advertises the Sensor Manager **twice** — service 256 on node 5 at raw
  `0x3201` (v1/inst50, the functional one, and exactly what the upstream `qcom_smgr`
  driver matches) and on node 7 at raw `0x0100` (v0/inst1). Mainline has only the
  node-7 one. One diff, and the missing piece was named.)
- **★ A userspace QMI client needs no kernel build at all** — worth doing *before*
  writing a driver, to find out whether the service answers. Python:
  `socket.socket(42, SOCK_DGRAM)` (AF_QIPCRTR); the address is a **`(node, port)`
  tuple**, not packed `sockaddr` bytes (`TypeError: must be tuple` otherwise); and
  **`bind((<local_node>, 0))` is mandatory** — without it the socket's port stays 0
  and replies never arrive. Message: `struct.pack('<BHHH', 0x00, txn, msg_id, len)`
  + TLVs; the response TLVs parse in a few lines.
- **How (traffic):** `fp3-porting-debug/scripts/qrtr_lookup.py` (example: ADSP = node 5, SLIMbus service
  0x301). Note that these logs typically show message *headers* (service, msg-id,
  length), not payload — enough to see *whether* and *what type* of message flowed,
  not its field values.
- **Interpret + caveat:** matching message length/type against the oracle tells you
  the transport works and the request shape is plausible. It does **not** prove the
  content is semantically different when it differs, nor equal when it matches —
  two QMI frameworks encode the same fields to different byte-lengths. (Worked
  example + trap: the golden select-instance frame was longer than mainline's, which
  *looked* like a missing field — but the oracle's own kernel source encodes the
  same two fields, so the length delta was framing, not a semantic field. Don't
  build a fix on a length delta without confirming the *fields* differ.)

### Clocks (is the block even powered/clocked)
- **Answers:** which clocks are on, at what rate, parented where.
- **How:** `clk_summary` if present; on older frameworks read per-clock
  `/d/clk/*/{enable,rate,parent}`.
- **☠️ Column gotcha — `clk_summary`'s `enable_count` is the *1st* field after the
  clock name, not a later one.** The columns are `name enable prepare protect rate
  accuracy phase duty hw_enable`; the *5th* number after the name is `accuracy`, not
  enable. A parser that reads the wrong column silently reports **zero enabled
  clocks** on a system that clearly has some — verify your parser against a clock you
  *know* is on (`xo`, a cpu-pll) before trusting a "nothing is enabled" result.
- **Interpret:** compare the oracle's clock set to the test side's. **Prefer the
  enable-*count* diff during the active event over an idle snapshot** — an idle
  snapshot can miss a boot-transient clock (wrong timing proves nothing about a
  negative), whereas "which clocks have `enable_count>0` while audio plays" is a
  hard differential and needs *only* debugfs (no `/dev/mem`, so no devmem kernel and
  no gated-register hazard). (Worked example: golden idle shows *no* audio/lpass/slim
  AP clock on — suggestive that the SLIMbus core clock is co-processor-internal — but
  the *decisive* version is the active-audio enable-count diff on the oracle, which
  needs no MMIO at all.)

### genpd performance state (is a power domain actually being voted — and WHEN)
- **Answers:** does the AP request a performance level (voltage corner) from a power
  domain, and at what level, during the window that matters.
- **How:** `/sys/kernel/debug/pm_genpd/pm_genpd_summary` — the `performance` column on
  the domain row, plus the per-consumer child rows underneath it.
- **☠️ A steady-state snapshot of a remoteproc PROXY power domain is actively
  misleading.** `qcom_q6v5_pas` votes its proxy PDs at `INT_MAX`
  (`qcom_pas_pds_enable()` → `dev_pm_genpd_set_performance_state(pds[i], INT_MAX)`) and
  **releases the vote at handover**, so once the co-processor is up the summary reads
  `performance 0` — which looks exactly like "nobody ever voted", even though the domain
  was at maximum for the whole boot. Measure the vote by **sampling across a controlled
  SSR**, never with a resting snapshot. (Worked example 07-26: this single distinction
  killed an entire hypothesis — that mainline fails to vote a CX corner for the ADSP —
  by showing `cx_perf = 2147483647` for ~160 ms right after `echo start`.)
- **☠️ A single snapshot means nothing even for non-proxy domains** — a shared rail
  oscillates with its other consumers (the CX rail here flips `0`↔`256` from display
  activity alone). Sample, and report the max over the window, not a point reading.
- **Interpret:** `INT_MAX` (2147483647) is "max out this domain", and it dominates any
  `required-opps` you might add — so adding `required-opps` to a node whose PD is already
  proxy-voted is a **no-op**, and shipping it would falsely imply the vote was missing.
  Check `proxy_pd_names` in the driver's resource struct before theorising about a
  missing corner vote.

### The golden oracle capture (when you can't probe the oracle live)
- **Answers:** what does the *working* system emit during the exact handshake you're
  debugging?
- **How:** boot `slot_a`, capture its ipc_logging/trace during the event
  (`fp3-porting-debug/scripts/ut-capture-framer.sh`). Reading an ipc_logging buffer **drains**
  it — drain once at T0 so a later read is a clean delta.
- **Interpret:** this is your reference for every header/timing diff. Save the files
  (`ut-framer-golden-*/`); they encode the target sequence and timing (e.g. "master
  capability arrives ~2 ms after the power-request response").

### Forcing a co-processor restart to re-run its init (repeatable trigger)
- **Answers:** lets you re-observe a *boot-time* handshake without a full reboot.
- **How:** `echo stop >…/remoteproc2/state; sleep 2; echo start >…` — remoteproc
  re-`request_firmware`s (so it also picks up a swapped firmware file) and the
  co-processor re-runs init. **Do it in one foreground command** (a backgrounded
  stop-sleep-start gets its `start` killed by sudo session teardown, leaving the
  co-processor offline).
- **Interpret / caveat:** on a clean kernel this is a ~2 s loop; on a dirty/hacked
  kernel the stop path can reboot the device — keep cold-boot as fallback. Note some
  co-processor state only initialises on a *cold* boot; if a reload behaves
  differently from a boot, that itself is a clue.
- **★ SSR-reload IS the robust firmware-deploy vehicle on the dead/PAS side — prefer it
  over cold-boot-and-read when the OS is already up.** A cold-boot deploy (swap `adsp.mbn`
  → `reboot` → wait → read) is at the mercy of this device's boot flakiness: a *warm*
  reboot (`systemctl reboot` / `fastboot reboot`/`continue`) frequently drops to fastboot
  instead of booting the slot (only a **cold power-cycle** boots reliably), and a dirty
  rootfs from a prior crash-loop makes the slot loop. All of that evaporates if you never
  reboot: `cp signed.mbn …/adsp.mbn; echo stop >…/remoteproc2/state; sleep 2; echo start
  >…; sleep ~8` re-loads the *swapped* firmware and re-runs the co-processor's full init
  (including its early clock-enable path) with the OS staying up — then read SMEM
  immediately. A whole firmware cave-experiment cycle in ~10 s with zero reboot lottery.
  (Worked example: the framer-branch-enable capture on the dead side that repeatedly failed
  as a cold-boot deploy succeeded first try via SSR-reload; the co-processor's clock-enable
  stores fire during SSR re-init exactly as at boot.) Restore-and-heal the same way (`cp
  .stockbak …; SSR-reload`), no reboot needed.
- **★ When the out-of-band link is flaky, the on-device runner must persist its result to a
  disk file, not just stdout — otherwise a link drop mid-measurement loses the whole run.**
  This device's host↔device USB-NCM link drops unpredictably (re-enumerates with a new MAC →
  stale-ARP "No route to host"; ~~sometimes vanishes entirely until a physical replug~~ — both of
  those are fixed now: the host flushes the stale neighbour entry on every link change and the
  device re-binds its own UDC when the link jams, see [Unattended access](../../../../README.md#unattended-access-no-on-device-login-no-usb-replug)). If you
  drive the SSR-swap→reload→read→heal chain as one *interactive* SSH command and the link
  dies at second 3, the co-processor still ran and wrote SMEM, but you never see the readout
  and the next reboot clears SMEM — the measurement is gone. Fix: stage a small **on-device
  runner script** that does the whole chain locally and `tee`s its output to a file on the
  device's own rootfs (e.g. `… | tee /root/ckb9-result.txt`). Now a link drop costs nothing —
  reconnect and `cat` the file, or if the link stays dead, retrieve it **cross-slot** (boot the
  oracle slot, loop-mount the dead slot's rootfs, read the file). Stage the runner + its inputs
  (signed `.mbn`, SMEM reader) onto the dead slot's disk cross-slot *before* booting it, so the
  measurement needs only one brief connection to launch — or none, if you make it a boot-time
  oneshot. (Worked example: `ckb9_pmos_onboard.sh` — swap→SSR→`python3 …read.py`→restore→heal,
  all `| tee /root/ckb9-result.txt`; three interactive-SSH attempts lost the read to link drops,
  the tee'd file survived the fourth.)
  - **☠️ Correction: a whole-run `{ big block } 2>&1 | tee f` still loses the late lines if the
    device reboots mid-run — pipe them to disk *directly*, with an explicit `sync`.** `tee`'s file
    only holds what the pipe *flushed*; the block's stdout is fully buffered, so if an SSR/boot
    flakiness reset hits before the block finishes, the file truncates at an *early* line and the
    critical tail (the SMEM readout you actually came for) is gone — even though the run "wrote to a
    file". Fix: write the one line that matters straight to a synced file *before* anything that can
    reset the device — `python3 read.py > /root/out.txt 2>&1; sync` — rather than relying on the
    outer tee-pipe to carry it. (Worked example, folyt.134: the FRS6 onboard truncated at
    `-- deploy FRS6 --` and lost the readout under the tee-pipe; the v2 runner writing the readout
    with `> $RES; sync` first captured it on the first try.)

### Runtime-PM as a reboot-free re-trigger for a "boot-time-once" event (the lightest lever)
- **Answers:** is a co-processor init you *assumed* was boot-only actually a runtime,
  repeatable event? And if so, can you drive+instrument it at will without any reboot/reflash?
- **Why it matters:** "it's boot-time-once, SSR won't re-run it" is a claim that is easy to
  assert from the *broken* side (where the event never succeeds, so of course nothing re-runs)
  and wrong on the *working* side. Test it before building a whole reflash-per-iteration cave loop.
- **How:** find the driver's runtime-PM node (`find /sys/devices -path '*<blk>*/power/runtime_status'`),
  confirm it's *supported* (status is `active`/`suspended`, not `unsupported`), then cycle it:
  `echo auto > .../power/control` + idle → **autosuspend** (issues the co-processor's power-down,
  e.g. QMI POWER_REQ INACTIVE); `echo on > .../power/control` → **forced resume** (power-up /
  POWER_REQ ACTIVE). Read the block's status register via `/dev/mem` between steps (safe here
  because the resume clocks the block; see rule 4b for the suspended constant).
- **Interpret:** if the status register *cycles* (down on suspend, back up on resume) the event
  is runtime-repeatable and you have a reboot-free harness — ftrace/register-watch/fw-cave the
  transition at will. If it stays down on resume, the runtime path differs from boot (still a clue).
  (Worked example: the SLIMbus framer was believed ADSP-boot-only; the NGD controller
  `c140000.slim` runtime-PM node cycles `FRM_STAT` `0x40`(gated)↔`0x060d1901`(framed) on
  `echo auto`/`echo on` — a reboot-free framer bring-up on the working slot. The AP side of that
  resume, by ftrace, does *nothing* subsystem-specific — no clock/regulator/regmap — just the
  untraced QMI, confirming the work is all co-processor-internal.)
- **Caveat — mechanism parity for a two-sided diff:** the downstream (oracle) driver may support
  runtime-PM `control` while the mainline (SUT) driver reports `unsupported` — there you force the
  same power-req via unbind/rebind instead. The *trigger* (POWER_REQ re-issued) is the invariant;
  the AP mechanism to cause it differs per driver. Don't call the two non-comparable.

### remoteproc coredump (devcoredump) — the WHOLE co-processor memory, offline (the fat-pipe exfil)
- **Answers:** what is in the co-processor's *entire* runtime memory right now — every struct, heap,
  pointer graph — for unlimited offline analysis. This is the tool when a firmware-cave exfil (bounded
  by the tiny safe SMEM window, ~tens of bytes per SSR cycle) can't carry what you need — e.g. chasing a
  multi-level heap pointer graph. It is also **the only *safe* way to read the firewalled carveout**: an
  AP `/dev/mem` read of the remoteproc carveout wedges the device (safety rule 5), but the coredump path
  goes through the remoteproc driver's own legitimate mapping.
- **How (proven on this device, ~30 s, reboot-free-ish):** the mainline kernel ships it
  (`CONFIG_DEV_COREDUMP=y`, `QCOM_Q6V5_PAS`). (1) `echo enabled >
  /sys/kernel/debug/remoteproc/remoteprocN/coredump`; (2) trigger a crash — there is an on-demand
  **`crash` debugfs node**: `echo 1 > /sys/kernel/debug/remoteproc/remoteprocN/crash` (a graceful `echo
  stop > state` does **not** produce a dump — coredump fires only on the crash/recovery path); (3) the
  kernel recovers the co-processor (dmesg: `crash detected … type watchdog → recovering → is now up`) and
  exposes an **ELF** at `/sys/class/devcoredump/devcdN/data`; (4) `cp` it out, then `scp`. **Clean up:**
  `echo disabled > …/coredump` and `echo 1 > …/devcdN/data` (frees the devcd; it also auto-expires after
  ~5 min), so future crashes don't auto-fill the tiny rootfs.
- **Interpret / gotchas:** ☠️ `stat -c%s data` reads **0** — the size materialises only on *read*; use
  `cat data | wc -c` (or just `cp`) to get the real size. A **full** dump ≈ the carveout size (here
  ~16.98 MB of the 17 MB `0x8d600000-0x8e6fffff`); a *small* dump means the platform gave a **selective
  SMEM-minidump** instead (predefined segments — may miss the heap you want), so **always check the size
  first** to know which you got. The ELF is indexed by **physical** address (the firmware phdrs' paddr),
  while co-processor pointers are **virtual** — bridge VA→PA with the *static* firmware's phdr table
  (each LOAD carries both vaddr+paddr), then PA→file-offset with the coredump's phdr table. The dump
  holds **runtime** values (heap/BSS populated), unlike the static firmware image. (Worked example:
  `scripts/coredump_resolve.py` resolves an ADSP VA into the dump; it cracked the "framer ctx points to
  parent structs in runtime heap" chase that the 8-word-per-cycle SMEM cave could only sample.)
- **What the coredump does NOT contain: MMIO peripheral registers.** It dumps the co-processor's DDR
  carveout only (code/data/heap); hardware register blocks (the LPASS framer/clock/PHY at `0xeeXXXXXX`)
  are *not* DDR and are absent. So the dump *subsumes* the DDR-reading caves (a ctx/heap-struct scan is
  now an offline read of the dump) but *not* the MMIO-reading caves. For live register values you need
  either the **AP-aperture `/dev/mem` read** (the MMIO instrument above — try this FIRST, it's the
  cheapest and needs no cave/crash) or, if the block has no AP aperture, a firmware cave. Ranked for
  "I need a co-processor register": (1) AP `/dev/mem` at the aliased AP aperture + force-clock
  (validated, folyt.139); (2) firmware cave (only when the register is genuinely co-processor-private).
  **☠️ A custom coredump segment for MMIO (`rproc_coredump_add_custom_segment` + a dumpfn that ioremaps
  the block) LOOKS like the clean kernel-side way to fold MMIO into the dump, but it HANGS on this PAS
  setup — validated-and-rejected (folyt.140).** The mechanism registers fine (FP3's default path is
  `rproc_coredump`, which honours custom segments), *but the coredump runs AFTER `rproc_stop`*
  (remoteproc_core.c: `rproc_stop` → then `->coredump`), so by the time the dumpfn reads the block the
  SSR teardown has gated its clock → the MMIO read **hangs the recovery worker** → AP watchdog → dirty
  rootfs → reboot-loop (a full cross-slot recovery to escape). Only pursue it if you can keep the block's
  clock voted across the dump, or force `dump_conf=inline` so the dump runs in the crash context *before*
  stop — not worth it when the AP-aperture read already works. (DDR custom segments are fine; the hazard
  is MMIO-during-recovery specifically.)
- **When you still need a cave instead:** the coredump is a *snapshot at the crash instant* of one side.
  For a live value at a *specific* code point (mid-function state), or the two-sided both-sides-anchor
  capture, the firmware cave is still the instrument (see the RE track). Use the coredump for breadth
  (whole DDR, offline), the AP-aperture read for a live register, the cave for a targeted code instant.
  - **Before building a dead-side SSR-cave for a *resting* ctx field, read it from the coredump first.**
    Every non-transient field (pointers, config, last-cycle status objects, whole vtable chains) is
    already in the dump — a planned cave to fetch it is wasted. (Worked example, folyt.147: the
    framing-START dispatch-selector `ctx+0xe08`, the wait-status object `ctx+0xe54`, and the vtable
    chain all came from the coredump; the SSR-cave was unnecessary.) **The cave is only for what the
    coredump CAN'T hold: a return value / an in-progress wait / a mid-function transient** — those
    exist only live. To catch one, splice at a fn-INTERNAL single-word packet where the target
    register is still live (e.g. right after the wait, at the packet that loads its return value into
    a GPR), not at fn-entry. (Worked example, folyt.149: the framing-START capability-wait's actual
    return `-2 = timeout` was invisible in the resting coredump; a live cave spliced at `0xf04d15bc`
    — `r0 = memw(ctx+0xe54)`, where r0 still held the wait return — captured it, first try on SSR-reload.)

---

## Inspecting and patching the ADSP firmware (the RE track) — see `references/firmware-re.md`

When AP-side probes exonerate the AP (driver byte-complete, registers show the *remote* side
silent), the question moves into the co-processor firmware. The method — full recipes, offsets,
Hexagon encoders, and worked examples — is in
[`references/firmware-re.md`](references/firmware-re.md). The shape of it:

- **Firmware identity first:** byte-`cmp` oracle vs test-side firmware; identical ⇒ the difference is *environmental*, not the code — one result that reframes the whole search.
- **Disassembly:** unencrypted QDSP6 ELF32 (Hexagon) via LLVM, each PT_LOAD at its own vaddr.
- **Read what it decides:** find the devcfg property-read pattern; map the config-struct offsets the code branches on.
- **Runtime pointer chains:** static disasm bottoms out at `callr memw(obj+N)` / runtime-mapped bases — walk one pointer level per cold boot, resolve rodata/text hops offline. Know the NPA vote/rate framework (an "enable success" rc=0 is *decoupled* from the physical branch toggling); an enable has TWO sub-paths (NPA vote vs the config-group→HalHwIo register poke); a candidate leaf is only "the poke" once a positive control confirms it fires on the WORKING side.
- **Capture the register base:** splice the clock's own enable-method (found via the static registry: name→ID→ops-vtable→enable-method), filter by the registry-entry pointer. **RCGR (rate) ≠ CBCR (gate)** — capture what the enable primitive *actually writes*, not a handle/offset heuristic.
- **Patch + re-sign:** secure-boot off → testkey images load; map vaddr→file-offset per segment, `qtestsign -v3`. Works on the **pmOS/PAS** side (`qcom_q6v5_pas` accepts qtestsign's dummy signing). ☠️ **The UT/PIL side (`subsys-pil-tz`) REJECTS a qtestsign image — `adsp: Initializing image failed(rc:-22)`, ADSP never loads, cave never fires** (folyt.162). Confirmed causes: qtestsign emits a `HashSegmentV3`-*header* format + 1MB-aligns the first PT_LOAD, but stock UT wants the raw QC hashseg (no header, starts with a 32-byte hash) at compact offsets. The resign that works = **minimal-change** (`scripts/build_ut_cave_minimal.py`, folyt.163): keep the stock `.mdt` byte-for-byte, patch only the .text `.bNN` (on UT that's `adsp.b04`), update ONLY that segment's hash in the stock hashseg (stale sig unverified w/ secure-boot off). **QC hashseg format (RE'd folyt.163):** the FULL hashseg lives in `adsp.b01` (and is packed into `adsp.mdt` at file 0x234, right after ehdr+phdrs — NOT at the phdr's p_offset). Layout = `[0x28-byte header][ SHA256(seg_i) at 0x28 + i*0x20 ][signature][cert]`; seg1's own slot is zeroed; hash[0]=SHA256(ehdr+phdrs). So b04's hash = raw `SHA256(adsp.b04)` at hashseg **0xa8** (= `adsp.b01`+0xa8 and `adsp.mdt`+0x2dc — update both). The earlier "cert interleaves early" was an artifact of reading the hashseg at the wrong offset in the .mdt. (Deploy-tested? see journal folyt.163+.)
- **Exfil channel:** patch the firmware to write into SMEM (AP-readable); validate with a known constant; locate the stash offset from the live TOC, never a hardcoded one.
- **The entry-trace / cave pattern** (the workhorse "does F run, with what args?") + its ☠️ safety rules: positive control for "magic absent", never a cave-MMIO-read, cap the stash footprint, splice the convergence point, disasm-verify the *patched image* before signing, and prove the reboot actually happened.

## Recovery (getting back to a known state) — see `references/recovery.md`

Disposable + dual-slot, so nothing here is fatal; recognise the state fast. Full procedures in
[`references/recovery.md`](references/recovery.md):

- **`18d1:d001` is ambiguous** (fastboot gadget *and* pmOS CDC-NCM) — disambiguate by USB descriptor before assuming a boot-loop.
- **"ping works, ssh refused" is usually a missing host route,** not a brick — stabilise the link host-side once (pin iface name + static host IP).
- **CDC-NCM jam** (`NETDEV WATCHDOG`): the device self-recovers in minutes — wait passively or reboot the DEVICE. ☠️☠️ **NEVER** host-side USB/link restart (pushes it to non-enumerating, and can disconnect the USB-mounted `/mnt`).
- **A/B retry fallback** flips slots; `set_active` resets the count.
- **☠️ Keep the rescue wrappers OFF the thing you are testing.** `fp3-ssh`/`fp3-link` were symlinks into a **USB-attached** work disk, so they would have vanished at exactly the moment that disk was unmounted for a repower — the worst possible time to lose the way back in. Real copies (or symlinks into a repo) on the *system* disk.
- **A gadget parked in the wrong mode by the DEVICE cannot be fixed from the host** — measured: a leaf-port `authorized` toggle and a `usb` driver unbind/bind both left the device number and the gadget mode untouched, because neither drops VBUS, and the root hubs report `No power switching`. The lever is device-side (re-bind the UDC) or a hub with per-port power switching. See "Unattended access" in the repository README.
- **Truly wedged** (raw gadget / hung fastboot pipe) → physical Power ~10 s + Power+VolDown (needs the user).
- **A dead slot dropping to fastboot is almost never the `adsp.mbn`** (fw loads post-kernel) — fsck the dirty loop-rootfs from the other slot instead of re-flashing the ADSP.
- **Repair / pre-stage a broken slot's rootfs from the healthy slot** (`losetup -fP` → `e2fsck -y` → mount) — a ~2-minute offline edit, no reflash.
- **UT vendor firmware VFAT stuck READ-ONLY after a deploy+reboot** (`/dev/mmcblk0p1`; `mount -o remount,rw` returns rc=0 but `/proc/mounts` still shows `ro`, every write fails): a write + unclean Android reboot left a *"Duplicate directory entry"* corruption + dirty flag. **Fix (folyt.162):** unmount ALL p1 refs (bind-mounted into the LXC container: `/android/vendor/firmware_mnt` + `/var/lib/lxc/…`), `fsck.vfat -a -w /dev/mmcblk0p1`, remount rw, restore stock split fw, verify per-file md5, reboot. ⚠️ `grep mmcblk0p1` also matches `mmcblk0p13` (dsp) → collateral unmount; use an exact match and remount p13. Always back up stock `adsp.mdt adsp.b*` to a writable dir first.

## Worked example — see the umbrella skill

The SLIMbus/WCD9326 framer investigation is the case this whole skill is distilled
from. To avoid two copies drifting apart, the down-the-stack walk-through (register
probe → firmware identity → clock probe → entry-traces → QMI diff → co-processor-internal
clock) lives **once**, in `fp3-porting-debug` ("how the SLIMbus wall was localised").

The *method* lessons it teaches are already embedded in the sections above; the
*current* status of the investigation lives in the data pack bundled with the umbrella
skill — `fp3-porting-debug/references/slimbus-audio-context.md` §0
(verdict + open frontier), plus `FP3-slim-debug-journal.md` in the project docs — **not
here**, because a status pinned in skill text ages into a wrong claim. Re-measure before
trusting any specific number in this file.
