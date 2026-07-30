# Sailfish OS — Fairphone 3 (fp3) community port — AKCIÓTERV

> Megjegyzés: Ez a dokumentum a hivatalos HADK (Hardware Adaptation Development Kit)
> folyamatot követi. Hivatkozás: https://hadk.sailfishos.org
> Referencia port: github.com/mlehtima/droid-config-fp4 (Fairphone 4)
> A `> Megjegyzés:` blokkokat szabadon bővítsd a munka során tapasztaltakkal.

## Eszköz- és környezeti adatok

| Tulajdonság | Érték |
|---|---|
| Eszköz | Fairphone 3 (`fp3`) |
| SoC | Qualcomm Snapdragon 632 / **MSM8953** (`sdm632`) |
| GPU | Adreno 506 |
| Kernel forrás | github.com/FairphoneMirrors/android_kernel_fairphone_sdm632 |
| Android base | LineageOS (FP3) |
| Munkakönyvtár | `$FP3_ROOT/` |
| OS | Linux live USB (root **ephemeral**, reboot resetel!) |

> Megjegyzés: ⚠️ A live USB root partíciója minden reboot után visszaáll.
> MINDEN adat, SDK, repo, build kimenet a `/mnt/1TB/` perzisztens lemezre kerüljön.
> Ha bármi a home-ba vagy `/` alá települ, az elveszik.

### Konvenciók ebben a dokumentumban

- `- [ ]` = elvégzendő lépés (pipáld ki haladáskor)
- `$PLATFORM_SDK_ROOT` = `$FP3_ROOT/sdk` (példa)
- `$ANDROID_ROOT` = `$FP3_ROOT/hadk` (a HABUILD tree)
- `$VENDOR` = `fairphone`, `$DEVICE` = `fp3`
- A `HABUILD_SDK [...]` prompt a habuild chrootot jelöli; a `PLATFORM_SDK $` a platform SDK-t.

---

## 0. Előkészületek és környezet

**Nehézség: Alacsony · Kockázat: Közepes (live USB adatvesztés)**

- [x] Ellenőrizd, hogy a `/mnt/1T` fel van csatolva és írható — OK (ext4, rw)
- [x] Legalább ~200 GB szabad hely a `/mnt/1T`-n — OK (**851 GB szabad** a 908 GB-ból)
- [x] Alap eszközök telepítése (curl wget git rsync bzip2 ca-certificates kpartx sudo lzop bc) — OK
- [x] Git globális azonosító beállítása (repo init kéri) — beállítva host-on ÉS a HABUILD chroot /root/.gitconfig-ban
  ```bash
  git config --global user.name "lajoshazilg"
  git config --global user.email "lajoshazilg@gmail.com"
  ```
- [ ] Hozz létre egy `restore_env.sh` szkriptet, ami reboot után újratelepíti az apt csomagokat és exportálja a változókat
- [ ] Jegyezd fel a Sailfish OS célverziót (pl. `4.6.0.x`) — minden tarball/branch ehhez igazodik

> Megjegyzés: A célverziót rögzítsd és NE keverd a HADK PDF verziójával.
> Mindig az adott Sailfish kiadáshoz tartozó HADK-t használd.

### Környezeti változók (forrásold minden új shellben)

- [ ] Hozz létre `$FP3_ROOT/env.sh` fájlt:
  ```bash
  export VENDOR=fairphone
  export DEVICE=fp3
  export RELEASE=5.0.0.71                 # legfrissebb stable ("Tampella")
  export PORT_ARCH=aarch64                # FP3 = 64-bit ARM (MSM8953)
  export ANDROID_ROOT=$FP3_ROOT/hadk
  export PLATFORM_SDK_ROOT=$FP3_ROOT/sdk
  export HABUILD_SDK_ROOT=$FP3_ROOT/habuild
  export MER_ROOT=$FP3_ROOT/sdk
  # hybris manifest / Android base / kernel — mind lineage-18.1 (Android 11)
  export HYBRIS_MANIFEST_BRANCH=hybris-18.1
  export LINEAGE_BRANCH=lineage-18.1
  export KERNEL_BRANCH=lineage-18.1
  ```

