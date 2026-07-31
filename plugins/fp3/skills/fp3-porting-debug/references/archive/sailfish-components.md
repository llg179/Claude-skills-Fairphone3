# Sailfish OS — Fairphone 3 (fp3) port — komponens-eredet (provenance) napló

> ⚠️ **AI-generated.** This page — and the code, device tree and tooling it
> describes — was written by Claude (Opus 5) working under the direction of
> Lajosházi, László Gergely, who reviewed every change and made or reviewed
> every measurement it rests on. Kernel commits carry `Co-authored-by: Claude`;
> anything prepared for the LKML carries `Assisted-by:` instead and never a
> `Signed-off-by` from the assistant, since only a human can certify the DCO.

> Cél: **megosztható tapasztalat**. Minden komponens: honnan jön (repo + branch/commit),
> mi a szerepe, mit kellett módosítani és **miért**. A kronológiai részletek: `archive/boot-debug-log.md`.
> Build-recept és környezet: lentebb. Frissítendő minden új komponensnél/módosításnál.

## Cél-konfiguráció

| Tulajdonság | Érték |
|---|---|
| Eszköz | Fairphone 3 (`fp3`), SoC MSM8953 / Snapdragon 632, GPU Adreno 506, aarch64 |
| Android base a készüléken | **/e/OS A15 (LineageOS 22-alapú)**, build `BP1A.250505.005` (2026-06-10) |
| Sailfish hybris ág | **hybris-22.2** (Android 15) — mert a flashelt /e/OS A15-höz illeszkedik |
| Kernel | 4.9.x (sdm632), lineage-22.2 |
| Munkafa | `$FP3_ROOT/hadk22` (a régi 18.1 fa: `hadk/`, megtartva referenciának) |
| Sailfish Platform SDK | 4.6.0.13 (Sauna) tooling; target `fairphone-fp3-aarch64`, tooling `SailfishOS-5.0.0.62` |

> **Miért hybris-22.2 és nem 18.1:** a készülék /e/OS A15-öt futtat (system_a/vendor_a).
> Egy A11 (hybris-18.1) droid-hal-init nem linkel A15 libekkel (4 major ABI-eltérés,
> pl. libbacktrace→libunwindstack). Lásd a 18.1↔A15 ütközés diagnózisát a facts-ben.

---

## Komponensek — honnan jönnek

| Komponens | Repo | Branch / commit | Szerep | Módosítás? |
|---|---|---|---|---|
| hybris manifest | `mer-hybris/android` | `hybris-22.2` | repo manifest (default.xml) | — |
| **device tree** | `LineageOS/android_device_fairphone_FP3` | `lineage-22.2` | FP3 device config | — |
| **kernel** | `LineageOS/android_kernel_fairphone_sdm632` | `lineage-22.2` | 4.9 kernel | ✅ **defconfig** (lásd lent) |
| **vendor blobs** | `TheMuppets/proprietary_vendor_fairphone_FP3` | `lineage-22.2` (git-lfs) | proprietary HAL/firmware | ✅ **radio LFS pull** |
| hybris-boot | `mer-hybris/hybris-boot` | `a16` | boot image init/ramdisk | — (a manifest hozza) |
| droidmedia | `sailfishos/droidmedia` | `android15` | média HAL bridge | — (a manifest hozza) |
| selinux_stubs | `mer-hybris/android_external_selinux_stubs` | `hybris-22.2` | selinux stub | — |
| busybox prebuilt | `mer-hybris/android_external_busybox_prebuilt` | `master` | ramdisk busybox | — |
| **libhybris** | `sailfishos-mirror/libhybris` | `02f9f62678ba2902d5fc0a180e0526525cca0a3b` | `libui_compat_layer` + compat rétegek | ✅ **manifestbe felvéve** (base manifest kihagyja!) |
| **mer-kernel-check** | `mer-hybris/mer-kernel-check` | (manifest) | kernel-config ellenőrző | ✅ **QTAGUID opcionális** |
| **dhd (droid-hal-device)** | `mer-hybris/droid-hal-device` | `master` | droid-hal RPM build receptek | — (klónozva `hadk22/rpm/dhd`-be) |
| **droid-configs (alap)** | `mlehtima/droid-config-fp3` | `master` (18.1-era, de FP3-HW-specifikus) | sparse overlay, audio, usb-moded, patterns | klónozva `hadk22/hybris/droid-configs`-ba; 22.2-n **változtatás nélkül épült** |
| └ droid-configs-device (dcd) | `mer-hybris/droid-hal-configs` (submodule) | `c8280ec` (a fenti repo pinje) | közös config template | — (elég volt a régi pin) |
| **droid-hal-version** | `mer-hybris/droid-hal-version` | `master` | SSU verzió/repo csomag | spec a template-ből instanciálva |

