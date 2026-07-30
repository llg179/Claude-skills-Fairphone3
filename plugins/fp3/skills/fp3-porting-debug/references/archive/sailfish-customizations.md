# Sailfish FP3 port — build customizations log

All deviations from upstream/base files are documented here:
what changed, why, from what to what, and the effect.

---

## ramdisk: `init` script

**File:** `hybris/hybris-boot/ramdisk/init` (in the built ramdisk: `/init`)
**Upstream:** `https://github.com/mer-hybris/hybris-boot` — stock `init` script
**Modified:** 2026-06-25

### 1. `fail()` function — dmesg dump to SD card

**From:**
```sh
fail()
{
    echo "initrd: Failed" > /dev/kmsg
    echo "initrd: $1" > /dev/kmsg
    reboot2 recovery
}
```

**To:**
```sh
fail()
{
    echo "initrd: Failed: $1" > /dev/kmsg
    if [ -n "$SDLOG" ]; then
        echo "$(cat /proc/uptime | cut -d' ' -f1) initrd: FAIL: $1" >> $SDLOG
        echo "--- dmesg ---" >> $SDLOG
        dmesg >> $SDLOG
        sync
        umount /sdlog 2>/dev/null
    fi
    reboot2 recovery
}
```

**Why:** When the ramdisk boot fails (e.g. root mount error), USB telnet never
starts, leaving no way to read the error. `fail()` now writes the error message
and the full dmesg to the SD card before rebooting to recovery.

**Effect:** On boot failure, `/boot.log` on the SD card contains the kernel log.
Readable from TWRP or any recovery after the failed boot attempt.

---

### 2. Early SD card mount + `log()` function

**From:** No SD card logging; all output went only to `/dev/kmsg`.

**To:** Inserted after `/dev` is mounted:
```sh
SDLOG=""
mkdir -p /sdlog
if mount -t vfat /dev/mmcblk1p1 /sdlog 2>/dev/null; then
    SDLOG=/sdlog/boot.log
    echo "=== initrd boot $(cat /proc/uptime) ===" >> $SDLOG
    echo "initrd: SD card mounted, logging to $SDLOG" > /dev/kmsg
fi

log() {
    echo "initrd: $1" > /dev/kmsg
    [ -n "$SDLOG" ] && echo "$(cat /proc/uptime | cut -d' ' -f1) initrd: $1" >> $SDLOG
}
```

**Why:** On FP3, `/dev/mmcblk1p1` is the first SD card partition. If an SD card
is present, it is mounted at the very start of init (after proc/sys/dev mounts,
before root mount) and logging begins immediately. If no SD card is inserted,
the mount silently fails and `$SDLOG` stays empty — everything continues normally,
just without SD logging. Does not interfere with USB charging (no RNDIS involved).

**Effect:** With an SD card inserted, `/sdlog/boot.log` contains a timestamped
log of every init step.

---

### 3. Redirect `root-mount` output to SD log

**From:**
```sh
$MNTSCRIPT $ROOTMNTDIR
```

**To:**
```sh
log "Running $MNTSCRIPT"
$MNTSCRIPT $ROOTMNTDIR >> ${SDLOG:-/dev/null} 2>&1
```

**Why:** `root-mount` has its own `log()` but its stdout/stderr was discarded.
LVM and e2fsck output (likely the actual cause of root mount failures) is now
captured in the SD log.

**Effect:** If `vgchange` or the ext4 mount fails, the concrete error message
appears in the log.

---

### 4. dmesg dump before `switch_root`

**From:** No ramdisk-phase kernel log was saved on successful boot.

**To:**
```sh
log "Switching to rootfs at ${ROOTMNTDIR}, with init ${INITBIN}"
if [ -n "$SDLOG" ]; then
    echo "--- dmesg at switch_root ---" >> $SDLOG
    dmesg >> $SDLOG
    sync
    umount /sdlog 2>/dev/null
fi
exec switch_root ${ROOTMNTDIR} ${INITBIN}
```