> Megjegyzés: Döntési indoklás (2026-06 kutatás alapján):
> - **RELEASE=5.0.0.71**: ez a legfrissebb *stable* ("stop release", 2025-10-30).
>   Az 5.1.0.x "Pispala" még Early Access. Stabil alapról indulunk, később
>   az SSU `version --dup` paranccsal felhúzható EA-ra.
> - **hybris-18.1 / lineage-18.1 (Android 11)**: a HADK hivatalosan Android 11-ig
>   támogatott; az MSM8953-ra ez a legjobban kiérlelt baseport. A referencia
>   FP4 port (mlehtima/droid-config-fp4, ill. SailfishOS-for-the-fairphone-4)
>   szintén hybris-18.1 forkot használ. Az újabb hybris-20/21/22/23 még
>   éretlen general adaptation, MSM8953-ra felesleges kockázat.
> - **Kernel**: `LineageOS/android_kernel_fairphone_sdm632` @ **lineage-18.1**
>   (a FP3 device tree `kernel/fairphone/sdm632` alá húzza). A
>   `FairphoneMirrors/...sdm632` repo elavult (utolsó commit 2020), NE azt használd.
> - **Vendor blobok**: `TheMuppets/proprietary_vendor_fairphone` @ lineage-18.1
>   (tartalmaz FP3-at). Ha hiányozna blob, az eszközről `adb pull`-lal pótolható.
> - **PORT_ARCH=aarch64**: a Snapdragon 632 64-bites; a Sailfish userland aarch64.

---

## 1. Platform SDK telepítés ✅ KÉSZ (2026-06-21)

**Nehézség: Alacsony · Kockázat: Alacsony**
**Függőség: 0. szakasz kész**

- [x] Töltsd le a legfrissebb Platform SDK chroot tarballt (242 MB)
  ```bash
  curl -O https://releases.sailfishos.org/sdk/installers/latest/Jolla-latest-SailfishOS_Platform_SDK_Chroot-i486.tar.bz2
  ```
- [x] Csomagold ki a tarballt KANONIKUS layoutba (`$PLATFORM_SDK_ROOT/sdks/sfossdk`)
  ```bash
  sudo mkdir -p $PLATFORM_SDK_ROOT/sdks/sfossdk
  sudo tar --numeric-owner -p -xjf Jolla-...-Chroot-i486.tar.bz2 -C $PLATFORM_SDK_ROOT/sdks/sfossdk
  ```
- [x] Állítsd be a `sdk` aliast a `~/.bashrc`-ben
  ```bash
  alias sdk='sudo $PLATFORM_SDK_ROOT/sdks/sfossdk/sdk-chroot'
  ```
- [x] Lépj be a Platform SDK-ba és ellenőrizd — sikeres (i686 chroot, Sailfish 4.6.0.13)
- [x] Bent: `sudo zypper ref` lefutott + `android-tools-hadk kmod createrepo_c` telepítve
- [ ] (opcionális) teljes `sudo zypper up` a chrootban — még nem futott

> Megjegyzés (2026-06-21, TÉNYLEGES eredmények):
> - URL: https://releases.sailfishos.org/sdk/installers/latest/Jolla-latest-SailfishOS_Platform_SDK_Chroot-i486.tar.bz2
>   (a docs.sailfishos.org/Tools/Platform_SDK/Installation/ adta meg, "Quick start").
> - **Platform SDK chroot verzió: Sailfish OS 4.6.0.13 (Sauna)** (toolchain).
> - **FONTOS layout-tanulság:** a `sdk-chroot` ELVÁRJA, hogy a SDK a `<bázis>/sdks/<név>/`
>   alatt legyen (a script ellenőrzi: `basename(dirname(sdkroot)) == "sdks"`). Ezért NEM
>   a `$PLATFORM_SDK_ROOT` gyökerébe, hanem `$PLATFORM_SDK_ROOT/sdks/sfossdk/`-ba került.
>   A `targets/` és `toolings/` könyvtárakat az első belépéskor a script automatikusan
>   létrehozta `$PLATFORM_SDK_ROOT` alatt.
> - Belépés: `sudo $PLATFORM_SDK_ROOT/sdks/sfossdk/sdk-chroot`
> - `android-tools-hadk` adja az `ubu-chroot` parancsot (HABUILD belépéshez).
> - A "Failed to create bus connection" / machine-id warningok ártalmatlanok (live USB).

---

## 2. HABUILD SDK (Ubuntu chroot) telepítés ✅ KÉSZ (2026-06-21)

**Nehézség: Közepes · Kockázat: Alacsony**
**Függőség: 1. szakasz kész (a HABUILD-be a Platform SDK-ból lépünk be)**

- [x] Töltsd le a HABUILD (Ubuntu 20.04 focal) chroot tarballt (423 MB)
  ```bash
  TARBALL=ubuntu-focal-20210531-android-rootfs.tar.bz2
  curl -O https://releases.sailfishos.org/ubu/$TARBALL
  ```
- [x] Csomagold ki a HABUILD chrootot `$PLATFORM_SDK_ROOT/sdks/ubuntu`-ba (numeric-owner)
  ```bash
  sudo mkdir -p $PLATFORM_SDK_ROOT/sdks/ubuntu
  sudo tar --numeric-owner -xjf $TARBALL -C $PLATFORM_SDK_ROOT/sdks/ubuntu
  ```
- [x] Állítsd be a `habuild` belépő aliast (`ubu-chroot`)
- [x] Lépj be a HABUILD SDK-ba és ellenőrizd — sikeres (Ubuntu 20.04.2 LTS focal, x86_64)
- [x] Build függőségek alapja megvan a chrootban: `git` és `java` (OpenJDK) jelen van
- [ ] (később, repo sync előtt) `repo` parancs beszerzése + további HADK függőségek