---

## Saját módosítások (porter-patch-ek) — mit, hol, miért

### 1. Kernel defconfig — Sailfish mer-kernel-check kötelező opciók
**Fájl:** `hadk22/kernel/fairphone/sdm632/arch/arm64/configs/lineageos_FP3_defconfig` (backup `.bak.preSF`)
A lineage-22.2 FP3 kernel (4.9) ugyanazokat a Sailfish-opciókat hiányolta, mint a 18.1:
`CONFIG_VT=y`, `NET_L3_MASTER_DEV=y`, `SYSVIPC=y`, `DEVTMPFS=y` + `DEVTMPFS_MOUNT=y`, `FHANDLE=y`,
`CONFIG_DUMMY` **off** (a check `n`-t kér). **Miért:** systemd/connman/Sailfish userland igényli.

### 2. mer-kernel-check — QTAGUID opcionálissá
**Fájl:** `hadk22/hybris/mer-kernel-check/mer_verify_kernel_config:332` (backup `.bak.qtaguid`)
`CONFIG_NETFILTER_XT_MATCH_QTAGUID y,m,<=4.13.0` → `y,m,!` (opcionális).
**Miért:** a qtaguid symbol **nem létezik** a lineage-22.2 kernelben (Android Q után deprecated,
eBPF váltja; nincs Kconfig/forrás). A check 4.9-re kötelezőként kérte → elkerülhetetlen ERROR.
connman működik nélküle (csak per-uid iptables statisztika). (18.1-ben a kernel MÉG tartalmazta.)

### 3. vendor radio blobok — git-lfs pull
**Hol:** `hadk22/vendor/fairphone/FP3/radio/*.img` (12 db: modem, dsp, tz, aboot, sbl1, rpm, cmnlib*,
devcfg, keymaster, lksecapp, mdtp). **Miért:** a repo sync LFS-pointereket hagyott (133B ASCII) →
a kati `add-radio-file-sha1-checked` a pointer SHA1-ját látta → mismatch. Fix:
`git lfs pull --include "radio/*"` a vendor repóban (HABUILD, git-lfs 3.7.1).

### 4. droid-hal-fp3.spec — A15 root-mountpoint cruft eltávolítás
**Fájl:** `hadk22/rpm/droid-hal-fp3.spec` (létrehozva a dhd template-ből; `%define device FP3`,
`rpm_device fp3`, `droid_target_aarch64 1`). Hozzáadva:
`%define custom_install_cmds rm -rf %{buildroot}/{adb_keys,bugreports,cache,d,product,sdcard,system_ext}`
**Miért:** az A15 root több mountpoint-stubot tartalmaz, amit a dhd `_remove_cruft` listája nem fed →
"Installed (but unpackaged)". Nem droid-hal tartalom (a 18.1 sem szállította). A `custom_install_cmds`
a dhd kanonikus install-hookja (`droid-hal-device.inc:1105`). (A `straggler_files` út zsákutca:
RPM makró nem tud újsort tartani, amit a `%files` egy-fájl/sor igényel.)

---

## Build-környezet recept (megosztható, a fő tanulság) — soong memória a 15.9G RAM-os gépen