**Why:** If the ramdisk phase succeeds but the Sailfish init (systemd, lipstick)
hangs later, the ramdisk-era kernel log is lost. This dump preserves it.
The `umount` is required because after `switch_root` the `/sdlog` mount point
is no longer accessible from the old namespace.

**Effect:** On every boot (successful or not) the full ramdisk-phase kernel log
is preserved on the SD card.

---

## ramdisk: `sbin/root-mount` script

**File:** `hybris/hybris-boot/ramdisk/sbin/root-mount`
**Modified:** 2026-06-25

### 1. SD log detection in `root-mount`

**From:**
```sh
log()
{
    echo "root-mount: $1" > /dev/kmsg
}
```

**To:**
```sh
SDLOG=""
[ -d /sdlog ] && mount | grep -q /sdlog && SDLOG=/sdlog/boot.log

log()
{
    echo "root-mount: $1" > /dev/kmsg
    [ -n "$SDLOG" ] && echo "$(cat /proc/uptime | cut -d' ' -f1) root-mount: $1" >> $SDLOG
}
```

**Why:** `root-mount` is called as a child process from `init` and does not
inherit shell variables. It must re-detect whether the SD card is mounted
(`mount | grep`) and write to the same log file independently.

**Effect:** LVM discovery, VG activation, and ext4 mount steps all appear in
the SD log under the `root-mount:` prefix.

---

## Kernel defconfig: `lineageos_FP3_defconfig`

**File:** `kernel/fairphone/sdm632/arch/arm64/configs/lineageos_FP3_defconfig`
**Modified:** 2026-06-21

### Sailfish mer-kernel-check required options

The upstream LineageOS FP3 defconfig was missing several Sailfish-mandatory
kernel options. The `mer_verify_kernel_config` perl script reported 9 errors;
8 were fixed:

| CONFIG | From | To | Why |
|--------|------|----|-----|
| `CONFIG_DUMMY` | `=y` | unset | mer-check requires it off; dummy net interface conflicts |
| `CONFIG_VT` | unset | `=y` | Virtual terminal; needed for Sailfish console handling |
| `CONFIG_FHANDLE` | unset | `=y` | systemd file handle API |
| `CONFIG_DEVTMPFS` | unset | `=y` | Automatic /dev population at boot |
| `CONFIG_DEVTMPFS_MOUNT` | unset | `=y` | /dev auto-mount without explicit initrd step |
| `CONFIG_SYSVIPC` | unset | `=y` | SysV IPC; required by several Sailfish middleware components |
| `CONFIG_NET_L3_MASTER_DEV` | unset | `=y` | VRF/L3 master device; required by connman |
| `CONFIG_NLS_UTF8` | unset | `=y` | UTF-8 filename encoding (also required for vfat SD card mounts) |

**Not fixable:**
- `CONFIG_NETFILTER_XT_MATCH_QTAGUID` — symbol does not exist in kernel 4.9
  (replaced by eBPF-based netstat after Android Q; the checker marks it
  "deprecated/optional", does not block boot)

---

## Notes on applying ramdisk changes to the build

The `init` and `root-mount` changes above were applied to the manually extracted
ramdisk at `$FP3_ROOT/ramdisk-work/`. To repack and produce a new
boot image:

```bash
# 1. Repack ramdisk
cd $FP3_ROOT/ramdisk-work
find . | cpio -o -H newc | gzip > ../ramdisk-patched.img.gz

# 2. Reassemble boot image (keeping original kernel)
# -- see build-droid-hal.sh or use abootimg/mkbootimg --
```

**Preferred approach:** Backport the changes into the source tree
(`hybris/hybris-boot/` repo) so that the next `make hybris-hal` includes them
automatically without manual ramdisk surgery.

### v3: init-debug support + SD bind-mount (2026-06-25)