> Megjegyzés (2026-06-21, TÉNYLEGES eredmények):
> - URL: https://releases.sailfishos.org/ubu/ubuntu-focal-20210531-android-rootfs.tar.bz2
>   (OpenJDK 1.8+ változat; a HADK setupsdk fejezet adta meg). Régi alternatíva
>   OpenJDK 1.7-hez: `ubuntu-trusty-20180613-android-rootfs.tar.bz2`.
> - **A HABUILD chroot a Platform SDK ALÁ települ** (`$PLATFORM_SDK_ROOT/sdks/ubuntu`),
>   és a Platform SDK-n BELÜLRŐL lépünk be:
>   ```bash
>   sudo $PLATFORM_SDK_ROOT/sdks/sfossdk/sdk-chroot      # 1) Platform SDK
>   ubu-chroot -r /parentroot$PLATFORM_SDK_ROOT/sdks/ubuntu   # 2) HABUILD (bent)
>   ```
>   (A bind-mountolt `/parentroot` előtag kell, mert a `/mnt/1T` csak így látszik
>   a Platform SDK chrootból.)
> - Ártalmatlan warning belépéskor: `mount_bind /var/run/dbus: None of these exists`
>   és `cannot set terminal process group` — non-interaktív belépésnél normális.
> - A HABUILD-ben fordul az Android tree + kernel; a Platform SDK-ban a droid-hal RPM
>   és a `mic` image. Két külön chroot, két külön cél.

> Letöltött tarballok megőrizve: `$FP3_ROOT/sdk/Jolla-...-Chroot-i486.tar.bz2`
> és `$FP3_ROOT/downloads/ubuntu-focal-20210531-android-rootfs.tar.bz2`
> (reboot utáni újratelepítéshez nem kell újraletölteni — a chrootok a perzisztens
> lemezen vannak, csak a sdk-chroot bind-mountokat kell újra felhúzni belépéskor).

---

## 3. Android tree (repo sync) — LineageOS FP3 base

**Nehézség: Közepes · Kockázat: Közepes (manifest illeszkedés)**
**Függőség: 2. szakasz kész (HABUILD-ben dolgozunk)**

- [x] repo tool beszerzve: host-on `$FP3_ROOT/bin/repo` (launcher v2.54) ÉS a HABUILD chrootba `/usr/local/bin/repo`
- [x] Android root könyvtár létrehozva: `$FP3_ROOT/hadk`
- [x] HADK/Hybris manifest inicializálva (host-ról futtatva, működik)
  ```bash
  cd $FP3_ROOT/hadk
  repo init -u https://github.com/mer-hybris/android.git -b hybris-18.1 --depth=1
  ```
- [x] Helyi manifest létrehozva: `$FP3_ROOT/hadk/.repo/local_manifests/fp3.xml`
  > Repo nevek/branch-ek ELLENŐRIZVE (`git ls-remote ... lineage-18.1` mindháromra OK).
  > A device tree a `device/fairphone/FP3` (NAGYBETŰS), nem `fp3`. A kernelt a
  > `LineageOS/android_kernel_fairphone_sdm632` adja (NEM a FairphoneMirrors elavult).
  ```xml
  <?xml version="1.0" encoding="UTF-8"?>
  <manifest>
    <project path="device/fairphone/FP3"
             name="LineageOS/android_device_fairphone_FP3"
             revision="lineage-18.1" remote="github" />
    <project path="kernel/fairphone/sdm632"
             name="LineageOS/android_kernel_fairphone_sdm632"
             revision="lineage-18.1" remote="github" />
    <project path="vendor/fairphone"
             name="TheMuppets/proprietary_vendor_fairphone"
             revision="lineage-18.1" remote="github" />
  </manifest>
  ```
- [x] Fa szinkronizálása KÉSZ — 66 GB, log: `$FP3_ROOT/repo_sync.log`
  ```bash
  cd $FP3_ROOT/hadk
  repo sync -j4 --fetch-submodules --no-clone-bundle --no-tags 2>&1 | tee $FP3_ROOT/repo_sync.log
  ```
  > Lemez: 849 GB szabad a /mnt/1T-en a sync indulásakor; 66 GB felhasználva.
  > **Ismert nem-kritikus hiba:** `external/python/pybind11/tools/clang` submodule üres
  > (`wjakob/clang-cindex-python3` repo törölve a googlesource-ról). Ez az FP3 hybris
  > buildhez nem szükséges, biztonságosan figyelmen kívül hagyható.
  > Az Etar/calendar submodule lock (`File exists`) tranziens race condition volt, repo újrapróbálta.
