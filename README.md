# Claude-skills-Fairphone3

Claude Code skills for bringing up and debugging **mainline Linux on the
Fairphone 3** (MSM8953 / SDM632) — postmarketOS, Sailfish OS (hybris), and the
downstream Ubuntu Touch build used as a working-hardware oracle.

These grew out of a long-running effort to get the WCD9335 SLIMbus audio path
working on mainline. They encode method rather than answers: how to get ground
truth out of the hardware, how to run one-change experiments safely on a device
you cannot afford to brick, and how to tell a healthy-looking Linux subsystem
from a pin that is actually dead.

## What's in it — three skills, and the boundary between them

They split by **the moment in the work**, not by topic. One question picks one:

| you are about to… | load | it answers |
|---|---|---|
| …work out *what is even wrong* | [`fp3-porting-debug`](plugins/fp3/skills/fp3-porting-debug/) | where to look, which of the three OSes answers which question, how to get ground truth out of silicon that has no debug port |
| …try *one specific change* | [`fp3-kernel-test`](plugins/fp3/skills/fp3-kernel-test/) | how to run the edit → build → deploy → measure cycle once, safely, and read the result honestly |
| …*publish* work that already works | [`msm8953-mainline-pr`](plugins/fp3/skills/msm8953-mainline-pr/) | how to turn discovery-ordered fork branches into a series a maintainer will take, and where an AI-assisted series may legally go |

**Orient → execute → publish.** They are meant to be loaded one at a time; a
routine build-and-measure cycle should not have to carry the whole umbrella.

Each owns something exclusively, and the others point at it rather than
restating it:

| owned by | what |
|---|---|
| `fp3-porting-debug` | the device substrate (partitions, boot chain, unattended access), the three OS tracks and the oracle idea, the `scripts/` tooling, the two running logs, and `references/archive/` — the dated record of what was already tried |
| `fp3-kernel-test` | **all brick-safety and measurement-integrity rules**, in `references/safety.md`; the instruments (MMIO, QMI/QRTR, clocks, genpd, coredump, and the device-tree schema checkers) and the recovery recipes |
| `msm8953-mainline-pr` | commit form, provenance and attribution rules, writing and validating a DT binding, the DCO/`Assisted-by:` disclosure, whether a series actually *applies* to its destination tree, how to declare an unmerged prerequisite, and where a series may be sent |