**Changes:**
- `init` now prefers `/init-debug` over `/sbin/preinit` if it exists in the rootfs
- When booting via `init-debug`, `/sdlog` is bind-mounted into the rootfs instead of unmounted, so init-debug can write to `/sdlog/init-debug.log`
- `/sdlog` directory created in Sailfish rootfs as bind-mount target
- `init-debug` patched to log to `/sdlog/init-debug.log` instead of `/init.log`
- `/init_enter_debug2` placed in rootfs to halt boot and open telnet on 2323

**Effect:** On boot, init-debug runs in real rootfs mode, sets up RNDIS USB (192.168.2.15),
opens telnet on port 2323, logs all output to SD card.

---

### v2 logging overhaul (2026-06-25)

**Changes:**
- **Log rotation:** Each boot gets its own directory `/sdlog/boot-N/` (N=0,1,2,...); last 5 kept
- **Per-module log files:** `init.log` and `root-mount.log` are separate files in the boot dir
- **dmesg snapshots:** `dmesg-fail.log` on failure, `dmesg-switch_root.log` on success
- **root-mount verbosity:** pvresize, vgchange, lvs, e2fsck, resize2fs all logged to `root-mount.log`
- **SDLOG_DIR env:** `init` passes `SDLOG_DIR` to `root-mount` via environment so both write to same boot dir
- **Always logs:** dmesg dumped at `switch_root` even on successful boot

---

## Flash log: sailfish.img001 → userdata (2026-06-25)

**What:** `sailfish.img001` (Android sparse image, 1.4 GB) flashed to the
`userdata` partition (`/dev/block/bootdevice/by-name/userdata`, ~52 GB).

**Why TWRP sideload failed:** The file is an Android sparse image, not a TWRP
installable zip. Wrapping it in a zip and sideloading stopped at ~47% — TWRP
ran out of `/tmp` space trying to unzip a 1.4 GB file.

**Method used:**
```bash
# Push image to TWRP /tmp
adb push sailfish.img001 /tmp/sailfish.img001
# Convert sparse and write directly to partition
adb shell "simg2img /tmp/sailfish.img001 /dev/block/bootdevice/by-name/userdata"
```

**Result:** DONE — `simg2img` reported success. Userdata partition contains
the Sailfish rootfs (ext4/LVM).

---

## Flash log: hybris-boot-sdlog.img → boot_a (2026-06-25)

**What:** `hybris-boot-sdlog.img` (22 MB) flashed to `boot_a` slot via fastboot.

**Sequence:**
1. TWRP flashed to `boot_a` first (for sideload attempt) — overwrote Sailfish boot
2. `fastboot flash boot_a hybris-boot-sdlog.img` — restored correct boot image
3. `fastboot reboot` → "Fairphone powered by Android" bootanimation visible

**Status (2026-06-25 08:19 UTC):** Phone showing bootanimation, boot outcome pending.

---

## Fix: system and vendor partition mounts (2026-06-25)

**Problem:** After `switch_root`, Sailfish systemd started but `droid-hal-init` failed
silently. Root cause: `/system` directory in the Sailfish root was empty — the Android
`system_a` partition was never mounted. `droid-hal-init` is an Android ELF binary that
requires `/system/bin/bootstrap/linker64` to start.

**Why it was missing:** The `fstab` in the Sailfish image only contains the LVM volumes
(`/` and `/home`). The `/system` and `/vendor` mounts are normally provided by
`droid-config-fp3` (Step 6 of HADK) which was not built yet.

**Fix:** Created systemd mount units manually in the Sailfish image:

`/etc/systemd/system/system.mount`:
```ini
[Unit]
Description=Mount Android system partition
DefaultDependencies=no
Before=local-fs.target droid-hal-init.service

[Mount]
What=/dev/block/mmcblk0p30
Where=/system
Type=ext4
Options=ro,noatime
```