- [x] Ellenőrizd, hogy a `device/`, `kernel/`, `vendor/` fák feltöltődtek — MIND OK:
  - `device/fairphone/FP3/` — BoardConfig.mk, device.mk, extract-files.sh stb.
  - `kernel/fairphone/sdm632/` — Makefile, Kconfig, teljes kernel tree
  - `vendor/fairphone/FP3/` — proprietary blobs, BoardConfigVendor.mk
- [ ] Szerezd be a proprietary blobokat (extract-files vagy vendor repo) és tedd a `vendor/fairphone/fp3` alá
- [ ] Alkalmazd a `device-info/fixup-mountpoints-fp3.sh` szkriptet a partíciós eltérések javítására
  ```bash
  # a meglévő szkript a repóban — futtasd a HADK fixup-mountpoints lépésnél
  ```

> Megjegyzés: A pontos LineageOS branch (18.1 vs 19.1) és a hybris manifest verzió
> KÖLCSÖNÖSEN illeszkedjen. A postmarketOS port és a LineageOS device tree jó forrás
> a helyes repo nevekhez/branchekhez. A `<...>` helyőrzőket töltsd ki valós értékkel.

---

## 4. Kernel konfiguráció és build

**Nehézség: Magas · Kockázat: Magas (mer-kernel-check, defconfig)**
**Függőség: 3. szakasz kész**

- [x] HABUILD-ben forrásold a build környezetet — OK (2026-06-21)
  - FONTOS: a lunch/product kódnév **NAGYBETŰS**: `breakfast FP3` (NEM `fp3`).
    A device tree `lineage_FP3` terméket definiál (`device/fairphone/FP3/`).
    A `breakfast fp3` "Can not locate config makefile for product lineage_fp3" hibát ad.
  - Belépés HABUILD-be host-ról (nested chroot): lásd `bin/habuild-run.sh` wrapper.
    A hadk a HABUILD-en belül itt látszik: `/parentroot/parentroot$FP3_ROOT/hadk`
  - breakfast FP3 OK: TARGET_PRODUCT=lineage_FP3, arm64, PLATFORM_VERSION=11, lineage-18.1
  ```bash
  cd $ANDROID_ROOT && source build/envsetup.sh
  breakfast FP3   # NAGYBETŰ!
  ```
- [x] Futtasd a Sailfish kernel config ellenőrzőt a defconfig-on — OK (2026-06-21)
  - defconfig neve: `lineageos_FP3_defconfig` (NEM fb3_defconfig)
  - kernel: 4.9.218, KERNEL_OBJ: `out/target/product/FP3/obj/KERNEL_OBJ`
  - `mer_verify_kernel_config` PERL szkript, nincs PATH-ban → közvetlenül futtatva:
  ```bash
  cd $ANDROID_ROOT
  perl hybris/mer-kernel-check/mer_verify_kernel_config \
    out/target/product/FP3/obj/KERNEL_OBJ/.config
  ```
- [x] Javítsd a hiányzó/hibás CONFIG kapcsolókat a defconfigban — 8/9 ERROR javítva (2026-06-21)
  - Módosított fájl: `kernel/fairphone/sdm632/arch/arm64/configs/lineageos_FP3_defconfig`
    (backup: `lineageos_FP3_defconfig.bak.*`)
  - [x] CONFIG_DUMMY=y → **kikapcsolva** (a check n-t követel)
  - [x] CONFIG_VT=y
  - [x] CONFIG_FHANDLE=y
  - [x] CONFIG_DEVTMPFS=y + CONFIG_DEVTMPFS_MOUNT=y
  - [x] CONFIG_SYSVIPC=y
  - [x] CONFIG_NET_L3_MASTER_DEV=y
  - [x] CONFIG_NLS_UTF8=y
  - [ ] CONFIG_NETFILTER_XT_MATCH_QTAGUID — **NEM javítható, nem blokkoló**:
    a szimbólum NEM létezik ebben a 4.9-es kernelben (Android Q után megszűnt,
    eBPF-alapú netstat váltja). A checker maga "deprecated/optional"-ként jelöli.
    Egyetlen maradék "ERROR", de boot-ot nem akadályozza.
  - Megjegyzés: a kötelező Sailfish opciók (CGROUPS, NAMESPACES, NET_NS, SECCOMP,
    NETFILTER, INOTIFY_USER, FANOTIFY, AUDIT) már a base defconfigban OK voltak.
