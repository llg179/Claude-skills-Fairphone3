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

## Install

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
`FP3_PW` (the pmOS user password you chose at install) and `FP3_SERIAL`.

Put your own values in `fp3-env.local.sh` next to it — that file is
git-ignored. Start from `fp3-env.local.sh.example`.

The Python helpers read the same names from the environment, with the default
spelled out in the code:

```python
FP3_ROOT = os.environ.get("FP3_ROOT", "/mnt/1TB/Fp3-Sailfish")  # project data root
```

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

GPL-2.0-or-later. See [LICENSE](LICENSE).

The scripts here generate and analyse patches against the Linux kernel and
carry register maps and disassembly notes derived from that work, so the whole
repository uses the kernel's own license rather than a separate one for the
prose. Individual files carry:

    SPDX-License-Identifier: GPL-2.0-or-later