`/etc/systemd/system/vendor.mount`:
```ini
[Unit]
Description=Mount Android vendor partition
DefaultDependencies=no
Before=local-fs.target droid-hal-init.service

[Mount]
What=/dev/block/mmcblk0p32
Where=/vendor
Type=ext4
Options=ro,noatime
```

Both symlinked into `local-fs.target.wants/`.

**Partition mapping (FP3, MSM8953):**
- `system_a` → `/dev/block/mmcblk0p30`
- `vendor_a` → `/dev/block/mmcblk0p32`

**How applied:** Mounted `sailfish-raw.img` on PC via loop device + LVM, edited files,
unmounted, re-flashed to phone userdata via `simg2img` through TWRP ADB shell.

---

## init-debug patches (2026-06-25)

**File:** `/init-debug` in Sailfish rootfs

### Patch 1: SD card logging redirect
```sh
exec > /sdlog/init-debug.log 2>&1   # line 24, top of script
```
**Why:** init-debug normally logs to `/init.log` which is unreadable after boot. Redirected to SD card so logs survive reboot.

### Patch 2: systemd output to SD card
```sh
exec $INIT --log-level=debug --log-target=kmsg &> /sdlog/systemd-stdout.log
```
**Why:** Capture systemd's stdout/stderr on SD for post-mortem analysis.

### Patch 3: continuous dmesg capture (v4, 2026-06-25)
```sh
dmesg -w >> /sdlog/dmesg-systemd.log 2>&1 &
exec $INIT --log-level=debug --log-target=kmsg &> /sdlog/systemd-stdout.log
```
**Why:** After `exec $INIT`, the shell is replaced by systemd. A background `dmesg -w` forked before exec becomes an orphan (adopted by systemd) and captures all kernel messages including systemd service failures — even if systemd crashes quickly.

**Effect:** `/sdlog/dmesg-systemd.log` contains full kernel log from systemd start until crash/reboot.

---

## Boot debug findings (2026-06-25)

### SD card log structure
Each boot creates `/sdlog/boot-N/` directory with:
- `init.log` — ramdisk init steps with timestamps
- `root-mount.log` — LVM activation, pvresize, e2fsck, resize2fs output
- `dmesg-switch_root.log` — full kernel log at switch_root moment

`/sdlog/init-debug.log` — appended across boots (init-debug output)

### boot-3 findings
- LVM **first-boot resize** triggered: root 1.51→2.93 GiB, home 32M→45.81 GiB (expected, one-time)
- inject_loop ran with HALT_BOOT=y — phone halted waiting for telnet "continue"
- telnetd PID 734 confirmed listening on 192.168.2.15:2323
- **Problem: `18d1:d001` RNDIS never visible on PC** despite configfs setup on phone

### RNDIS telnet not working — known issue
- Phone side: USB gadget set up via configfs (`/config/usb_gadget/g1/`), UDC=`7000000.dwc3`
- PC side: `18d1:d001` never enumerated, `rndis_host` driver never loads
- One earlier boot DID configure `enx2a49e310a5db` (confirmed in background task log)
- Suspected cause: UDC already bound to old `18d1:d00d` gadget from ramdisk phase; init-debug doesn't unbind before reconfiguring
- Workaround: use HALT_BOOT=n (remove `init_enter_debug2`) and capture logs to SD card instead

### dsme.service masked (2026-06-25)

**File:** `/etc/systemd/system/dsme.service` → symlink to `/dev/null`

**Why:** DSME (Device State Management Entity) has `StartLimitAction=reboot` in its service unit. When droid-hal-init fails (no Android HAL config without droid-config-fp3), DSME doesn't receive the boot-complete signal and crashes repeatedly. After 3 crashes in 600 seconds, systemd initiates a reboot. This caused the crash loop.

Additionally, DSME arms the hardware watchdog (`/dev/watchdog`). If DSME crashes without closing the watchdog fd, the hardware watchdog fires ~60-90s later causing another reboot.