Az A15 soong-analízis working set-je ~14G live → nem fér a 15.9G RAM-ba → swap-thrash → gépfagyás.
**Megoldó recept (mind kell):**
- **soong_build wrapper** (`hadk22/out/host/linux-x86/bin/soong_build` → `.real` + bash wrapper),
  mert a soong `env -i`-vel indít → a shell `GOMEMLIMIT` **nem jut el** hozzá. A wrapper az `env -i`
  UTÁN állít: `GOMEMLIMIT=20GiB` + `GOGC=300` + `GODEBUG=madvdontneed=1`. **A GOMEMLIMIT-et a
  live set FÖLÉ (20G) kell tenni**, NEM alá — különben folyamatos GC pásztázza a swap-backed heapet
  (22500 fault/s → 131/s). 
- **zram** (`/dev/zram0`, 14G, zstd, prio 100) + **SSD swap** (`/dev/sda5`, 32G, prio 10).
- `systemd-oomd` leállítva (memória-nyomásra ölne).
- **`setsid`-leválasztás** minden hosszú buildhez (a harness reapeli a sima háttér-taskokat).

> Live-USB tanulságok: device-nevek rebootnál átrendeződnek (lsblk!); SDK target sb2-regisztrációja
> elveszik reboot után → `regtarget.sh`; adb/fastboot újratelepítendő; `/tmp` nem perzisztens.

---

## Beépített referencia-portok / források (mások munkája, amire alapozunk)

- **mlehtima/droid-config-fp3** + **droid-config-fp4** — FP3/FP4 droid-config (HW-specifikus configok).
- **mer-hybris/hadk-faq** — droid-hal-version layout, spec-módosítási szabályok, gyakori hibák.
- **postmarketOS fp3** — működő HW configok, firmware-nevek, kernel patchek referenciája (audio/path-ok).
- A korábbi saját **hybris-18.1** munka (`hadk/`, `droid-hal-fp3/`, `sailfish-customizations.md`) — kernel-config
  és spec-minták.

---

## Állapot-jelölés (HADK lépések)

- [x] 1–4: SDK, Android tree, kernel, hybris-hal build ✅
- [x] 5: droid-hal-fp3 RPM-ek (9 db) ✅
- [x] 6: droid-config-fp3 RPM-ek (11 db) ✅
- [~] droid-hal-version-fp3 (épül)
- [ ] 7–8: patterns + image (mic) → flashelhető zip
- [ ] 9–10: flashelés + HW bringup

