# fp3-kernel-test — Recovery procedures (full text)

> Split out of `SKILL.md`; loaded on demand when a slot/link/rootfs needs recovering.

## Recovery (getting back to a known state — this is method, keep it sharp)

The device is disposable and dual-slot, so *nothing here is fatal* — but each
recovery costs time, so recognise the state fast:

- **`18d1:d001` is ambiguous** — it is *both* the bootloader-fastboot gadget *and*
  pmOS's own CDC-NCM network gadget. Don't assume it's fastboot. Disambiguate by the
  USB descriptor (`lsusb -v -d 18d1:d001 | grep -E "bInterfaceClass|iSerial"`):
  CDC-NCM / iSerial "postmarketOS" = **pmOS booted fine** (that's why `fastboot
  devices` is empty — no fastboot iface).
- **"ping works, ssh refused/timed-out" is usually a missing host route, not a
  boot-loop.** pmOS exposes a CDC-NCM gadget; the host must bind its iface and own an
  address on the device's subnet (the device runs a tiny DHCP server and answers on
  `$FP3_DEV_IP`, handing the host `.2`). Disambiguate boot-loop vs route-miss via the
  USB descriptor (above) before burning an hour.
- **Stabilise the link once, host-side, instead of fighting it every boot (the method).**
  The gadget picks a *random* MAC each boot, so a MAC-based predictable iface name
  (`enx<mac>`) changes every time and any manually-added address is lost. Two host-side
  pieces kill both problems with zero device-side risk (nothing on the phone changes):
  - **Pin a stable iface name** with a systemd `.link` that matches the gadget by a
    boot-invariant property — its *driver* (`cdc_ncm`) or USB VID:PID — and renames it,
    e.g. `/etc/systemd/network/10-fp3.link` = `[Match] Driver=cdc_ncm` + `[Link]
    Name=fp3` (and `MACAddressPolicy=none` to keep the device's own MAC). Verify without
    a reboot via `udevadm test-builtin net_setup_link /sys/class/net/<cur>` (expect
    `ID_NET_NAME=<yourname>`); it applies on the *next* device (re)appearance, so the
    live link is untouched.
  - **Pin the host address** with a network-manager profile bound to that stable *ifname*
    (not the MAC), static `<host>/<prefix>` matching the device subnet, autoconnect on.
    ☠️ Add the new profile *before* deleting the old auto-created one — deleting the
    *active* profile instantly drops the live link (recover with a manual
    `ip addr add`). Leave the machine's real ethernet profile alone.
  - **Verify** with one controlled reboot on known-good firmware: the iface should come
    back under the fixed name with the address auto-assigned and TCP up in ~tens of
    seconds, no manual step. After this, every cold-boot is deterministic.
  - Optional convenience: wrap the "ensure host IP then ssh/scp" and "status / passive-
    wait" moves in small scripts (this repo ships `fp3-ssh` and
    `fp3-link {status|up|wait}` in `fp3-porting-debug/scripts/`, symlinked into `/usr/local/bin`).
    They're just shorthand for the steps above — if absent, do the steps directly.
- **CDC-NCM JAM (`NETDEV WATCHDOG: transmit queue timed out`; ping-alive but TCP dead):
  the device SELF-RECOVERS in minutes — wait passively, or reboot the DEVICE.**
  ☠️☠️ **NEVER restart/reset USB (or the link) on the HOST to "force a rebind".** That
  means no `echo 1 > /sys/bus/usb/devices/*/remove`, no `authorized` toggle, no
  `USBDEVFS_RESET` ioctl, no cdc_ncm/port unbind-rebind, **and** no `ip link down/up` /
  `nmcli` link cycling. Two reasons, both hard-learned: (1) it does **not** clear a
  *device-side* gadget jam — it pushes the device from *recoverable* (TCP-dead) to
  *not-enumerating at all*; (2) **the host's `/mnt` work disk is itself USB-attached, so a
  host USB reset can disconnect `/mnt` mid-session** (loses the kernel tree, firmware,
  scripts, docs). Recovery is patience or a **device reboot** — never a host-side USB/link
  restart. The one *targeted, non-USB* gentle move allowed: the flapping gadget
  re-enumerates with a **new random MAC**, leaving a stale host ARP for `$FP3_DEV_IP`;
  clear it **once per new MAC** with `ip neigh flush dev fp3 && ip addr replace
  $FP3_HOST_IP/16 dev fp3`, then a single spaced SSH probe. Otherwise just wait — TCP
  probes themselves queue packets and prolong the jam.
- **A/B retry fallback:** a slot that never marks boot-successful decrements its
  retry count each boot and eventually lk2nd falls back to the *other* slot. So a
  `reboot bootloader` from the test slot can land you on the oracle. `fastboot
  set_active b` resets the count for one clean boot.
- **After a slot-swap round-trip (pmOS→UT→pmOS via `set_active` + warm `fastboot reboot`), a COLD
  power-cycle is the reliable boot — warm reboot loops, and cross-slot fsck is necessary-but-not-
  sufficient.** Diagnosis of the resulting loop: host dmesg `cdc_ncm register/unregister` + a rising
  `usb device number` every ~3-30 s = the kernel comes up (gadget enumerates) then resets ~3-9 s later;
  a *decrementing* `slot-retry-count` (e.g. 7→5) confirms it's a real boot-fail, not NCM flakiness (the
  connect/disconnect cadence + retry-count together disambiguate boot-loop from link-wedge). The rootfs
  is dirty from the half-boots (`e2fsck` shows `recovering journal` + orphan-clear), so fsck it cross-slot
  first (recovery recipe below) — **but the fsck alone does NOT break the loop; the next warm `fastboot
  reboot` loops identically.** The actual fix is a **cold power-cycle** (hold Power ~10 s → power-on),
  which boots first try. **So default to a cold power-cycle after any slot-swap round-trip, not a warm
  reboot.** (Worked example, folyt.77/154: both swap directions needed a cold cycle; warm boot stuck in
  fastboot both ways.)
- **Truly wedged (no usable interface — raw configfs gadget, or a hung fastboot
  pipe):** host-side USB resets do **not** clear a device-side gadget hang. Only fix
  is physical: hold Power ~10 s, then Power+VolDown → fresh fastboot. This needs the
  user. Prefer a booted-OS `reboot` over hammering flaky `fastboot` commands, which
  are a recurring trigger for this wedge.
- **Repairing a broken test-slot rootfs from the oracle:** the pmOS rootfs is a
  nested loop image inside its system partition. From the oracle: create the
  partition node, `losetup -P`, `e2fsck -fy` the inner partitions (this clears the
  ext4 `orphan_present` flag that otherwise blocks a RW-mount on the old kernel),
  fix files, `set_active b`. If the old kernel still won't RW-mount, `debugfs -w`
  edits without mounting. From the oracle, reboot-to-bootloader needs root
  (`sudo -S reboot bootloader`; plain `adb reboot bootloader` = permission denied).
  Practical notes from a real run: the oracle's `e2fsck` may not be on `sudo`'s PATH
  (`which` finds nothing) — call it by full path (`/sbin/e2fsck`); `adb push` into
  `/data/local/tmp` is denied on the UT oracle, so run repair commands inline
  (`adb shell 'echo <pw> | sudo -S sh -c "…"'`, never `sudo adb`). **After the fsck,
  expect the *first* test-slot boot to still loop once and the *second* to come up
  clean** — the recovered journal + cleared `orphan_present` settle over one extra
  reboot, so don't declare the repair failed until you've let it retry twice.
  ☠️ **The system partition's device node is `/dev/mmcblk0pNN`, NOT
  `/dev/block/mmcblk0pNN`** — `losetup -fP /dev/block/…` fails *silently* with `rc=1`
  and no message on this oracle; `find /dev -name mmcblk0pNN` first (pmOS system_b =
  `mmcblk0p31`). **`losetup -fP` exposes a nested MBR** → `loopXp1` = `pmOS_boot`
  (ext2), `loopXp2` = `pmOS_root` (ext4); **fsck BOTH** — on a real reboot-loop run
  the ext2 boot partition was dirty too (`FILE SYSTEM WAS MODIFIED`), not just the
  ext4 root. Note `loop0` is the oracle's own android-rootfs, so `-fP` lands on
  `loop1`. For the paired **disk cleanup** (the loop-rootfs runs ~90 %+): mount
  `loopXp2` and clear `/var/cache/apk/*` (the biggest hog — it balloons to ~64 MB
  once the device has network for `apk`) and the journal (`find …/var/log/journal
  -name '*.journal*' -delete`), which freed ~90 MB in one run. **The dirty fs was the
  actual loop cause here** (recovered journal + orphan-clear), not disk-full — fsck
  fixed it and the *second* boot came up clean; leftover audio-RE staging under
  `/home/*` is not yours to delete.
- **A dead slot that drops to fastboot on boot is almost never the `adsp.mbn` you
  flashed — the co-processor firmware loads *post-kernel* (remoteproc), so a bad ADSP
  image can't stop the kernel from booting.** A fastboot fallback is a boot-image / lk2nd
  / rootfs-level failure. The usual real cause here is a **dirty loop-rootfs** from a
  prior crash-loop (fsck needed), not your firmware. Don't waste time re-flashing the
  ADSP to "fix boot"; fsck the rootfs.
- **Recover (or pre-stage a firmware into) a broken slot by mounting its rootfs from the
  *other, healthy* slot — no reflash.** Boot the oracle (UT/slot_a; it boots reliably),
  then reach the test slot's pmOS rootfs directly: it's a full-disk image on a raw
  partition (here `system_b` = a partition whose contents are a DOS-partitioned image), so
  `losetup -fP /dev/<system_b>` exposes `loopNp1/loopNp2`, `e2fsck -y loopNp2` (clears the
  crash-loop dirt), `mount loopNp2 /mnt` → you now have the dead OS's `/` offline. From
  there restore `adsp.mbn.stockbak` → `adsp.mbn`, free disk (`rm` stale
  `var/log/journal/*/*.journal`, apk cache — a >90%-full rootfs is itself a boot/deploy
  hazard), or stage a cave; `umount; losetup -d`. This turns "slot won't boot" into a
  ~2-minute offline edit and needs no fastboot/pmb reflash. (Do it all rooted via the
  oracle's `sudo`, never `sudo adb`.)
  - **Concrete map + method (folyt.134):** on this device the pmOS rootfs is NOT on userdata
    (p62 is UT's) — it's on **`system_b` (`/dev/mmcblk0p31`)**, onto which a *whole DOS-partitioned
    disk image* is written raw (`blkid` shows `PTTYPE="dos"` and *no* filesystem directly on p31).
    By-name symlinks are absent, so find it with `blkid`. Then from UT:
    `LD=$(losetup -fP --show /dev/mmcblk0p31)` → `${LD}p1`=pmOS_boot(ext2), `${LD}p2`=pmOS_root(ext4)
    → `e2fsck -fy ${LD}p2` → `mount ${LD}p2 /mnt/pmroot` → read the tee'd readout / restore
    `adsp.mbn.stockbak` / free disk → `sync; umount; losetup -d $LD`. **A successful `losetup -d`
    is itself proof the umount was clean** — it fails (busy) if anything still holds the loop, so it
    doubles as the "safe to switch slots" check.
- **Stuck at the Fairphone logo after a pmOS "kernel update" → you flashed over lk2nd; `pmb flasher
  flash_lk2nd` recovers it.** Symptom: every fresh build hangs identically at the logo regardless of
  content, drops to fastboot, dark after `continue`. Cause = `pmb flasher flash_kernel` overwrote the
  342 KB lk2nd on `boot` with a raw boot.img (safety rule 12). Fix: `pmb flasher flash_lk2nd` → extlinux
  boots the old kernel already on loop1p1 → pmOS up first try (~12 s). Then update the kernel the RIGHT
  way (into the rootfs: `pmb sideload` / `apk add --allow-untrusted` / full `pmb install`), never
  `flash_kernel`. Diagnosis shortcut: ask the user what's ON SCREEN — "Fairphone logo" = kernel never
  started (bootloader/boot-image), not a kernel-content bug.
- **UT (Halium) cross-slot repair of a runtime-written `/etc` file: it lives on the WRITABLE OVERLAY
  (`userdata`), NOT on the `system_a` base.** Anything written at runtime to UT's `/etc/systemd/system/`
  goes to the userdata overlay (system_a is a read-only base). So to remove a boot-hanging service
  cross-slot (from pmOS/slot_b): `mount /dev/mmcblk0p62 /mnt/ud` → the unit is at
  `/mnt/ud/system-data/etc/systemd/system/` (+ its `sysinit.target.wants/` symlink) → `remount,rw`,
  `rm` both, `sync`. The `system_a` partition (mmcblk0p30) holds only the Halium base and won't have it.
  (Same cross-slot pattern as the loop-rootfs fsck above, just on the correct overlay partition —
  this is the recovery for the boot-armed-diag hang, safety rule 14.)
- **Duplicate the device address on only ONE host iface.** If you `ip addr add
  $FP3_HOST_IP/16` onto the wrong iface (e.g. the machine's real ethernet) *as well as* the
  CDC-NCM `fp3` iface, the kernel may route the device subnet out the wrong interface →
  `No route to host` even though `fp3` looks correctly configured. Keep the device-subnet
  address on the gadget iface only (`ip addr del` it from any other), then `ip route flush
  cache`.

---