**Effect:** DSME doesn't start; no boot-timeout enforcement; no watchdog arming. The ramdisk's `echo V > /dev/watchdog` disables the hardware watchdog, and our debug service writes V again for safety. Phone stays up indefinitely until we telnet in.

**Note:** Re-enable DSME once droid-hal-init works properly (after building droid-config-fp3).

---

### sailfish-debug.service updated (2026-06-25)

**Key changes from v1:**
- `echo V > /dev/watchdog` — disable hardware watchdog before anything else
- `ip link set usb0 up` — correct interface name (usb-moded configfs creates `usb0`, not `rndis0`)
- `ip addr add 192.168.2.15/24 dev usb0` — set IP on usb0

**usb-moded network config (discovered):**
- `usb-moded-configfs-fp4.ini`: `interface = usb0`, `function_rndis = rndis.usb0`, `configs/b.1`
- No `developer_mode-configfs.ini` in dyn-modes (only `-android` variant) → usb-moded fell back to android sysfs backend → RNDIS not configured properly → PC never got rndis_host
- Fix: debug service now uses `usb0` directly and feeds proper IP

---

### Boot crash loop findings (2026-06-25)

USB sequence during Sailfish boot (from PC dmesg):
1. `18d1:d00d` — ramdisk + init-debug phase (PC sees bootloader USB, init-debug USB rebind fails)
2. `22b8:2e81` — usb-moded transitional mode
3. `22b8:2e76` — Sailfish developer/RNDIS mode (usb-moded active, lasts ~91s)
4. disconnect → reboot → repeat

Key facts:
- `22b8:2e76` appears on PC but no rndis_host driver loads (USB class descriptors unclear)
- Sailfish systemd IS starting (usb-moded proves it)
- ~91s after usb-moded: crash (watchdog timeout or service failure)
- `RuntimeWatchdogSec` in `/etc/systemd/system.conf` likely set to 60-90s → killing system

### Rootfs image workflow
All rootfs changes applied by:
1. `sudo losetup -f --show sailfish-raw.img`
2. `sudo vgchange -a y sailfish`
3. `sudo mount /dev/sailfish/root /mnt/sailfish`
4. Edit files
5. `sudo umount`, `vgchange -a n`, `losetup -d`
6. `adb push sailfish-raw.img /tmp/` (no sudo needed)
7. `adb shell "dd if=/tmp/sailfish-raw.img of=/dev/block/mmcblk0p62 bs=4096"`

---

### developer_mode-configfs.ini létrehozva (2026-06-25)

**File:** `/etc/usb-moded/dyn-modes/developer_mode-configfs.ini` (ÚJ)

**Probléma:** usb-moded "USB gadget silent after switch_root" — a telefon futott de nem mutatott USB eszközt PC-nek.

**Root cause:** Csak `developer_mode-android.ini` volt jelen, ami `/sys/class/android_usb/android0/` android sysfs backendbe próbált írni. Ez az interfész NEM LÉTEZIK az FP3 kernelén (csak configfs alapú USB gadget van). usb-moded csendesen meghiúsult, nem konfigurált USB gadgetet.

**Fix:** `developer_mode-configfs.ini` létrehozva a dyn-modes könyvtárban:
```ini
[mode]
name = developer_mode
module = none
network = 1
network_interface = usb0
appsync = 1
softconnect = 1

[options]
idProduct = 0A02
nat = 0
dhcp_server = 1
```

**Hogyan működik:** usb-moded a kernel által elérhető backend alapján választ: ha nincs `/sys/class/android_usb/android0/` (android sysfs), configfs backendre vált. A configfs backend a már meglévő `usb-moded-configfs-fp4.ini` alapján konfigurálja a gadgetet (`configs/b.1`, `rndis.usb0`, `usb0` interface). Az ini fájl `-configfs.ini` suffixe biztosítja a helyes mód betöltését.

