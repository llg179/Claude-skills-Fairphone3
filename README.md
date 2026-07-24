# Claude-skills-Fairphone3

Claude Code skills for bringing up and debugging **mainline Linux on the
Fairphone 3** (MSM8953 / SDM632) — postmarketOS, Sailfish OS (hybris), and the
downstream Ubuntu Touch build used as a working-hardware oracle.

These grew out of a long-running effort to get the WCD9335 SLIMbus audio path
working on mainline. They encode method rather than answers: how to get ground
truth out of the hardware, how to run one-change experiments safely on a device
you cannot afford to brick, and how to tell a healthy-looking Linux subsystem
from a pin that is actually dead.

## What's in it

| Skill | What it's for |
|---|---|
| `fp3-porting-debug` | Umbrella method: hardware facts, the three OS tracks, ground-truth acquisition, debugging techniques, reference notes from the audio work. |
| `fp3-kernel-test` | The edit → build → deploy → capture loop for a single kernel/DT/firmware change, with brick-safety gates and recovery recipes. |

## Installing the skills

```
/plugin marketplace add llg179/Claude-skills-Fairphone3
/plugin install fp3@Claude-skills-Fairphone3
```

Then invoke with `/fp3-porting-debug` or `/fp3-kernel-test`.

If you would rather not use plugins, copy or symlink the two directories under
`plugins/fp3/skills/` into your own `~/.claude/skills/`.

## Configuration

Nothing is hardcoded to one machine. All settings live in
`plugins/fp3/skills/fp3-porting-debug/scripts/fp3-env.sh`, written as
`${VAR:-default}` with a comment naming the default:

```sh
export FP3_DEV_IP="${FP3_DEV_IP:-172.16.42.1}"   # default: pmOS USB-net device address
export FP3_ROOT="${FP3_ROOT:-$HOME/fp3}"         # default: project data root
```

Two values deliberately have **no** default, because they are yours:

* `FP3_PW` — the password of the pmOS user, whatever you set during
  `pmbootstrap init`. The scripts use it for `sshpass` and for `sudo -S` on the
  device.
* `FP3_SERIAL` — your device's USB serial number. The flashing scripts pass it
  to `fastboot -s` so they act on the right phone if anything else is plugged
  in, and it is how a script tells "the phone came back" from "some other
  device appeared".

  Read it off the device, whichever mode it is in:

  ```
  fastboot devices          # in the bootloader
  A209H47E0202    fastboot

  adb devices               # in Android, TWRP or a booted pmOS with adb
  A209H47E0202    device

  lsusb -v -d 18d1: 2>/dev/null | grep iSerial   # from the USB descriptor
  ```

  It is the first column, before the mode word. The same string is printed by
  `fastboot getvar serialno`. It is a property of the phone, so it does not
  change when you reflash or switch slots.

Put your own values in `fp3-env.local.sh` next to it — that file is
git-ignored. Start from `fp3-env.local.sh.example`.

The Python helpers read the same names from the environment, with the default
spelled out in the code:

```python
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root
```

## Installing the two OSes

This is the setup the skills assume: **Ubuntu Touch on slot `_a`** as the
working-hardware oracle, **postmarketOS on slot `_b`** as the mainline target,
and swapping between them with nothing but `fastboot set_active`.

### Before you start

* Bootloader **unlocked** (Fairphone publishes the code; this wipes the phone).
* `fastboot`, `adb`, and `pmbootstrap` on the host.
* A TWRP image for FP3. You need it because **`fastboot boot <img>` is broken on
  this aboot** — TWRP has to be flashed to a partition and booted from there.
  `twrp.sh flash-b` puts it on `boot_b` so `boot_a`/lk2nd stays untouched.

### How the FP3 is laid out

A/B device, but with **one shared `userdata`** — which is what makes a naive
dual-boot install fight itself.

| what | where |
|---|---|
| `boot_a` / `boot_b` | mmcblk0p27 / p28 |
| `system_a` / `system_b` | mmcblk0p30 / p31 |
| `vendor_a` / `vendor_b` | mmcblk0p32 / p33 |
| `dtbo_a` / `dtbo_b` | mmcblk0p23 / p24 |
| `userdata` (shared, ~52 GB) | mmcblk0p62 |

Node paths differ per booted OS: pmOS exposes `/dev/block/bootdevice/by-name/`,
Ubuntu Touch uses `/dev/disk/by-partlabel/`. For cross-slot recovery use the raw
`/dev/mmcblk0pNN` node — `losetup -fP` silently fails on `/dev/block/...`.

### Ubuntu Touch (slot `_a`)

Install with the UBports installer, then enable developer mode and set a
passcode — both live in `userdata`, so they must be restored whenever userdata
is rewritten. Take a backup once it works:

```
scripts/ut-backup.sh          # gz images of system_a, vendor_a, userdata via TWRP
scripts/ut-discover.sh        # what is actually on the device right now
```

`scripts/swap-to-ut.sh` restores that backup unattended: TWRP on `boot_b`, then
stream-decompress the gz images straight onto the block devices (they are far
too large to stage in the TWRP ramdisk).