- [x] Fordítsd a hybris-hal-t (ez fordítja a kernelt + ramdiskeket) — KÉSZ (2026-06-22)
  ```bash
  make -j3 hybris-hal   # log: habuild/hybris-hal.log  (-j3, NEM nproc — OOM miatt)
  ```
  > ⚠️ **OOM-tanulság (2026-06-21):** az első `make -j4 hybris-hal` futásnál a
  > `soong_build` (Java) OutOfMemory-t kapott és meghalt, mert a gépen **SWAP = 0** volt
  > (15 GB RAM önmagában kevés a soong + ninja párhuzamos terheléshez).
  >
  > **Megoldás — 8 GB swap fájl a perzisztens /mnt/1T lemezen:**
  > ```bash
  > sudo fallocate -l 8G /mnt/1TB/swapfile
  > sudo chmod 600 /mnt/1TB/swapfile
  > sudo mkswap /mnt/1TB/swapfile
  > sudo swapon /mnt/1TB/swapfile     # free -h: Swap 8.0Gi
  > ```
  > ⚠️ Live USB: reboot után a swap eltűnik (a fájl marad a /mnt/1T-n, csak
  > `swapon /mnt/1TB/swapfile` kell újra). Vedd fel a `restore_env.sh`-ba (0. szakasz).
  >
  > **Build újraindítás csökkentett párhuzamossággal + Java heap kap:**
  > ```bash
  > export _JAVA_OPTIONS="-Xmx6g"
  > make -j3 hybris-hal 2>&1 | tee habuild/hybris-hal.log
  > ```
  > Háttérben fut a `bin/habuild-run.sh` wrapperen keresztül. breakfast FP3 előtte
  > újra OK (TARGET_PRODUCT=lineage_FP3, arm64, lineage-18.1).
- [x] Sikeres build: `hybris-boot-lvm.img` (22 MB) és `sailfish.img001` (1.4 GB) megvannak (2026-06-22)
- [x] `mer-kernel-check` — 8/9 javítva, 1 nem blokkoló (QTAGUID, lásd fent)

> Megjegyzés: A "FATAL" hibák kötelezően javítandók, a "WARNING"-ok jellemzően tolerálhatók.
> Minden defconfig módosítást commitolj a kernel repóba, hogy reprodukálható legyen.

---

## 5. droid-hal-fp3 repo létrehozása és build

**Nehézség: Magas · Kockázat: Magas (csomagolási hibák, submodulok)**
**Függőség: 4. szakasz kész (hybris-hal lefordult)**

- [x] Klónozd a `droid-hal-device` build receptet (rpm/dhd) — KÉSZ
  - A dhd a `$ANDROID_ROOT/rpm/dhd`-be került (`git clone` a droid-hal-fp3-ből másolva).
  - Standalone másolat is van: `$FP3_ROOT/droid-hal-fp3/`.
- [x] `rpm/droid-hal-fp3.spec` létrehozva a dhd template alapján — KÉSZ
  - **FONTOS:** `%define device FP3` (NAGYBETŰ, mert a `breakfast FP3` az
    `out/target/product/FP3`-ba fordít, és a .inc a `%{device}`-t használja a product
    útvonalhoz). `%define rpm_device fp3` (kisbetű, ssu/csomag oldalon).
  - `%define droid_target_aarch64 1` (MSM8953, 64-bit).
- [x] SDK tooling + target telepítve (HADK előfeltétel a build_packages.sh-hoz) — KÉSZ
  - Tooling: `SailfishOS-5.0.0.62` (a 5.0.0.71 tarball nincs publikálva, a legközelebbi
    5.0.0.x a 5.0.0.62; forrás: releases.sailfishos.org/sdk/targets/).
  - Target: `fairphone-fp3-aarch64` (a build pontosan ezt a nevet várja:
    `$VENDOR-$DEVICE-$PORT_ARCH`).
  - **TANULSÁG:** `sdk-assistant ... create`-et MINDIG `--non-interactive` kapcsolóval
    futtasd, különben /dev/null stdin mellett végtelen `read(EOF)` ciklusban beragad.
  - Tarballok: `$FP3_ROOT/sdk-tarballs/{tooling,target}.tar.7z`.
- [x] `build_packages.sh --droid-hal` futtatása — KÉSZ (2026-06-22)
  ```bash
  # Platform SDK-ból:
  source /parentroot$FP3_ROOT/env.sh
  export ANDROID_ROOT=/parentroot$FP3_ROOT/hadk
  cd "$ANDROID_ROOT" && rpm/dhd/helpers/build_packages.sh --droid-hal
  ```
  - **HIBA #1 (megoldva):** `mer_verify_kernel_config` ERROR:
    `CONFIG_NETFILTER_XT_MATCH_QTAGUID is unset` (kötelező 4.9-es kernelen).
    Egy korábbi session már felvette a defconfigba
    (`kernel/fairphone/sdm632/arch/arm64/configs/lineageos_FP3_defconfig`),
    DE a kernel nem volt újrafordítva, így az `out/.../KERNEL_OBJ/.config` még a régi.
    MEGOLDÁS: kernel újrafordítás HABUILD-ben (KERNEL_OBJ/.config törlése + `make hybris-hal`),
    majd `build_packages.sh --droid-hal` újra.
  - Build log: `$FP3_ROOT/habuild/droid-hal-build.log`
  - Teljes RPM-build log: `$ANDROID_ROOT/droid-hal-fp3.log`
