# FP3 downstream (UT/Halium 4.9.218) audio-framer boot sequence — full ordering

Live capture 2026-07-23 (folyt.194), on OUR device, slot_a UT. This is the
**working** path: WCD9335 gets `laddr 0xc8/0xc7` at t≈21.94s. Source split
(kernel-boot vs userspace-init) is the whole point — the ADSP that frames the
SLIMbus is loaded **late, by userspace init**, not early by the kernel.

Data: `dmesg` + `/sys/kernel/debug/ipc_logging/c140000.slim/log`. Full dmesg
saved as evidence (scratchpad ut-fullboot-dmesg.txt at capture time).

## ★ Two load-order facts that matter most

1. **The DLKM audio modules FAILED to load and it did NOT matter.** At t=18.15
   init runs `modprobe -a audio_apr audio_adsp_loader audio_q6_notifier
   audio_q6 … audio_wcd9335 audio_machine_sdm450` — every one **fails**
   (`q6_notifier_dlkm: disagrees about version of symbol module_layout`,
   service `exited with status 1`). The framer still comes up. ⇒ **the framer
   chain runs on the BUILT-IN kernel drivers** (compiled into the 4.9 image),
   NOT on the loadable audio_* DLKMs. Do not chase the DLKM list as the trigger.
2. **The ADSP is loaded by USERSPACE INIT, late (t≈21.48s)** — not by the kernel
   at boot. Trigger chain: init `firmware_mounts_complete` action
   (`/init.rc:330`) → `early-boot` action (`/vendor/etc/init/hw/init.qcom.rc:74`)
   → `subsys-pil-tz c200000.qcom,lpass: adsp: loading`. There is a **~15s gap**
   between the AP-side NGD HW coming up (t=6.12) and the ADSP arriving (t=21.5).
   Mainline instead auto-boots the ADSP EARLY from the kernel (qcom_q6v5_pas,
   ~t=19.8) — different order, no userspace gate.

## Full timeline (t = seconds; SRC = kernel-boot | userspace-init | pil-result)

| t | event | SRC |
|------|-------|-----|
| 0.000 | reserved-mem: `adsp_region@0`, `adsp_fw_region@0`, `adsp_shmem_device_region@0xc0100000` | kernel (DT) |
| 2.000 | `soc:qcom,msm-adsprpc-mem` assigned adsp_region | kernel-boot |
| 2.014 | `c200000.qcom,lpass` assigned adsp_fw_region | kernel-boot |
| 2.785 | ALSA core Initialized | kernel-boot (built-in) |
| 3.645 | `sps:BAM 0x7904000` registered (20 pipes) | kernel-boot |
| 4.45  | subsys-pil-tz infra: kgsl-hyp(a506_zap), venus register (`minidump-id not found for adsp`) | kernel-boot (PIL infra) |
| 5.93  | `msm-dai-q6-tdm` pri/sec/tert rx+tx probe (built-in Q6 DAIs) | kernel-boot |
| 6.113 | `adsprpc-smd` chrdev | kernel-boot |
| 6.118 | ipc: **start logging for slim dev c140000.slim** (NGD driver probe) | kernel-boot |
| 6.123 | ipc: **NGD SB controller is up!** (AP-side NGD HW ready) | kernel-boot |
| 18.15 | init: `modprobe -a audio_apr audio_adsp_loader … audio_wcd9335 audio_machine_sdm450` (DLKM) → **ALL FAIL vermagic, status 1** | userspace-init (irrelevant) |
| 21.42 | `wcnss: wcnss_wlan triggered by userspace` → wcnss subsys load | userspace-init |
| 21.48 | init action `firmware_mounts_complete` (/init.rc:330) | userspace-init |
| 21.48 | init action `early-boot` (/vendor/etc/init/hw/init.qcom.rc:74) | userspace-init |
| 21.481| **subsys-pil-tz c200000.qcom,lpass: adsp: loading** 0x8d600000→0x8e700000 | userspace-triggered PIL |
| 21.484| init: exec `/vendor/bin/init.qcom.early_boot.sh` | userspace-init |
| 21.715| adsp: **Brought out of reset** | pil-result |
| 21.750| adsp: **Power/Clock ready interrupt received** + error-monitoring up | pil-result |
| 21.815| **apr_tal: Q6 Is Up** (APR link to ADSP audio) | pil-result |
| 21.862| `sysmon-qmi: Connection established … adsp's SSCTL service` | pil-result |
| 21.867| ipc: **Slimbus QMI NGD CB received event:2** (SLIMbus QMI svc 0x301 SERVER_ARRIVE) | ← the trigger |
| 21.894| `sps:BAM 0xc104000` enabled **23 pipes** + registered (slimbam RX/TX) | pil-result |
| 21.897| ipc: **SLIM SAT: Rcvd master capability** ← FRAMER FRAMES (~30ms after 0x301 arrive) | ADSP |
| 21.898| ipc: capability exchange successful / Slim runtime resume ret 0 | ADSP |
| 21.898| `wcd-slim tasha-slim-pgd` probe (parses vregs, DT node `/soc/slim@c140000/tasha_codec`) | kernel-boot |
| 21.944| **slimbus:1 laddr:0xc8** EAPC 0x1:0xa0 / **laddr:0xc7** EAPC 0x0:0xa0 | ADSP framer |
| 21.945| slim device up (dev_up=1); wcd9335 v2.0; chip id maj 0x107 min 0x1 | kernel-boot |
| 21.973| ipc: **reg-SSR with:adsp, PDR not available** (downstream ties to SSR, NOT PDR) | kernel-boot |
| 22.417| init.qcom.early_boot.sh exits (0.929s) | userspace-init |
| 23.568| init: `adsprpcd` | userspace-init |
| 24.4  | sound-card wcd_mbhc_start, Headset/Button Jack inputs, ASoC routes | kernel-boot |

