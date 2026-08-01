# Script index

> ⚠️ **AI-generated.** This page — and the code, device tree and tooling it
> describes — was written by Claude (Opus 5) working under the direction of
> Lajosházi, László Gergely, who reviewed every change and made or reviewed
> every measurement it rests on. Kernel commits carry `Co-authored-by: Claude`;
> anything prepared for the LKML carries `Assisted-by:` instead and never a
> `Signed-off-by` from the assistant, since only a human can certify the DCO.

What each script in this directory is for. Everything here is driven by
`fp3-env.sh` — source it (or let the script source it) so `FP3_PW`,
`FP3_DEV_IP`, `FP3_ROOT` and friends are set; see the repository README.

Runtime output goes to `$GEN` (see `README-generated.md`), never into this
directory.

### Environment and device access

| script | what it does |
|---|---|
| `fp3-env.sh` | FP3 bring-up — shared environment. Source this from the other scripts. |
| `fp3-env.local.sh.example` | Copy to fp3-env.local.sh (git-ignored) and fill in your own values. Anything you do not set falls back to the documented default in fp3-env.sh. |
| `fp3-ssh.sh` | fp3-ssh — SSH/scp to the FP3 dev device (pmOS) over the stable NCM link. Prefers key auth; retries with a neighbour flush when the link is mid-reconnect. |
| `fp3-link.sh` | fp3-link — host-side NCM link helper for the FP3 dev device (pmOS). `status`/`ip`/`wait`, plus `heal` (neighbour flush + NM bounce) and `install-key`. |
| `ut-ssh.sh` | ut-ssh — reach the device while it runs Ubuntu Touch, with no unlock and no replug: USB rndis, then WiFi, then UT's usb-moded rescue sshd. |
| `usb-repower-safely.sh` | Power-cycle a USB port without corrupting a USB-attached work disk (quiesce, clean SCSI delete, remount by UUID). Usually unnecessary — check the bus topology first. |
| `post-reboot.sh` | Config lives in fp3-env.sh; every value there has a documented default. |

### Flashing, slots and recovery

| script | what it does |
|---|---|
| `slot.sh` | A/B slot retry-count kezelés (fastboot módban!). usage: slot.sh get \| set [a\|b] \| active [a\|b] Megjegyzés: ezen az FP3 abooton a `set_active` NEM … |
| `flash-pmos.sh` | pmOS flash-szekvencia (fastboot módban). Tartalmazza a vbmeta-disable lépést, ami a hybris/AVB-gyanú miatt KELL ("Fairphone powered by android -> fast… |
| `flash-a10.sh` | Faithful, NON-INTERACTIVE re-implementation of Fairphone's flash_fp3_factory.sh for FP3-REL-Q-3.A.0136 (Android 10), with TWO deliberate deviations: |
| `twrp.sh` | TWRP indítás. Mivel `fastboot boot twrp.img` az FP3 abooton FAILED ('unknown reason'), két megbízható út van: 1) flash a boot_b slotra + set_active b … |
| `twrp-dd.sh` | TWRP-adb úton image partícióra írása (mert `fastboot boot` az FP3 abooton tiltott/megbízhatatlan). Sparse Android image-et simg2img-gal ír; nyers imag… |
| `to-twrp.sh` | IDLE → TWRP TÖLTÉS.  A mainline pmOS kernelben NINCS FP3/PMI632 charger+fuelgauge driver (csak qcom,pmi632-typec látszik, CURRENT_NOW=0) → pmOS-ben az… |
| `to-pmos.sh` | TWRP/recovery → back to pmOS: `set_active b` → lk2nd (`boot_b`) → pmOS. Only adds the "get out of TWRP first" step around the ordinary slot switch. (Fixed 2026-07-28: it used to `set_active a`, correct only in the pre-dual-slot layout.) |
| `swap-to-pmos.sh` | **NOT the way to switch OS** (that is `slot.sh set b` + reboot, no flashing). Reinstalls pmOS from scratch — use only when the pmOS side is broken, e.g. lk2nd was overwritten. |
| `swap-to-ut.sh` | **NOT the way to switch OS** (that is `slot.sh set a` + reboot, no flashing). Repair path only: restores the dev-enabled UT backup when slot a has been damaged. ☠️ Flashes TWRP onto `boot_b` (today lk2nd) and rewinds `userdata`. |
| `setup-dualslot.sh` | ONE-TIME dual-slot install: pmOS -> slot _b (rootfs on system_b), UT stays on _a. After this, OS-swap is a single `fastboot set_active a\|b` + reboot … |
| `boot-watch.sh` | Reboot + kimenet-detektálás: USB-net (=bootolt pmOS) VAGY vissza-fastboot (=bukott). A LOGFÁJL markerét figyeli (nincs pgrep self-match). Háttérben fu… |
| `flash-wait-capture.sh` | Wait for the device to appear in fastboot (user puts it there with Power+VolDown), then flash the already-built rootfs (pmb install already ran) to sy… |
| `sd-fsck.sh` | SD-kártya debug-log workflow: ha a telefon az SD-jére írja a boot/debug logot, a (vfat) "dirty bit" miatt máshol nem/koszosan mountolódik. Ez umountol… |
| `restore-pw.sh` | Restore sane PipeWire/ALSA state on the device: Amp Mode plus headphone and speaker volumes, and restart the user PipeWire stack. |
| `diag-pw.sh` | Dump the PipeWire/ALSA side of the audio state: Amp Mode enum, jack switches, sinks and current routing. |
| `ut-backup.sh` | Back up developer-enabled UT (slot a) partition images for installer-free pmOS<->UT swap. |
| `ut-discover.sh` | READ-ONLY discovery on UT (downstream slot_a) to find the real node paths the SLIMbus framer SSR-recovery trace will need, before we trigger anything. |