- [ ] Ellenőrizd a kimeneti RPM-eket
  ```bash
  ls -la $ANDROID_ROOT/droid-local-repo/fp3/
  ```
- [ ] Hozd létre a `droid-hal-version-fp3` csomagot (`build_packages.sh --version`)

> Megjegyzés: Ha hiányzó fájlokra panaszkodik a csomagolás (`%files` mismatch),
> az `*.spec` `%files` szakaszában kell felvenni/kizárni. Ez iteratív munka.
> Segédscriptek: `$FP3_ROOT/bin/{create-sdk-target,build-droid-hal,rebuild-kernel}.sh`

### Boot debug (2026-06-25)

- [x] Ramdisk SD kártya logging (boot-0..3 sikeresen logolt, régi init-tel)
- [x] system.mount + vendor.mount kézzel létrehozva (/dev/block/mmcblk0p30, p32)
- [x] developer_mode-configfs.ini létrehozva → 22b8:2e76 megjelenik usb-moded-ből
- [x] 28 service maszkolva (dsme, droid-hal-init, connman, stb.)
- [x] sailfish-debug.service + sdlog-dmesg.service a rootfsen
- [x] init-debug eltávolítva a rootfsből
- [x] .fs-resized létrehozva → LVM resize skip (root-mount gyors)

### Ramdisk USB RNDIS + inject loop (2026-06-25)

- [x] `setup_usb_rndis()` implementálva — g1 gadget rebuild RNDIS-re (rndis.usb0, 22b8:2e76)
- [x] `ramdisk_inject_loop()` implementálva — named pipe, watchdog keepalive, USB reconnect loop
- [x] 22b8:2e76 EGYSZER megjelent (PC uptime ~35785s) — g1-RNDIS MŰKÖDIk
- [x] Watchdog keepalive hozzáadva inject_loop-ba (echo 1 minden 10s, mindkét /dev/watchdog*)
- [x] USB reconnect loop: 5 mp-enként ellenőrzi az iface-t, ha eltűnt → setup_usb_rndis újra
- [x] telnetd dupla spawn bug javítva (killall telnetd USB reconnect előtt)

### Tanulságok és nyitott problémák

- **SD log hiány (boot-4+):** `-o rw,sync` vfat mount opció SIKERTELEN a 4.9-es kernelen
  → sdlog_init mount-ja meghiúsult, SDLOG_DIR="" → sem init.log, sem usb-debug.log nem keletkezett
  → Javítva: sima `mount -t vfat` (2026-06-25)
- **TWRP-ből nem olvasható az eMMC rootfs:** nincs lvm eszköz TWRP-ben
  → usb-debug.log (ami /rootfs/tmp-re megy) csak telnetből olvasható
- **Slot retry counter:** minden failed boot decrementálja → EDL → kell `fastboot set_active a`
- **rndis_host PC-n:** minden debug session elején kézzel kell:
  ```bash
  sudo modprobe rndis_host
  echo "22b8 2e76" | sudo tee /sys/bus/usb/drivers/rndis_host/new_id
  ```
- **UDC nem látszik:** ha setup_usb_rndis "NO UDC" logol → USB teljesen sötét marad
  → DWC3 (7000000.ssusb) kell hogy szerepeljen /sys/class/udc/-ban ~5s-on belül

### Jelenlegi állapot (2026-06-25 ~16:50 UTC)

- hybris-boot-sdlog.img flashelve: vfat fix + watchdog keepalive + USB reconnect loop + killall telnetd
- Telefon boot óta USB-sötét (~5 perc) → valószínűleg inject_loop fut, de UDC nem jelenik meg
- **KÖVETKEZŐ:** TWRP → SD log olvasás (boot-0 új init-tel?) → usb-debug.log diagnózis
- **KÖVETKEZŐ:** ha SD log van → meglátjuk mi az UDC állapot a setup_usb_rndis-ben
- **HOSSZÚTÁVÚ:** telnet 192.168.2.15:23 → `echo continue > /init-ctl/stdin` → systemd debug

---

## 6. droid-config-fp3 létrehozása (FP4 alapján)

**Nehézség: Magas · Kockázat: Közepes**
**Függőség: 5. szakasz (droid-hal RPM-ek megvannak)**

- [ ] Klónozd a referencia FP4 configot tanulmányozásra
  ```bash
  git clone https://github.com/mlehtima/droid-config-fp4.git $FP3_ROOT/reference/droid-config-fp4
  ```
- [ ] Hozd létre a `$ANDROID_ROOT/hybris/droid-configs` repót fp3-ra (másold az FP4 struktúrát)
- [ ] Igazítsd a `sparse/` overlay-t fp3-ra:
  - [ ] `sparse/etc/` rendszer konfigok (udev, systemd)
  - [ ] `sparse/usr/libexec/droid-hybris/` HW specifikus
  - [ ] hwcomposer / minimediaservice konfigok az Adreno 506-hoz