Two things deliberately live **outside** all three: what the device does *today*
and how to build/deploy it are in
[`llg179/fp3-pmaports/docs/`](https://github.com/llg179/fp3-pmaports/tree/main/docs),
and the branch model is in that repo's
[README](https://github.com/llg179/fp3-pmaports#the-branch-model). The test for
which home something belongs in — *would it be wrong next month* vs *would it
still be true on a different phone* — is written down in `fp3-porting-debug`
under "Where knowledge lives".

## Installing the skills

```
/plugin marketplace add llg179/Claude-skills-Fairphone3
/plugin install fp3@Claude-skills-Fairphone3
```

Then invoke with `/fp3-porting-debug`, `/fp3-kernel-test` or
`/msm8953-mainline-pr`.

If you would rather not use plugins, copy or symlink the three directories under
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
* **Never restart USB from the host** while a flash or capture is running — and note
  that a host-side reset cannot fix a device-side gadget jam anyway, which was measured
  rather than assumed: see [Unattended access](#unattended-access-no-on-device-login-no-usb-replug).
* Once pmOS is up: `ssh $FP3_USER@$FP3_DEV_IP` over the USB NCM link
  (`scripts/fp3-ssh.sh` wraps it, `scripts/fp3-link.sh` brings up the host address).
* **Neither OS needs a human at the phone.** Unlocking the screen and unplugging the
  cable used to be part of every cycle; both are gone. The full recipe, host and device
  side, is in [Unattended access](#unattended-access-no-on-device-login-no-usb-replug).

#### Slot `_b` runs out of space, and that turns into a boot loop

This is the single most common way the dev slot dies, and it looks like a
firmware bug, so it is worth understanding before it happens.

**Why it is tight.** `system_b` (`/dev/mmcblk0p31`) is about 3 GB, and it does
not hold a filesystem directly — a *whole DOS-partitioned disk image* is written
onto it raw, so `blkid` reports `PTTYPE="dos"` and no filesystem on `p31`
itself. Inside are two partitions: `p1` = `pmOS_boot` (ext2) and `p2` =
`pmOS_root` (ext4). The rootfs is ~2.1 GB in a ~2.4 GB partition, so it sits
around 90 % full from day one. There is no room to grow into.

**What fills it.** A deploy campaign — repeatedly building, sideloading and
cold-booting kernels — plus the systemd journal from every crash and ADSP
subsystem restart. The two real hogs are `/var/cache/apk/` (balloons to ~64 MB
once the device has network for `apk`) and `/var/log/journal/`.

**How it fails.** Two different faults that produce the same symptom:

1. **Disk full** — deploys start failing in confusing ways (a half-written
   package, a partial module install) and the next boot loops.
2. **Dirty filesystem** — any unclean cycle (a crash, a forced power-cycle, an
   ADSP wedge) leaves a recovering journal and orphaned inodes. This, not
   disk-full, was the actual cause in the real reboot-loop runs.

Two traps in the diagnosis:

* **`fsck` alone does not break the loop.** After repairing, a *cold power-cycle*
  is the reliable boot; a warm `fastboot reboot` keeps looping.
* **A slot dropping to fastboot is almost never the `adsp.mbn` you just
  flashed.** Co-processor firmware loads post-kernel via remoteproc, so a bad
  ADSP image cannot stop the kernel from booting. Fsck the rootfs instead of
  reflashing firmware.

**Repair it from the healthy slot — no reflash, about two minutes.** Boot the
oracle (Ubuntu Touch on `_a`, which boots reliably) and reach into the dead
slot's rootfs offline:

```sh
# by-name symlinks are absent here, so find the partition with blkid
blkid | grep -i dos                      # pmOS lives on mmcblk0p31 (system_b)

LD=$(losetup -fP --show /dev/mmcblk0p31) # note: loop0 is the oracle's own
                                         # rootfs, so this lands on loop1
/sbin/e2fsck -fy ${LD}p1                 # pmOS_boot  (ext2)
/sbin/e2fsck -fy ${LD}p2                 # pmOS_root  (ext4)

mkdir -p /mnt/pmroot && mount ${LD}p2 /mnt/pmroot
rm -f /mnt/pmroot/var/cache/apk/*
find /mnt/pmroot/var/log/journal -name '*.journal*' -delete

sync && umount /mnt/pmroot && losetup -d $LD
```

Details that cost real time when you get them wrong:

* **Fsck *both* inner partitions.** In an actual loop run the ext2 boot
  partition was dirty too (`FILE SYSTEM WAS MODIFIED`), not just the ext4 root.
* That cleanup freed about 90 MB in one run — enough to boot and keep working.
* **A successful `losetup -d` is itself the "safe to switch slots" check.** It
  fails with `busy` if anything still holds the loop device, so it doubles as
  proof the unmount was clean.
* On the oracle, `e2fsck` may not be on `sudo`'s `PATH` (`which` finds nothing)
  — call it by absolute path, `/sbin/e2fsck`.
* Do all of it rooted through the oracle's own `sudo`
  (`adb shell 'echo <pw> | sudo -S sh -c "…"'`), never `sudo adb`.
* Leave `/home/*` alone — staging left there is not yours to delete.

**Prevent it instead.** Before a measurement or deploy campaign: check `df`,
cap the journal (`journalctl --vacuum-size=`, or `SystemMaxUse=` in
`journald.conf`), and clear the apk cache. Gate the campaign on free space
*and* on a clean rootfs — and never force an unclean reboot on a healthy
system, because that is what dirties the loop-rootfs for the next boot.

## Unattended access: no on-device login, no USB replug

For a long time both OSes needed a human at the phone: unlock the screen, and
pull the cable out and back in. That is fatal for an overnight run and it
poisons measurements, because half of a "the driver is dead" result turns out to
be "the link was dead". This section is the complete recipe that removes both,
for postmarketOS and for Ubuntu Touch.

Every file referenced below lives in
[`scripts/unattended/`](plugins/fp3/skills/fp3-porting-debug/scripts/unattended/) —
deploy them from there rather than copying out of this page.

Verified end to end on 2026-07-28 by rebooting each OS with **nothing touched on
the phone**:

| OS | back over USB | back over WiFi | evidence it was the fix |
|---|---|---|---|
| postmarketOS | 39 s | — | the gadget MAC changed across the reboot (`f2:f1:1c:12:52:3e` → `96:a3:fd:e8:4e:a7`) and the interface name, host IP and neighbour entry all followed automatically |
| Ubuntu Touch | 79 s | 76 s | `ut-force-usbnet` logged `rndis up after 2 tries`, i.e. the gadget really was in `charging_only` at boot and the D-Bus requests are what brought it up |

### First, the thing that does not work

Before the recipe, the dead end, because it looks obvious and costs an hour.

**You cannot emulate a replug from the host.** Measured, not assumed:

```sh
echo 0 | sudo tee /sys/bus/usb/devices/1-5/authorized   # deauthorize
echo 1 | sudo tee /sys/bus/usb/devices/1-5/authorized
echo 1-5 | sudo tee /sys/bus/usb/drivers/usb/unbind     # driver unbind/bind
echo 1-5 | sudo tee /sys/bus/usb/drivers/usb/bind
```

Both ran cleanly and changed nothing: the device number stayed at `037` and the
gadget stayed in `0000:0afe` (charging only). Neither drops VBUS, so the *phone*
never sees a disconnect and never re-evaluates its USB mode. Cutting VBUS is not
available either unless an external hub with per-port power switching sits in the
path:

```sh
sudo lsusb -v -d 1d6b:0002 2>/dev/null | grep -i "power switching"
#   No power switching (usb 1.0)
```

So every fix below is either host-side *addressing* (which is where the "No route
to host" class of failure lives) or device-side *state* (which is where the mode
lives). There is nothing in between.

If the work disk is itself USB-attached, check the topology before touching any
port — on this machine the disk and the phone were on different buses, so a
targeted cycle of the phone's port could not affect the disk:

```sh
findmnt -no SOURCE /mnt/1TB          # /dev/sdb2
readlink -f /sys/block/sdb           # .../usb2/2-1/...   -> bus 2
readlink -f /sys/bus/usb/devices/1-5 # the phone          -> bus 1
```

[`usb-repower-safely.sh`](plugins/fp3/skills/fp3-porting-debug/scripts/usb-repower-safely.sh)
automates the safe sequence for the case where they do share a bus: quiesce
(`fuser -Mvm`), `sync`, `umount`, a clean SCSI `delete`, the power cycle, then
remount **by UUID** — the letter can change from `sdb` to `sdc` across a repower.

### Part 1 — postmarketOS

Four host-side files and three device-side changes.

#### 1.1 Pin the interface name, and give it a fixed address (host)

The gadget picks a fresh random MAC on every boot, so anything that keys off the
MAC — the interface name, a NetworkManager profile bound to a MAC — churns. Pin
by *driver* instead, with
[`host/10-fp3.link`](plugins/fp3/skills/fp3-porting-debug/scripts/unattended/host/10-fp3.link):

```sh
sudo install -m644 …/unattended/host/10-fp3.link /etc/systemd/network/
sudo nmcli connection add con-name fp3 type ethernet ifname fp3 \
    ipv4.method manual ipv4.addresses 172.16.42.2/16 \
    ipv4.never-default yes ipv6.method ignore connection.autoconnect yes
```

Bind the profile to the *interface name*, never to a MAC, for the same reason.

#### 1.2 Flush the neighbour entry on every link change (host)

This is the single highest-value item: it is what made the cable seem dead.
After the phone re-enumerates with a new MAC, the host still holds an ARP entry
for `172.16.42.1` pointing at the previous one, and every connection fails with
`No route to host` until it ages out.
[`host/50-fp3-link`](plugins/fp3/skills/fp3-porting-debug/scripts/unattended/host/50-fp3-link)
is a NetworkManager dispatcher script that flushes it; it covers the UT interface
too.

```sh
sudo install -m755 -o root -g root …/unattended/host/50-fp3-link \
    /etc/NetworkManager/dispatcher.d/
sudo systemctl enable --now NetworkManager-dispatcher.service
```

#### 1.3 Key login and an ssh alias (host)

```sh
FP3_PW=<your pmOS password> scripts/fp3-link.sh install-key
cat …/unattended/host/ssh-config.example >> ~/.ssh/config   # then fix the WiFi address
```

After this, [`fp3-ssh.sh`](plugins/fp3/skills/fp3-porting-debug/scripts/fp3-ssh.sh)
uses the key automatically and retries with a neighbour flush between attempts.

#### 1.4 Let user services run without a login (device)

```sh
sudo loginctl enable-linger fp3
```

Without lingering, `user@<uid>.service` only runs while someone is logged in, so
pulseaudio and anything else in the user session is absent until you unlock the
phone — and a long measurement started over SSH is killed the moment the session
ends. Check the uid: it is **not** necessarily 1000 (it was 10000 here).

#### 1.5 Heal a jammed gadget from the device side (device)

The only real lever, as established above:
[`pmos/fp3-usbnet-watchdog`](plugins/fp3/skills/fp3-porting-debug/scripts/unattended/pmos/fp3-usbnet-watchdog)
re-binds the UDC when the host has stopped enumerating it. It is conservative on
purpose: it never acts while the state is `configured` (healthy) or
`not attached` (no cable), and only after a *sustained* bad state, so a normal
transient during enumeration is ignored.

```sh
sudo install -m755 …/unattended/pmos/fp3-usbnet-watchdog /usr/local/bin/
sudo install -m644 …/unattended/pmos/fp3-usbnet-watchdog.service /etc/systemd/system/
sudo install -m644 …/unattended/pmos/fp3-usbnet-watchdog.timer   /etc/systemd/system/
sudo systemctl enable --now fp3-usbnet-watchdog.timer
```

#### 1.6 Stop the NetworkManager profile leak (device)

`usb-moded-developer-mode` runs an unconditional `nmcli connection add` on start
and only deletes the profile in its `down()`, so every unclean shutdown leaks
one. There were **96** of them here, all but one zero-length, which leaves NM
picking between identically named connections.
[`pmos/fp3-devmode-cleanup`](plugins/fp3/skills/fp3-porting-debug/scripts/unattended/pmos/fp3-devmode-cleanup)
prunes them, run from a drop-in before the service adds this boot's profile.

```sh
sudo install -m755 …/unattended/pmos/fp3-devmode-cleanup /usr/local/bin/
sudo mkdir -p /etc/systemd/system/usb-moded-developer-mode.service.d
sudo install -m644 …/unattended/pmos/10-cleanup-stale-profiles.conf \
    /etc/systemd/system/usb-moded-developer-mode.service.d/
sudo systemctl daemon-reload
```

### Part 2 — Ubuntu Touch

UT was the harder half, and the mechanism is completely different: `usb-moded`
parks the gadget in `charging_only` until the session says otherwise, so at the
lock screen the host sees **no network interface and no adb at all** — the phone
enumerates as `0000:0afe` with no functions. Since the host cannot force a
re-evaluation (see above), the fix has to come from inside.

The bootstrap problem is that getting inside needs the link. It is solved by
staging the access **offline from the other slot**, which needs no UI and no
working link.

#### 2.1 Stage SSH access from pmOS, with UT not running

Boot pmOS, then mount UT's writable overlay. UT keeps `/home` in `user-data/`
and the writable parts of `/` in `system-data/`, both on `userdata`:

```sh
sudo mkdir -p /mnt/ud
sudo mount /dev/disk/by-partlabel/userdata /mnt/ud
```

Install the host's public key for `phablet` (uid/gid **32011**):

```sh
sudo mkdir -p /mnt/ud/user-data/phablet/.ssh
sudo sh -c "echo '<your ~/.ssh/id_ed25519.pub>' > /mnt/ud/user-data/phablet/.ssh/authorized_keys"
sudo chown -R 32011:32011 /mnt/ud/user-data/phablet/.ssh
sudo chmod 700 /mnt/ud/user-data/phablet/.ssh
sudo chmod 600 /mnt/ud/user-data/phablet/.ssh/authorized_keys
```

Enable sshd at boot. UT normally only enables it from an Android property, via
`ssh-property-migration.service` — a one-shot that **masks itself after its first
run**, so relying on the property alone is fragile. Creating the wants-symlink
directly is robust:

```sh
sudo ln -sf /lib/systemd/system/ssh.service \
	/mnt/ud/system-data/etc/systemd/system/multi-user.target.wants/ssh.service
sudo sh -c 'echo -n true > /mnt/ud/android-data/property/persist.service.ssh'   # belt and braces
sudo sync && sudo umount /mnt/ud
```

Host keys need no attention: `ssh.service.d/lxc-android-config.conf` already
pulls in `ssh-generate-hostkeys.service`.

#### 2.2 Prepare the host for UT's gadget

UT binds `rndis_host` on the host side, pmOS binds `cdc_ncm`, so the two pins
never collide —
[`host/11-fp3ut.link`](plugins/fp3/skills/fp3-porting-debug/scripts/unattended/host/11-fp3ut.link):

```sh
sudo install -m644 …/unattended/host/11-fp3ut.link /etc/systemd/network/
sudo nmcli connection add con-name fp3ut type ethernet ifname fp3ut \
    ipv4.method auto ipv4.never-default yes ipv6.method ignore connection.autoconnect yes
```

**Use DHCP here, not a static address.** UT's `rndis_adb` mode sets
`network = 0`, leaving addressing to NetworkManager, which uses its shared-mode
subnet: the device comes up on **`10.42.0.1`**. The `10.15.19.82` in usb-moded's
own defaults file is *not* used in this mode — configuring the host for it gives
a link that is up and completely unreachable.

#### 2.3 Bring the gadget up at boot, from inside UT

With SSH working, install
[`ut/ut-force-usbnet.service`](plugins/fp3/skills/fp3-porting-debug/scripts/unattended/ut/ut-force-usbnet.service),
which asks usb-moded over D-Bus for `rndis_adb` until the gadget actually carries
the rndis function. Note `/` is read-only on UT, but `/etc/systemd/system` is a
read-write bind mount from `userdata`, so a unit can be installed without
remounting the rootfs. `/usr/local/bin` and `/var/lib` are read-only, which is
why the retry loop lives inline in the unit.

```sh
sudo install -m644 …/unattended/ut/ut-force-usbnet.service /etc/systemd/system/
sudo systemctl enable --now ut-force-usbnet.service
```

Two details that cost a cycle each:

* **`$$` is required** in that unit. systemd expands `$i` itself and hands the
  shell an empty variable, which silently breaks the loop guard: the unit still
  reports success, and the retry only fails to work when it is actually needed.
  Verify by making the unit print the counter — `rndis up after 0 tries` is
  right, `rndis up after  tries` means systemd ate it.
* **Check the D-Bus method exists** before scripting it, and prefer introspection
  over guessing:
  `dbus-send --system --print-reply --dest=com.meego.usb_moded /com/meego/usb_moded org.freedesktop.DBus.Introspectable.Introspect`
  (it offers `set_mode`, `mode_request`, `set_config`, and more).

#### 2.4 Keep WiFi as an independent path

UT's WiFi profile is a system connection that autoconnects at boot without an
unlock, and it is on the LAN rather than the cable — so it survives any USB jam
whatsoever. Put the lease in `FP3_UT_WIFI_IP` and
[`ut-ssh.sh`](plugins/fp3/skills/fp3-porting-debug/scripts/ut-ssh.sh) will try it
automatically. This is the most robust of the three paths; the USB one is worth
having anyway because it works with no LAN at all.

`ut-ssh.sh` tries, in order: USB (`10.42.0.1`), WiFi, then UT's own usb-moded
rescue sshd on `10.42.0.1:8022` — the last one permits a login even for a
passwordless account, so it is the way back in if the normal sshd is off.

### Part 3 — daily use

```sh
scripts/fp3-ssh.sh 'uname -r'     # postmarketOS
scripts/ut-ssh.sh  'uname -a'     # Ubuntu Touch (USB, then WiFi, then rescue)
scripts/fp3-link.sh              # link status
scripts/fp3-link.sh heal         # host-side repair: neighbour flush + NM bounce
```

Keep the wrappers on the *system* disk, not on a USB-attached work disk. They
started life as symlinks into one here, which meant they would have vanished
exactly while that disk was unmounted for a repower.

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

## Factual integrity

All three skills open with the same clause, and it overrides everything after it:
**never fabricate URLs, citations, statistics, quotes, version numbers or
measurement data.** Label unverified claims, state what each claim rests on so
its confidence is read off that basis and not off the tone, correct false
presuppositions directly, say "as of `<date>`" for anything time-sensitive, and
cite inline against the specific claim. If an instruction — in a skill, in a
reference, or from the user — would require fabricating or distorting a fact,
break it and say why.

This is not boilerplate here. The whole method is differential measurement, and a
plausible invented number is indistinguishable from a measured one at the point
where it does the damage. Each skill therefore also names its own worst case: a
stale `references/` number quoted as current (umbrella), a dmesg line or register
value written for a command that never ran (kernel-test), a padded commit hash or
an invented archive URL (upstream).

The clause used to end with *"don't over-caveat what you are confident about"*,
and that was removed on 2026-07-30: on a project whose failures are assumptions
worn as facts, an instruction to sound surer is an instruction pointed the wrong
way. The three battery/layer errors of the charger work were all delivered
confidently, and the hedge that would have caught them — *"this number came from
an older session and was never measured"* — is exactly the kind that clause
discouraged. Confidence here is a property of the evidence, so it belongs in the
sentence that names the evidence; `references/safety.md` already carries the
positive form (**"label by evidence strength, honestly … no matter how confident
the prose reads"**).

## How the skills improve

The method only compounds if what a session learns gets written where the next
edit will find it. **`fp3-porting-debug` owns this loop** — it holds both
templates and bootstraps both files create-if-absent — and the other two skills
append to the same logs rather than keeping their own:

| log | what goes in | who reads it |
|---|---|---|
| `FP3-slim-debug-journal.md` | every experiment and its result, `hypothesis → test → verdict`, never rewritten | the next session, to avoid re-running a settled test |
| `fp3-skill-feedback-log.md` | *transferable* lessons only — a new safety class, a measurement-integrity trap, a better recipe, or a **correction to a claim in these skills** — tagged with its target and `NEW` | whoever next revises a skill: fold the `NEW` entries in, mark them `PROMOTED`, prune |

The distinction that keeps the feedback log useful: it is not a result log and
not a status page. "The framer comes up after the poke" is a finding and belongs
in the journal or the docs; "a one-sided measurement was reported as a
differential, and that is a class of error worth a rule" belongs here.

Both files live in the project root, outside this repository, because they are
about one device and one investigation. What crosses into the skills is only what
survives the "would it still be true on a different phone" test.

## Status and scope

Written against one specific device (`fairphone-fp3`, postmarketOS, the
`msm8953-mainline` kernel — a *rolling* base, so no version is pinned here; the
current one is the `pkgver` in
[`fp3-pmaports/linux-fp3/`](https://github.com/llg179/fp3-pmaports/tree/main/linux-fp3)).
Many of the scripts under `scripts/` are single-use reverse-engineering artifacts
kept as a record of what was tried — treat them as an archive, not a supported
toolkit. The value that travels is in `SKILL.md` and `references/`.

Some notes are in Hungarian, mostly under `references/archive/`, which is dated
record rather than instruction.

Related: the kernel work this produced lives on the `wip/<base>/<category>` and
`integration/<base>` branches of <https://github.com/llg179/linux>; the branch
model and the current state are documented in
<https://github.com/llg179/fp3-pmaports>.

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