### Kernel / DTB / module deploy and test

| script | what it does |
|---|---|
| *(provenance: no script here)* | "Does what runs on the device trace to the installed package?" is answered by `fp3-pmaports/tests/fp3-selftest --only identity,dtb,modules` — kernel, device tree and module tree in one run. A script here would duplicate it and rot separately. |
| `test-slim-kernel.sh` | Install the freshly-built patched kernel into the pmOS rootfs, flash it to system_b (dual-slot), boot, and capture the slim/NGD bring-up dmesg (incl. … |
| `deploy-dtb-and-trace.sh` | Deploy a freshly-built sdm632-fairphone-fp3.dtb to the live pmOS /boot (extlinux loads it standalone), reboot, then capture the SLIMbus/NGD bring-up d… |
| `deploy-ko-dtb-trace.sh` | Deploy the rebuilt slim-qcom-ngd-ctrl.ko (CHECK_FRAMER_STATUS fix) + the slimbus-enabled sdm632-fairphone-fp3.dtb to the live pmOS, reboot, and captur… |
| `build_fg.sh` | Config lives in fp3-env.sh; every value there has a documented default. |
| `gcc_snapshot.py` | Zero-risk full GCC block snapshot for UT<->pmOS environmental diff (context §9 step 1). GCC (msm8953 qcom,gcc-msm8953) reg = <0x01800000 0x80000> is a… |
| `fdt_slim.py` | Minimal flattened-device-tree reader: walk a .dtb and print nodes and properties without needing dtc. |
| `build_ut_p1.py` | Build a UT p1 (vfat firmware) image from a PAS-signed adsp mbn, using the PROVEN compact-mdt + full-split recipe (folyt.80, confirmed vs ut-p1-hwl4.im… |

### Audio: routing, playback and capture checks

| script | what it does |
|---|---|
| `ear-tone.sh` | Call-independent earpiece OUTPUT test: route MultiMedia1 -> PRI_MI2S_RX -> PM8953 WCD earpiece and play a local tone. Proves codec earpiece + MI2S |
| `ear-tone2.sh` | Call-independent earpiece OUTPUT test with VERIFIED mixer state + MI2S clock check. Routes MultiMedia1 -> PRI_MI2S_RX -> PM8953 WCD earpiece, plays a … |
| `ear-tone3.sh` | Earpiece OUTPUT test v3 -- GUARANTEE the ALSA card is free first. Previous run failed with "Resource busy": PA auto-respawned / PipeWire held |
| `hph-test.sh` | Bisection: does the WCD ANALOG codec produce ANY sound? Route MM1 -> PRI_MI2S -> WCD and drive the HEADPHONE (HPHL/HPHR PA) instead of EAR. ~15s tone … |
| `spk-tone.sh` | List the speaker-path mixer controls (quinary MI2S / aw8898) and play a tone through them. |
| `verify-spk.sh` | Config lives in fp3-env.sh; every value there has a documented default. |
| `verify-spk2.sh` | Config lives in fp3-env.sh; every value there has a documented default. |
| `voice-test.sh` | Live in-call audio test harness for FP3 q6voice. $1 = earpiece \| speaker   $2 = duration seconds Frees the ALSA card from PulseAudio, sets the Voice … |
| `voicehold.py` | Open both playback+capture of the q6voice VoiceMMode1 PCM (hw:0,4) and HOLD them open without transferring data. The Gerhold q6voice driver starts the |
| `set-vol.sh` | Select the speaker sink in PipeWire and set it to a known unmuted volume. |
| `sink-check.sh` | Show what PipeWire currently sees: sinks, sources and the default routing (wpctl status). |
| `dapm-probe.sh` | Why is the earpiece silent despite aplay rc=0 + verified mixers? Hypothesis: the DAPM path MultiMedia1 -> PRI_MI2S_RX BE -> internal codec -> |
| `dapm-probe2.sh` | DAPM probe v2 -- fixes: (1) card name "Fairphone 3" has a SPACE, so iterate find output space-safely with `while read -r`; (2) keep a CONTINUOUS tone |
| `ucm-look.sh` | Print the device's ALSA UCM configuration for the card, including any .bak variants. |
| `ucm-why.sh` | Diagnose why UCM failed to load: check the ucm2 library includes, version and directory layout. |
| `fix-ucm.sh` | Restore the known-good UCM profile from its backup after a broken experiment. |

### Register and memory inspection

| script | what it does |
|---|---|
| `regdump.py` | Dump arbitrary MMIO register blocks through /dev/mem, page-aligned, with labels. |
| `regdump_pmos.py` | Read NGD + SLIMbus-BAM (v1.7.0) registers via /dev/mem to decide WHY mainline gets zero RX / TX-timeout: is the RX BAM pipe connected & is the framer … |
| `rdmem.py` | Read a single 32-bit MMIO register through /dev/mem (NGD block by default). |
| `rdreg.sh` | Read the SLIMbus NGD registers (CFG, STATUS, RX_MSGQ_CFG) on-device with devmem. |
| `rdreg2.sh` | Same NGD register read as rdreg.sh, but using busybox devmem and terse output. |
| `rdtlmm.py` | Read TLMM (pinmux) registers through /dev/mem to see the actual pad configuration. |
| `dump_lpass_regions.py` | Method-matched /dev/mem region dumper for the framer + LPASS clock-controller, usable IDENTICALLY on UT (downstream) and pmOS (mainline). Auto-force-r… |
| `diff_lpass_regions.py` | Word-by-word diff of two same-region MMIO dumps produced by dump_lpass_regions.py (the oracle/UT side vs the pmOS/dead side). This is the two-sided di… |
| `framer_mmio_dump.c` | Loadable module that snapshots the SLIMbus/LPASS framer and clock MMIO blocks so they survive an ADSP subsystem restart. |
| `frm.py` | frm.py — SLIMbus framer + NGD register reader (the §2 "hard fact" table). |
| `frm_causality.py` | Causality test on the framer state bits that differ working(UT)->dead(pmOS): +0x804 bit23 (UT=1,pmOS=0)  and  +0x430 bit4 (UT=1,pmOS=0). |
| `poll2.py` | Trigger slim-ngd rebind, then sample pipe3 RX + NGD over 8s with 150ms heartbeat, to see (a) how long the RX pipe stays connected vs the 1s capability… |
| `poll_pipes.py` | Keep pages mapped, sample fast, log every register transition during a re-triggered power_up. |
| `p2_read.py` | P2 reader — works on pmOS (mainline) and UT (downstream 4.9). Reads: enabled clocks (ec>0), focusing on lpass/slim/audio; codec+slimbus enum state. |
| `smem_toc_read.py` | SAFE: reads ONLY the proven-safe SMEM base 0x86300000 (single bounded mmap). Parses the legacy SMEM header + TOC to locate item id=469 (IMAGE_VERSION_… |

### Firmware and coredump analysis (offline)

| script | what it does |
|---|---|
| `coredump_resolve.py` | Resolve ADSP VIRTUAL addresses (0xf0xxxxxx) into the remoteproc COREDUMP, which is indexed by PHYSICAL address. Bridge = the static adsp.mbn phdr tabl… |
| `make_disasm_elf.py` | Wrap a raw code blob into a minimal ELF32-hexagon with one .text section at a given VA, so llvm-objdump -d gives real addresses + packet grouping. Usa… |
| `qsr_resolve.py` | Attack the QSR wall: resolve terse (0x92) ADSP F3 messages against adsp.mbn. |
| `parse_f3.py` | Decode a captured Qualcomm DIAG F3 log stream into readable messages. |
| `f3_dump.py` | Full ADSP F3 dump: all readable EXT (0x79) msgs grouped by ss_id + source file, plus QSR (0x92) msgs with line/hash/args and best-effort pointer-arg r… |
| `tzlog.py` | tzlog.py — TrustZone (TZBSP) diag-log reader for the FP3 (MSM8953). |

### Tracing, DIAG and messaging

| script | what it does |
|---|---|
| `diag.sh` | Roncsolásmentes diagnosztika TWRP-ből (retry-t NEM fogyaszt). - boot_a tényleg lk2nd-e?  - utolsó-boot kernel-log (pstore/ramoops) |
| `diag-adsp.sh` | Collect ADSP state on-device: remoteproc status, uptime, kernel version and related logs. |
| `diagtap.py` | Minimal DIAG-over-rpmsg tap for mainline pmOS (msm8953). The ADSP/modem DIAG SMD channels are exposed as /dev/rpmsgN char devices. |
| `diagcap.py` | Capture ADSP F3 debug messages across an SSR (fresh SLIMbus framer bring-up). Re-arms DIAG F3 masks continuously so the fresh ADSP starts streaming AS… |
| `sensdiag.py` | pmOS/mainline ADSP F3 capture focused on the SENSORS subsystem (ss_id 53). Finds the ADSP remoteproc BY NAME (the index moves between boots) and re-binds the DIAG rpmsg channels itself, because an SSR destroys and recreates them unbound. |
| `ut-sensdiag.py` | The Ubuntu Touch (downstream `/dev/diag`) twin of `sensdiag.py`: writes the same RAW 0x7E-framed binary so one parser runs byte-for-byte on both sides — the precondition for a real oracle differential. Uses `time.monotonic()`; the wall clock jumps mid-boot. |
| `ut-bootdiag.service` | Boot-armed capture unit for UT, for events that happen before userspace is up (the ADSP leaves reset at ~t=21.9 s). `Type=simple` so it cannot stall the boot; the script waits for `/dev/diag` itself. Install into `/etc/systemd/system`, `enable`, reboot. |
| `parsef3.py` | Host-side F3 frame parser shared by both captures: de-stuffs the HDLC framing and yields `(timestamp, ss_id, line, file, format, args)` for extended (0x79) and terse/QSR (0x92) messages alike. |
| `ut-trace.sh` | DOWNSTREAM (Ubuntu Touch / Halium 10, downstream 4.9.218 kernel) SLIMbus trace. Run from HOST while phone is booted into UT with adb (Halium adb runs … |
| `ut-ssr-trace.sh` | UT ADSP SSR-recovery differenciál-trace (plan: lovely-dazzling-rain). A BIZONYÍTOTTAN működő UT-n (slot_a, halium-10.0 4.9.218) az ADSP-t SSR-rel |
| `ut-capture-framer.sh` | Enhanced WORKING-framer capture on Ubuntu Touch (downstream 4.9 kernel) for the on-device A/B vs mainline pmOS. The KEY additions over ut-trace.sh: |
| `los-trace.sh` | DOWNSTREAM (LineageOS A15 eng/userdebug, downstream 4.9 kernel) SLIMbus trace capture. Run from HOST while the phone is booted into LineageOS with adb… |
| `pdr_trace.sh` | Trace PDR (protection-domain restart) activity: service registry notifications and the audio_pd/servreg path. |
| `capture-dbg.sh` | Config lives in fp3-env.sh; every value there has a documented default. |
| `downstream-capture.sh` | FUTTASD a MŰKÖDŐ downstream rendszeren (Ubuntu Touch VAGY stock Android), rootként (UT: `sudo`; Android: `adb shell su`). A kimenetet küldd vissza. |
| `pmos-diag-capture.sh` | pmos-diag-capture.sh — run on pmOS as root (echo PW \| sudo -S bash THISFILE). Bind the ADSP DIAG (data) + DIAG_CNTL (gated to c200000), push the F3 m… |
| `pmos-baseline.sh` | pmOS-side (mainline, "broken" SLIMbus) baseline capture for downstream diff |
| `pmos-netcon-trigger.sh` | pmos-netcon-trigger.sh HOST_MAC  — run on pmOS as root. Bring up netconsole over the RNDIS link (device $FP3_DEV_IP -> host |
| `pmos-rpmsg-diag.py` | pmos-rpmsg-diag.py — read the ADSP's DIAG stream on pmOS via rpmsg_char, and (optionally) push the F3 message mask on the DIAG_CNTL channel so the ADS… |
| `adsp-smem-log.py` | adsp-smem-log.py — read Qualcomm SMEM_LOG ring from the AP on mainline pmOS. |
| `qrtr_lookup.py` | Minimal qrtr-lookup replacement: enumerate QRTR services via kernel name service. |
| `ut-diag-adsp.py` | ut-diag-adsp.py  — on-device (UT) ADSP/LPASS diag F3 capture via /dev/diag Pure python, no compilation. Constants verified against downstream source: |
| `ut_diag_f3.py` | UT (downstream 4.9 diagchar) ADSP F3 capture via /dev/diag. Unlike mainline rpmsg, UT uses the classic Qualcomm diagchar node: |

### Power, battery and thermal

| script | what it does |
|---|---|
| `discharge.sh` | GYORS AKKU-MERÍTÉS a duty-cycle charger-teszthez. pmOS-ben NINCS töltés → ott full terheléssel fogyasztjuk az akkut, amíg a TWRP-ben |
| `charge-test.sh` | DUTY-CYCLE töltés-teszt harness (user-protokoll: rövid pmOS burst → TWRP hő-ellenőrzés). Cél: kísérleti charger-kód TERMIKUSAN biztonságos tesztelése … |
| `fg-verify.sh` | fg-verify.sh — fuel-gauge (pmi632-battery) ellenőrzés pmOS-ben SSH-n. Kiolvassa a battery-psy capacity/voltage/status mezőit és a charger-psy-t, |
| `gen_ocv.py` | row-legend (centi-percent) and 25C column (3rd value, units of 100uV) from Kayo v1-lut |
| `thermprobe.sh` | Per-zóna thermal-mintázás sha256sum-load alatt: melyik szenzor megbízható? |

## `archive/`

208 files. Single-use reverse-engineering artifacts from the SLIMbus audio
investigation, kept as a record of what was tried rather than as a toolkit:

* `build_snap*.py` — build a patched ADSP firmware image carrying one
  instrumentation hook ("snapshot" N).
* `deploy_snap*.sh` — sign, flash and boot that image on one slot.
* `smem_snap*_read.py` — read back what the hook wrote into SMEM.
* `snap*.s` — the Hexagon assembly of the hook itself.
* `*_onboard.sh` — on-device driver for one snapshot run.
* `archive/m2/` — the firmware resigning and instrumentation tree; needs
  [qtestsign](https://github.com/msm8916-mainline/qtestsign) and a vendor ADSP
  image, neither of which is redistributable, so it will not run as-is.

They are grouped in threes (build → deploy → read) named after the experiment,
so `build_snapCKB8_patch.py` / `deploy_snapCKB8_*.sh` / `smem_snapCKB8_read.py`
belong together. The journal entries referenced in `../references/` explain
what each one was testing.