### postmarketOS (slot `_b`)

```
pmbootstrap init      # device: fairphone-fp3, kernel: mainline,
                      # bootloader lk2nd-msm8953, A/B via qbootctl
printf '$FP3_PW\n$FP3_PW\n' | pmbootstrap install     # it wants the password on stdin
```

Then flash, **in this order** — the order matters and a missing step is the
classic boot-loop cause:

1. **`dtbo`** — `fastboot flash dtbo_a` with [z3ntu/dtbo-fp3](https://github.com/z3ntu/dtbo-fp3).
   Skipping this is what leaves you stuck on the "Fairphone powered by android"
   screen. This, not AVB, was the real native-boot blocker.
2. **`lk2nd`** — `pmbootstrap flasher flash_lk2nd`, i.e. lk2nd onto `boot_a`.
   With lk2nd you do **not** flash a separate kernel/boot partition.
3. **`vbmeta`** — an empty vbmeta to disable verification.
4. **`rootfs`** — `pmbootstrap flasher flash_rootfs --partition userdata`
   (four ~519 MB sparse chunks).
5. `fastboot set_active a` and reboot.

`scripts/flash-pmos.sh full` drives steps 2-4. It does **not** flash the dtbo —
do that yourself, or use `scripts/swap-to-pmos.sh`, which handles the dtbo and
vbmeta too.

At the lk2nd unlocked-bootloader warning screen: press **power twice, then hold
volume-down** to reach the menu.

### Both at once: the dual-slot setup

`scripts/setup-dualslot.sh` is the one-time install that makes swapping free.
It puts the pmOS rootfs on **`system_b`** instead of `userdata`, so Ubuntu Touch
keeps `userdata` to itself and nothing has to be reflashed to switch.

It works because the pmOS initramfs scans `userdata` and then `system*` for a
partition holding exactly two subpartitions (boot + root) and loop-mounts it.
UT's plain-ext4 `system_a` and `userdata` have none and are skipped, so
`system_b` is picked up with no cmdline change. The 2.1 GB rootfs fits the 3 GB
partition.

After that, switching OS is:

```
scripts/slot.sh set a     # Ubuntu Touch
scripts/slot.sh set b     # postmarketOS
```

plus a reboot. `scripts/to-twrp.sh` and `scripts/to-pmos.sh` do the round trip
via TWRP when you need a recovery shell in between.

### Things that will bite you

* **A/B retry-count.** Every failed boot decrements it; `set_active` does not
  reset it. Only a successful boot plus `qbootctl` does. `slot.sh get` shows it.
* **`fastboot boot` does not work** on this aboot. Flash TWRP to `boot_b` and
  boot the slot instead (`twrp.sh flash-b`, `twrp-dd.sh` to write images from
  there).
* **Cycling fastboot** fails on the larger `boot_a`; you need a stable fastboot
  connection, not one that re-enumerates.
* **Never restart USB from the host** while a flash or capture is running.
* Once pmOS is up: `ssh $FP3_USER@$FP3_DEV_IP` over the USB NCM link
  (`scripts/fp3-ssh.sh` wraps it, `scripts/fp3-link.sh` brings up the host address).

## What is deliberately not here

* **No vendor firmware.** The ADSP image (`adsp.mbn`) and everything extracted
  from it are proprietary Qualcomm/Fairphone binaries and are not
  redistributable. Scripts that need them expect you to pull them off your own
  device. `.gitignore` blocks `*.mbn`, `*.elf`, `*.bin` so they cannot be
  committed by accident.
* **No third-party tools vendored.** The firmware-resigning work used
  [qtestsign](https://github.com/msm8916-mainline/qtestsign); fetch it yourself.
* **No device dumps.** Large raw captures (dmesg, SMEM, device trees) were
  stripped; the written analyses that reference them are kept.

## Status and scope

Written against one specific device (`fairphone-fp3`, pmOS 7.0.9,
msm8953-mainline). Many of the scripts under `scripts/` are single-use
reverse-engineering artifacts kept as a record of what was tried — treat them
as an archive, not a supported toolkit. The value that travels is in `SKILL.md`
and `references/`.

Some notes are in Hungarian; `references/slimbus-audio-context.md` is English.

Related: the kernel fixes this work produced live on the `fp3-709` branch of
<https://github.com/llg179/linux>.

## Safety

The kernel-test skill exists because this hardware is easy to brick. It assumes
a dual-slot setup with a known-good slot kept intact, and it gates anything that
writes to flash. Read `fp3-kernel-test/references/safety.md` before running
anything that touches a partition.

## License

Two licenses, per file, marked with an SPDX identifier:

| What | License | File |
|---|---|---|
| Python helpers (`*.py`) | MIT | [LICENSE.MIT](LICENSE.MIT) |
| Everything else — shell scripts, skills, reference notes | GPL-2.0-or-later | [LICENSE](LICENSE) |

The Python tooling is standalone analysis code, so it is permissive. The shell
scripts drive kernel builds and carry register maps and disassembly notes
derived from kernel work, so they stay under the kernel's own license.