- [ ] Igazítsd a `droid-configs.inc` / spec fájlt fp3-ra (csomagnevek FP4 → FP3)
- [ ] Állítsd be az `usb-moded` konfigot (USB módok)
- [ ] Állítsd be az audio policy / pulseaudio configot (MSM8953 — FP4-től eltérő!)
- [ ] Állítsd be a `dconf`/settings overlay-t (kijelző, gombok)
- [ ] Buildeld a configot
  ```bash
  rpm/dhd/helpers/build_packages.sh --configs
  ```

> Megjegyzés: Az FP4 SoC (SD750G) ELTÉR a FP3 MSM8953-tól. A config NAGY részben átvehető,
> de az audio policy, a kernel-specifikus path-ok és a firmware nevek külön igazítást kérnek.
> A postmarketOS fp3 config szintén hasznos referencia a HW path-okhoz.

---

## 7. Patterns / packages összeállítása

**Nehézség: Közepes · Kockázat: Közepes**
**Függőség: 6. szakasz kész**

- [ ] Hozd létre a `patterns/jolla-hw-adaptation-fp3.yaml` patternt (FP4 alapján)
- [ ] Vedd fel a droid-hal-fp3, droid-config-fp3, droid-hal-version-fp3 csomagokat
- [ ] Vedd fel a szükséges middleware csomagokat (ofono-binder, pulseaudio-modules-droid, gst-droid, geoclue, qt5feedback-haptics, ngfd)
- [ ] WLAN/BT firmware csomagok felvétele
- [ ] Buildeld a patterns csomagot
  ```bash
  rpm/dhd/helpers/build_packages.sh --mw   # middleware ha kell
  rpm/dhd/helpers/process_patterns.sh
  ```
- [ ] Ellenőrizd, hogy a pattern feloldódik (`zypper` dry-run a target repón)

> Megjegyzés: A pattern hiányzó függősége miatt a `mic` (8. szakasz) bukik el leggyakrabban.
> Itt fogd meg a hiányzó csomagokat, ne az image build közben.

---

## 8. Sailfish OS image build (mic)

**Nehézség: Közepes · Kockázat: Közepes (dependency resolution)**
**Függőség: 7. szakasz kész**

- [ ] Platform SDK-ban futtasd az image build helper-t
  ```bash
  cd $ANDROID_ROOT
  rpm/dhd/helpers/build_packages.sh --mic
  ```
- [ ] VAGY kézzel `mic` paranccsal a `.ks` kickstart alapján
  ```bash
  sudo mic create fs --arch=$PORT_ARCH \
    --tokenmap=ARCH:$PORT_ARCH,RELEASE:$RELEASE,EXTRA_NAME:-fp3 \
    --record-pkgs=name,url --outdir=sfe-fp3 --pack-to=sfe-fp3.tar.bz2 \
    $ANDROID_ROOT/Jolla-@RELEASE@-fp3-@ARCH@.ks
  ```
- [ ] Oldd fel a dependency hibákat (hiányzó csomag → vissza 7. szakaszhoz)
- [ ] A kész image tarball ellenőrzése
  ```bash
  ls -lh $ANDROID_ROOT/sfe-fp3*.tar.bz2 $ANDROID_ROOT/Jolla-*fp3*.zip
  ```

> Megjegyzés: A `--record-pkgs` listából utólag visszanézhető, pontosan mi került be.
> Tárold el a sikeres `.ks` fájlt verziókövetve.

---

## 9. Flashelés és tesztelés

**Nehézség: Közepes · Kockázat: MAGAS (brick veszély, EDL)**
**Függőség: 8. szakasz (image kész) + LineageOS/recovery az eszközön**

- [ ] Bootloader unlock a Fairphone 3-on (developer mód, OEM unlock)
  > ⚠️ Az unlock TÖRLI az eszközt. Fairphone hivatalos unlock kód kérhető.
- [ ] Telepítsd a kompatibilis LineageOS base-t (a HADK ezt vendor base-ként várja)
- [ ] Bootolj recovery-be (TWRP/LineageOS recovery)
- [ ] Flasheld a Sailfish zip-et a recovery-ből (sideload)
  ```bash
  adb sideload Jolla-$RELEASE-fp3-$PORT_ARCH.zip
  ```
- [ ] Első boot — figyeld telnet/adb-n a hibákat
  ```bash
  # ha telnet debug (port 23 / 2323) elérhető:
  telnet 192.168.2.15 23
  ```
- [ ] Ellenőrizd a `journalctl` és `dmesg` kimenetet az első bootnál
- [ ] Ha nincs UI: ellenőrizd `systemctl --user status` és a `lipstick`/`droid-hal-init` szolgáltatásokat