**Elvárt hatás:** `22b8:2e76` megjelenik, PC-n `rndis_host` betölt, `enx*` interfész látható → `telnet 192.168.2.15 23` sikerül.

---

### Ramdisk szintű USB RNDIS + telnet (2026-06-25)

**File:** `hybris/hybris-boot/ramdisk/init` — `setup_usb_rndis()` funkció hozzáadva

**Probléma:** Élő debug elérés kell a boot legkorábbi fázisában.

#### USB RNDIS kísérletek — mi nem sikerült és miért

| Kísérlet | Eredmény | Ok |
|----------|----------|----|
| Külön g2 gadget létrehozása | ❌ UDC bind néma fail | g1 még UDC-re kötve, g2 nem tud kötni |
| g1 modosítás, eredeti function megtartva | ❌ Disconnect → semmi | Régi function (ffs.adb?) és rndis.usb0 konfliktus configs/b.1-ben |
| g1 teljes rebuild: unbind → symlink törlés → rndis.usb0 → rebind | ✅ **EGYSZER MŰKÖDÖTT** (PC uptime ~35785s, 169s-ig állt) | Helyes megközelítés |
| Fenti, de PC-n rndis_host nem töltve | ❌ 22b8:2e76 megjelent de enx* nem kötött | PC-n kézzel kell: `echo "22b8 2e76" > /sys/bus/usb/drivers/rndis_host/new_id` |
| Fenti, watchdog keepalive nélkül | ❌ 90-169s után reset | MSM watchdog tüzel, `echo V > /dev/watchdog` nem állítja le |
| Watchdog keepalive (echo 1 / 10s) | ✅ 452s túlélés bizonyítva | Keepalive működik |

#### Jelenlegi állapot: setup_usb_rndis MOST VALÓSZÍNŰLEG működik, de SD log hiánya miatt vak voltunk

Az SD log javítás (`/dev/block/mmcblk1p1`) után az usb-debug.log megmutatja majd:
- UDC megtalálva-e (`ls /sys/class/udc/`)
- g1 unbind/rebind exit code
- rndis.usb0 function mkdir exit code
- Megjelent-e a hálózati interfész

#### Konfirmált tények

- `22b8:2e76` (RNDIS, Fairphone VID:PID) jelenik meg a PC-n ha setup sikerül
- PC-n szükséges minden session elején:
  ```bash
  sudo modprobe rndis_host
  echo "22b8 2e76" | sudo tee /sys/bus/usb/drivers/rndis_host/new_id
  echo "22b8 2e81" | sudo tee /sys/bus/usb/drivers/rndis_host/new_id
  ```
- configfs function neve: `rndis.usb0` (usb-moded-configfs-fp4.ini alapján)
- gadget configs path: `configs/b.1`
- Telefon IP: `192.168.2.15`, PC IP: `192.168.2.1`
- Telnet port: 23

**Fix (jelenlegi init):**
1. configfs mount
2. RNDIS gadget létrehozása (`22b8:2e76`, `configs/b.1`, `rndis.usb0`)
3. `ip addr add 192.168.2.15/24 dev usb0`
4. `telnetd -b 192.168.2.15:23 -l /bin/sh`
5. configfs bind-mount rootfs-be switch_root előtt (`/config`)

---

### sailfish-debug.service v3 (2026-06-25)

Új ExecStartPre: `dmesg > /sdlog/dmesg-at-usb-moded.log` és `journalctl -b > /sdlog/journal-at-usb-moded.log` — usb-moded induláskor SD-re snapshot.

---

### sdlog-dmesg.service (2026-06-25)

**File:** `/etc/systemd/system/sdlog-dmesg.service` + sysinit.target.wants symlink

Korai oneshot service: `dmesg -w >> /sdlog/dmesg-systemd.log &` — a teljes systemd fázis kernel logját írja SD-re folyamatosan.