## The framer activation, isolated (ipc_logging c140000.slim)

```
[ 6.123] NGD SB controller is up!            AP NGD ready, then idle-waits 15s
[21.867] Slimbus QMI NGD CB received event:2 ADSP registers SLIMbus QMI svc 0x301
[21.897] SLIM SAT: Rcvd master capability    ← ADSP frames the bus (~30ms later)
[21.898] SLIM SAT: capability exchange successful / Slim runtime resume: ret 0
[21.973] reg-SSR with:adsp, PDR not available
```

The AP-side action is ONLY the QMI handshake fired on `event:2` (0x301 server
arrive): SELECT_INSTANCE + POWER_REQ (per the golden ipc trace), and ~30 ms
later the ADSP broadcasts SLIM_USR_MC_MASTER_CAPABILITY. **This trigger is
byte-identical to what mainline qcom-ngd-ctrl sends** (180-session proved the
QMI bytes identical). Difference is purely the ADSP *response*: downstream frames
in 30 ms, mainline times out. PDR/servreg/audio_pd is NOT used (explicitly
"PDR not available") — pd-mapper is a dead end.

## Boot vs userspace — classification summary

- **Kernel-boot (built-in, compiled into 4.9 image):** ALSA, BAM/sps, all
  `msm-dai-q6-tdm` DAIs, adsprpc, the **SLIMbus NGD controller** (`c140000.slim`,
  up at t=6), the **wcd-slim/tasha codec** driver, `apr_tal`, sysmon-qmi, the
  `msm8952-slimbus-wcd` sound card. These are the framer chain.
- **Userspace-init (Android init .rc):** the failed audio_* **DLKM** modprobe
  (t=18, irrelevant); wcnss trigger; **the ADSP PIL load** via
  `firmware_mounts_complete`→`early-boot`→subsys-pil-tz + `init.qcom.early_boot.sh`
  (t=21.48) — this is the one userspace step that actually gates the framer,
  because it is what brings the ADSP (and its 0x301 QMI svc) up.
- **ADSP-internal (the wall):** the 30 ms POWER_REQ→MASTER_CAPABILITY. Not
  reproducible on mainline with identical AP trigger + identical 2020 firmware.

## Implication for mainline

Order difference is real but not obviously causal: downstream brings the AP NGD
up early (t=6) and the ADSP up late (t=21.5, userspace) with a 15 s idle gap,
then frames on 0x301-arrive. Mainline brings the ADSP up early (kernel) and the
NGD driver waits on the same 0x301/lpass-SSR path. The QMI content is identical
either way. So the boot-order is a candidate variable (late-userspace-ADSP vs
early-kernel-ADSP) but the established wall is the ADSP not answering POWER_REQ,
below the AP layer (see archive/slimbus-audio-context.md; folyt.118-193). Firmware
identical across all Android (folyt.191); Bert's exact 6.11 kernel = 0/8 on our
device (folyt.193) ⇒ device-specific + ADSP-internal, not AP-software.