> Megjegyzés: Készíts EDL (Emergency Download) mentési tervet az MSM8953-hoz
> (qboot / `firehose` programmer) BRICK esetére, MIELŐTT flashelsz.
> Mentsd le a gyári partíciókat (boot, system, persist) flashelés előtt.

---

## 10. HW komponensek tesztelése és javítása

**Nehézség: Magas · Kockázat: Közepes (komponensenként eltérő)**
**Függőség: 9. szakasz (eszköz bootol Sailfishre)**

> Megjegyzés: A postmarketOS fp3 port TELJES HW támogatással rendelkezik
> (display, GPU, kamera, audio, modem, WiFi, BT, GPS) — ez a legjobb referencia
> a működő konfigokhoz, firmware nevekhez és kernel patchekhez.

### 10.1 Display + GPU (Adreno 506)
- [ ] UI elindul, lipstick renderel
- [ ] Touch működik, gombok kalibrálva
- [ ] Fényerő szabályozás, képernyő ki/be (mce)
- [ ] Test: `EGL`/`hwcomposer` log tiszta-e (`/usr/libexec/droid-hybris/system/bin/test_hwcomposer`)

### 10.2 Audio
- [ ] Hangszóró kimenet (pulseaudio + droid module)
- [ ] Mikrofon felvétel
- [ ] Fülhallgató jack / útválasztás
- [ ] Hívás audio (modemmel együtt)
- [ ] Test: `pactl list` és `gst-launch` próba

### 10.3 WiFi
- [ ] WLAN bekapcsol, scan, csatlakozás (connman)
- [ ] firmware/nvram fájlok a helyükön
- [ ] Test: `connmanctl scan wifi`

### 10.4 Bluetooth
- [ ] BT bekapcsol, pairing
- [ ] BT audio (A2DP)
- [ ] Test: `bluetoothctl`

### 10.5 GPS
- [ ] geoclue/`gps-droid` fix
- [ ] Test: nyitott égbolt alatt fix idő mérése

### 10.6 Kamera
- [ ] Hátsó/elülső kamera előnézet
- [ ] Fotó/videó rögzítés (gst-droid camera)
- [ ] Test: kamera app + `gst-droid` pipeline

### 10.7 Modem (ofono / ofono-binder)
- [ ] SIM felismerés
- [ ] Hálózati regisztráció, jelerősség
- [ ] Hívás kezdeményezés/fogadás
- [ ] SMS küldés/fogadás
- [ ] Mobiladat (APN, RIL)
- [ ] Test: `/usr/share/ofono/scripts/list-modems`

### 10.8 Egyéb
- [ ] Szenzorok (gyorsulás, közelség, fény) — `sensorfwd`
- [ ] Rezgőmotor (ngfd / haptics)
- [ ] Akku töltöttség és töltés
- [ ] USB módok (MTP, fejlesztői)
- [ ] NFC (ha van)
- [ ] Ujjlenyomat olvasó

> Megjegyzés: A HW bringup sorrendje általában: display → input → WiFi → audio →
> modem → kamera → GPS → szenzorok. Komponensenként vesd össze a működő pmOS
> dmesg/konfig kimenetével a hibakeresésnél.

---

## Összefoglaló haladásmérő

- [x] 0. Előkészületek
- [x] 1. Platform SDK
- [x] 2. HABUILD SDK
- [x] 3. Android tree (repo sync)
- [x] 4. Kernel konfiguráció és build
- [~] 5. droid-hal-fp3 — boot debugging folyamatban (2026-06-25):
  - [x] developer_mode-configfs.ini → usb-moded 22b8:2e76 megjelenik
  - [x] 28 service maszkolva (droid-hal-init, DSME, connman, stb.)
  - [x] sdlog-dmesg.service + sailfish-debug.service → SD kártya logging
  - [x] Ramdisk: setup_usb_rndis() → RNDIS + telnet a boot legkorábbi fázisától (22b8:2e76 egyszer sikerült)
  - [x] Ramdisk: ramdisk_inject_loop() → watchdog keepalive + USB reconnect loop + named pipe
  - [x] vfat mount fix: `-o rw,sync` → sima mount (4.9 kernel nem támogatta a sync opciót)
  - [ ] SD log olvasása az új init-tel (boot-4 tartalmaz-e usb-debug.log-ot?)
  - [ ] Telnettel csatlakozni a ramdisk inject loop-hoz és azonosítani a crash okát
  - [ ] droid-config-fp3 létrehozása (HADK 6. lépés)
- [ ] 6. droid-config-fp3
- [ ] 7. Patterns / packages
- [ ] 8. Image build (mic)
- [ ] 9. Flashelés és tesztelés
- [ ] 10. HW bringup (display, audio, WiFi, BT, GPS, kamera, modem)

> Megjegyzés: A 4–6. szakaszok iteratívak — várhatóan többször vissza kell térni
> hozzájuk a HW bringup (10.) közben felmerülő hibák miatt.