## Porter patch — libhybris duplicate-module (2026-06-28)
**Component:** libhybris (Android-side compat layers)
**Repos involved:**
- `external/libhybris` ← sailfishos-mirror/libhybris @ 02f9f62 (added to local_manifests for hybris-hal's libui_compat_layer). Renamed on-disk to `external/libhybris.android-bak`.
- `hybris/mw/libhybris/libhybris` ← MW wrapper clone (from build_packages.sh --mw), full libhybris source.
**Problem:** both trees are scanned by kati (renaming a dir inside $ANDROID_ROOT does NOT remove it from the Android module scan) → both define `libcamera_compat_layer` etc. → `base_rules.mk:300 already defined` abort during `make droidmedia`.
**Modification:** emptied the 6 leaf `Android.mk` under `hybris/mw/libhybris/libhybris/compat/{camera,hwc2,surface_flinger,ui,media,input}/` (content-only disable comments, paths preserved) so kati ignores the MW clone's Android modules. `external/libhybris.android-bak` remains the single Android-side libhybris.
**Why content-only:** moving/renaming/adding files changes soong's glob file-set → forces a full re-glob (cost ~2.5h on 15GB-RAM+swap here). Editing file *content* keeps the glob set identical → no re-glob.
**Follow-up:** manifest still lists `external/libhybris` (now absent) → reconcile before any `repo sync` to avoid a 3-way duplicate.

## droidmedia (Android-side media bridge) — built 2026-06-28
- **Repo/version:** external/droidmedia @ git-describe `0.20260508.2+5+g4183e95` (mer-hybris/droidmedia). RPM: `droidmedia-0.20260508.2+5+g4183e95-1.aarch64`.
- **Build:** HABUILD `make -j3 libdroidmedia libminisf minimediaservice minisfservice` (NOT `make droidmedia` — no such target on this version; it's a no-op). Compiled clean on hybris-22.2/A15 (Android.mk has API-35 branches).
- **Packed by:** `build_packages.sh --gg` → pack_source_droidmedia-localbuild.sh → droidmedia RPM + gst-droid.
- **FP3 device-case fix:** pack uses `out/target/product/$DEVICE` with DEVICE=fp3 (lowercase) but product dir is FP3 → added symlink `out/target/product/fp3 -> FP3`.

## hybris-patches (REQUIRED, was missing) — A15/GCC build fixes
**Repo:** mer-hybris/hybris-patches @ `hybris-22.2` (a manifest project; apply with `hybris-patches/apply-patches.sh` from $ANDROID_ROOT BEFORE extracting headers / building).
**Why it matters here:** the FP3 tree was built/extracted WITHOUT applying hybris-patches → droid-headers contained raw A15 bionic/NDK clang-isms that gcc 10.3.1 (Sailfish 5.0's compiler — there is NO newer Sailfish gcc) cannot parse. This caused the libhybris MW failures.
**The two relevant patches:**
- `bionic/0010-hybris-Workaround-build-issues-with-gcc.patch` — guards `android/versioning.h` `__BIONIC_AVAILABILITY`/`__INTRODUCED_IN`/etc behind `#ifndef DISABLED_FOR_HYBRIS_SUPPORT` (empty in #else). android-config.h defines `DISABLED_FOR_HYBRIS_SUPPORT`. Fixes "android-config.h... no" configure failure.
- `frameworks/native/0006-hybris-Fix-build-with-gcc.patch` — strips `: int32_t` from `enum ADataSpace` (data_space.h) and `enum AHardwareBufferStatus` (vndk/hardware_buffer.h); fixes native_window.h `__INTRODUCED_IN` usage. Fixes "expected identifier or '(' before ':'" in libhybris gralloc.c.
**Toolchain note:** Sailfish OS 5.0.0.62 (Tampella) ships gcc 10.3.1 (cross: aarch64-meego-linux-gnu-gcc-10.3.1). No Sailfish SDK has gcc 13+. Building A15 hybris with gcc REQUIRES these hybris-patches; do NOT pursue an SDK upgrade for a newer gcc.
**Lesson:** ALWAYS run `hybris-patches/apply-patches.sh` right after `repo sync`, before `make hybris-hal`. Skipping it is the root cause of the A15-header/gcc errors.
**Applied (2026-06-28, fast path):** patch 0006's 3 edits applied directly to the TARGET droid-headers (`sdk/targets/fairphone-fp3-aarch64/usr/include/droid-devel/droid-headers/{android/data_space.h, vndk/hardware_buffer.h, android/native_window.h}`) — `--mw` uses these without reinstalling droid-hal-fp3-devel, so no droid-hal rebuild needed. TODO for durability: mirror to SOURCE `hadk22/frameworks/native/...` (content-only, no re-glob) or run apply-patches.sh properly.
**Independent confirmation:** the UBports FP3 (Halium 9.0) port recipe lists `hybris-patches/apply-patches.sh --mb` as a mandatory post-`repo sync` step — same step, different distro. Confirms our root-cause diagnosis.

## Reference: existing FP3 community trees (NOT our build base; for hw-config reuse only)
No A15/hybris-22 FP3 Sailfish port exists anywhere (GitHub "fairphone fp3 sailfish droid" = 0; FairSail forum thread is political, no code). The closest prior art is the **UBports/Halium-9 (Android 9) FP3 port** by **luksus42**. We do NOT reuse its build system (A9 vs our A15), but its MSM8953/sdm632 hardware mapping is largely stable A9→A15, so pull from it during the droid-config / hw-settings phase instead of guessing:
- kernel: `github.com/luksus42/android_kernel_fairphone_sdm632` (defconfig, sensors)
- device: `github.com/luksus42/android_device_fairphone_FP3`
- vendor: `github.com/luksus42/proprietary_vendor_fairphone`
- manifest: `github.com/luksus42/halium-devices` (`manifests/fairphone_FP3.xml`, halium-9.0)
- AOSP device tree (LineageOS 16): `github.com/WeAreFairphone/android_device_fairphone_FP3`
**Modifications:** none yet (reference only). **Why:** sensor/display/audio mapping, udev rules, hw-settings.ini values.
