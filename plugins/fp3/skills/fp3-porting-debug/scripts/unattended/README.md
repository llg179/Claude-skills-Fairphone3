# Unattended access — the files to deploy

> ⚠️ **AI-generated.** This page — and the code, device tree and tooling it
> describes — was written by Claude (Opus 5) working under the direction of
> Lajosházi, László Gergely, who reviewed every change and made or reviewed
> every measurement it rests on. Kernel commits carry `Co-authored-by: Claude`;
> anything prepared for the LKML carries `Assisted-by:` instead and never a
> `Signed-off-by` from the assistant, since only a human can certify the DCO.

Drop-in configuration that makes both OSes reachable with **no on-device login
and no USB replug**. The step-by-step procedure, and the reasoning behind each
piece, is in the repository README under "Unattended access"; this directory
holds only the files themselves so nothing has to be copied out of prose.

| where | file | goes to |
|---|---|---|
| host | `host/10-fp3.link` | `/etc/systemd/network/` |
| host | `host/11-fp3ut.link` | `/etc/systemd/network/` |
| host | `host/50-fp3-link` | `/etc/NetworkManager/dispatcher.d/` (mode 755, root:root) |
| host | `host/ssh-config.example` | append to `~/.ssh/config`, adjust the WiFi address |
| pmOS | `pmos/fp3-usbnet-watchdog` | `/usr/local/bin/` (mode 755) |
| pmOS | `pmos/fp3-usbnet-watchdog.service` | `/etc/systemd/system/` |
| pmOS | `pmos/fp3-usbnet-watchdog.timer` | `/etc/systemd/system/`, then `systemctl enable --now` |
| pmOS | `pmos/fp3-devmode-cleanup` | `/usr/local/bin/` (mode 755) |
| pmOS | `pmos/10-cleanup-stale-profiles.conf` | `/etc/systemd/system/usb-moded-developer-mode.service.d/` |
| UT | `ut/ut-force-usbnet.service` | `/etc/systemd/system/`, then `systemctl enable --now` |

Two things are *not* files and have to be done by hand, once each: installing
the SSH key (`fp3-link.sh install-key` for pmOS, and for Ubuntu Touch by staging
`authorized_keys` into its writable overlay from the other slot), and
`loginctl enable-linger` on pmOS.