---

### 28 service maszkolva (2026-06-25)

Az összes Android-függő és nem szükséges service maszkolva (`/dev/null` symlink):
droid-hal-init, droid-bootctl, droid-late-start, dummy_netd, init-done, bluebinder, sensorfwd, start-user-session, wayland.path, yamuisplash, rich-core-early-collect, runlevel-user-done, oneshot-root, oneshot-root-late, audiosystem-passthrough-dummy-af, connman, connman-vpn, mce, sailfish-fpd, sailfish-devicelock-encsfa-fpd, sailjaild, wait_for_keymaster, initial-bootstate, policies-setup, quota_nld, crash-reporter-endurance, crash-reporter-journalspy, nemo-devicelock.socket

---

### Ramdisk inject loop (2026-06-25)

**File:** `hybris/hybris-boot/ramdisk/init` — `ramdisk_inject_loop()` funkció hozzáadva

**Cél:** Interaktív boot debugging — a telefon a ramdisk fázisban megáll és vár, amíg a felhasználó telneten csatlakozik és manuálisan folytatja.

**Sorrend:**
1. `setup_usb_rndis()` — RNDIS gadget + telnetd indul
2. `ramdisk_inject_loop()` — létrehoz `/init-ctl/stdin` named pipe-ot, vár
3. Felhasználó csatlakozik: `telnet 192.168.2.15 23`
4. Lépésenkénti vizsgálat: rootfs `/rootfs`-en, LVM aktív, configfs `/config`-on
5. Folytatás: `echo continue > /init-ctl/stdin` → switch_root → systemd

**Elérhető parancsok a telnetből:**
- `echo continue > /init-ctl/stdin` — folytatja a bootot
- `echo reboot > /init-ctl/stdin` — újraindít
- `ls /rootfs` — Sailfish rootfs vizsgálata
- `cat /rootfs/etc/systemd/system/*.service` — service konfig
- `dmesg` — kernel log ramdisk fázisból
- `lvm lvs` / `lvm pvs` — LVM állapot

**hybris-boot-sdlog.img újraépítve:** setup_usb_rndis + ramdisk_inject_loop + dmesg SD-log + configfs bind-mount switch_root előtt

---

### ramdisk_inject_loop() watchdog keepalive + USB reconnect (2026-06-25)

**Probléma:** inject_loop-ban vár a telefon, de a kernel watchdog ~90-169s után tüzel és resetet okoz.

**Fix 1 — watchdog keepalive:**
```sh
(while true; do
    echo 1 > /dev/watchdog  2>/dev/null
    echo 1 > /dev/watchdog0 2>/dev/null
    sleep 10
done) &
WD_PID=$!
```

**Fix 2 — USB reconnect loop:**
```sh
(while true; do
    sleep 5
    IFACE=$(ls /sys/class/net/ 2>/dev/null | grep -E "^(rndis|usb)[0-9]" | head -1)
    if [ -z "$IFACE" ]; then
        log "USB iface eltűnt, újraindítás..."
        setup_usb_rndis
    fi
done) &
USB_PID=$!
```

**Fix 3 — telnetd dupla spawn megakadályozása:**
```sh
killall telnetd 2>/dev/null
telnetd -b 192.168.2.15:23 -l /bin/sh 2>/dev/null
```

**Hatás:** Telefon korlátlan ideig él az inject_loop-ban; USB disconnect esetén automatikusan újrahoz RNDIS-t.

---

### SD kártya logging — hibák és javítások (2026-06-25)

Ez a szekció összefoglalja az összes SD logging kísérletet, mi nem működött és miért.

---

#### ❌ Hiba 1: `-o rw,sync` mount opció (NEM a fő ok)

**Feltételezés:** `mount -t vfat -o rw,sync /dev/mmcblk1p1 /sdlog` sikertelen a 4.9.218-as kernelen.

**Valódi hatás:** Valószínűleg nem ez okozta a fő problémát. Eltávolítva, de önmagában nem oldotta meg.

---

#### ❌ Hiba 2: `sync` hiánya (részleges ok)

**Feltételezés:** FAT cache nem kerül ki a lemezre crash előtt → "Volume was not properly unmounted" TWRP dmesg-ben.

**Bizonyíték:** TWRP dmesg: `FAT-fs (mmcblk1p1): Volume was not properly unmounted` — ez azt jelzi valaki mountolta és nem umountolta. De ez lehet egy RÉGEBBI session dirty mountja is.

**Hatás:** `sync` hozzáadva minden SD-írás után. Önmagában nem oldotta meg a problémát.

---

#### ❌ Hiba 3: `2>/tmp/mnt_err` redirect — /tmp nem mindig létezik (részleges ok)

**Feltételezés:** `/tmp/mnt_err` redirect sikertelen → az egész mount sor mint parancs sikertelen → sdlog_init visszatér.

**Valóság:** `/tmp` LÉTEZIK a ramdiskban (ramdisk-work/tmp/ könyvtár van). Tehát ez NEM volt a probléma. De a kísérlet bemutatta, hogy a hibakeresés ilyen irányban zsákutca.

---

#### ✅ ROOT CAUSE: `/dev/mmcblk1p1` nem létezik — csak `/dev/block/mmcblk1p1`

**Felfedezés módja (2026-06-25):**
```
$ adb shell "ls -la /dev/block/mmcblk1p1 /dev/mmcblk1p1"
brw------- 1 root root 179, 65 ... /dev/block/mmcblk1p1
ls: /dev/mmcblk1p1: No such file or directory
```

**Magyarázat:** Az FP3 hybris-boot kernelen a devtmpfs a blokk eszközöket `/dev/block/` alkönyvtárba teszi (Android kernel konvenció), NEM a `/dev/` gyökérbe. A `mount -t vfat /dev/mmcblk1p1 /sdlog` tehát mindig csendesen sikertelen (nem létező eszköz, exit code 1), sdlog_init visszatér, SDLOG_DIR="" marad, **semmi nem kerül SD-re**.

**Miért volt "not properly unmounted" mégis?** A dirty bit boot-0..3-ból maradt (régi init, régi /dev/mmcblk1p1 elérési út, amely AZ AKKORI kernelen még működött). Az újabb init soha nem mountolta.

**Fix:**
```sh
# Volt:
mount -t vfat /dev/mmcblk1p1 /sdlog 2>/dev/null
# Javítva:
mount -t vfat /dev/block/mmcblk1p1 /sdlog 2>/dev/null
```

**Megjegyzés:** A régi init (boot-0..3) `/dev/mmcblk1p1`-et használt és működött — valószínűleg más kernel volt flashelve akkor (TWRP kernele más elérési utat használ). Az új hybris-boot image kernele Android-stílusú `/dev/block/` elrendezést követ.

---

#### Összefoglalás: SD logging iterációk

| Verzió | Módosítás | Eredmény | Ok |
|--------|-----------|----------|----|
| v1 (boot-0..3) | `mount /dev/mmcblk1p1` | ✅ MŰKÖDÖTT | Régi kernel/init kombó |
| v2+ | setup_usb_rndis hozzáadva | ❌ Semmi SD | `/dev/mmcblk1p1` nem létezik új kernelen |
| v3 | `-o rw,sync` eltávolítva | ❌ Semmi SD | Ugyanaz az ok |
| v4 | `sync` hozzáadva | ❌ Semmi SD | Ugyanaz az ok |
| v5 | `2>/tmp/mnt_err` diagnosztika | ❌ Semmi SD | Ugyanaz az ok |
| **v6** | **`/dev/block/mmcblk1p1`** | **⏳ Tesztelés alatt** | **Root cause javítva** |
