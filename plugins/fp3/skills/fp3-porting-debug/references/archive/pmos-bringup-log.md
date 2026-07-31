# postmarketOS mainline bring-up — dated execution log (2026-06-28 … 06-30)

> ⚠️ **AI-generated.** This page — and the code, device tree and tooling it
> describes — was written by Claude (Opus 5) working under the direction of
> Lajosházi, László Gergely, who reviewed every change and made or reviewed
> every measurement it rests on. Kernel commits carry `Co-authored-by: Claude`;
> anything prepared for the LKML carries `Assisted-by:` instead and never a
> `Signed-off-by` from the assistant, since only a human can certify the DCO.

> **Archive, not reference.** This is *what happened*, in order, with the dead
> ends kept — the record that answers "was this already tried?". It is not a
> description of how the device works today, and it is not a plan.
>
> **Where the current state lives:** `fp3-pmaports/docs/` — start at
> [`docs/kernel/README.md`](https://github.com/llg179org/fp3-pmaports/blob/main/docs/kernel/README.md),
> then the per-subsystem `docs/<subsystem>/` pages. **Method** — how to acquire
> ground truth, which instrument answers which question — is in the skill body
> and in `references/{safety,firmware-re,recovery,devmem-oracle-kernel}.md`.
>
> ☠️ **What was removed on 2026-07-30, and why.** The file opened with eight
> sections of status: a "hiteles feature-mátrix", a per-subsystem gap analysis
> with difficulty ratings, a feasibility estimate and a roadmap. Every one of
> them had gone false — the matrix still listed audio as "csak hangszóró;
> earpiece+mic NEM", charging as "nincs fuel-gauge/charger driver" and the
> sensors as missing, and put working voice calls at "~15-25%". All four are
> long done. They were deleted rather than updated: status does not belong in a
> skill, which is exactly the rot the "Where knowledge lives" rule exists to
> prevent. The dated log below is kept unchanged, because a dated log cannot go
> stale — it only ever claimed to describe the day it was written.

---

## 9. Végrehajtási napló (fact-log) — pmOS bring-up

> Élő napló. Cél: minden próbálkozás + tanulság rögzítése a megosztható tapasztalathoz.
> Részletes parancs-napló: `pmos-attempts.log`, `pmos-install.log` (mellette).

### 9.0 Környezet (2026-06-28, este)
- Host: **Ubuntu 26.04 LTS** live USB, `fp3` user, **passwordless sudo**. `apt` elérhető.
- **Lemez-felállás (FONTOS):** a root (`/dev/sda5`, 32G ext4) a live-USB overlay → **reboot-nál resetel**.
  Perzisztens: **`/dev/sdb2` → `/mnt/1TB`** (908G, 499G szabad). MINDEN ide megy.
  → pmbootstrap work-dir + pmaports + config mind `$FP3_PMOS/` alatt. A home (`~/.local`) NEM perzisztens.
- Eszköz USB-n: **`22b8:2e76 Motorola PCS FP3`**, két interfész: MTP + **ADB**. → TWRP **3.7.0_9-0**,
  `omni_FP3`, adb root-ként megy (recovery). Kernel a TWRP-ben: `4.9.112-perf+` (2020).
- **Partíciós tények (A/B eszköz, aktív slot `_a`):** `mmcblk0`, by-name: boot_a=p27/boot_b=p28,
  system_a=p30/system_b=p31, vendor_a=p32/p33, userdata=p62, dtbo_a=p23/p24, modem_a=p1, dsp_a=p13,
  vbmeta (lásd lk2nd). Bootloader **unlocked** (cél-eszköz).

### 9.1 Tooling telepítés
- `adb`/`fastboot` HIÁNYZOTT → `sudo apt-get install -y adb fastboot` (android-tools 34.0.5). OK.
- pmbootstrap host-dep: **`kpartx` kell** (`apt-get install kpartx multipath-tools dosfstools e2fsprogs`).

### 9.2 pmbootstrap setup — tanulságok
- **Forrás átköltözött:** a `gitlab.com/postmarketOS/pmbootstrap` CSAK redirect-stub. Helyes:
  **`https://gitlab.postmarketos.org/postmarketOS/pmbootstrap`** (v3.10.1).
- v3 nem-interaktív init recept:
  1. `-c <cfg> -w <work>` flag MINDEN hívásnál (különben home-ra ír). A `config` alparancs **nem hozza
     létre** a cfg-t → előbb kézzel megírni a `[pmbootstrap]` INI szekciót.
  2. **Gotcha:** a `-w` csak a work-dirt állítja; a **`aports` (pmaports) útvonalat KÜLÖN** kell, különben
     `~/.local/var/pmbootstrap/cache_git/pmaports`-ba (efemer home) klónoz. → `pmb config aports /mnt/1TB/...`.
  3. `init` interaktív, de a config-értékeket defaultként veszi → `yes '' | pmb init` elfogadja mind.
- **Választott config:** device=`fairphone-fp3`, ui=**phosh**, systemd=default(=igen), audio=pulseaudio,
  wifi=wpa_supplicant, usb=developer, tz=Europe/Budapest, locale=en_US.UTF-8, hostname/user=`fp3`.
- **install gotcha:** a user-jelszót interaktívan kéri, üres sort elutasít → **`install --password $FP3_PW`**
  (dummy jelszó; eszközön változtatható). `yes '' | pmb -y install --zap --password $FP3_PW`.

### 9.3 ÚJ TÉNYEK a pmaports-ból (frissebb mint a doc 2. szakasz wiki-snapshotja)
- **FP3 kategória most: `testing`** ("just boots → almost fully functioning"), NEM "community".
  (fp4=community, fp2/fp5/fp6=testing, fp1=downstream.) → a port instabilabb/mozgóbb a vártnál; reális elvárás.
- **deviceinfo (device-fairphone-fp3, pkgver 9, maint. Luca Weiss):**
  dtb=`qcom/sdm632-fairphone-fp3` (MAINLINE), arch aarch64, **drm=true**, flash=**fastboot**,
  generate_bootimg=true, vbmeta-partíció flash, `screen 1080x2160`, getty `ttyMSM0;115200`,
  partition_type=**msdos** (lk2nd még nem tud GPT-t al-partíciókhoz/SD-hez).
- **Függőségek (device APKBUILD):** kernel=**`linux-postmarketos-qcom-msm8953`** (community szint, msm8953-közös),
  bootloader=**`lk2nd-msm8953`**, A/B=**`qbootctl`**, modem: `rmtfs`+`msm-modem-uim-selection`,
  firmware: `firmware-fairphone-fp3-{adreno,adsp,audio,modem,venus,wcnss}` + `firmware-qcom-adreno-a530`,
  `soc-qcom-msm8953`, `mkbootimg`, `postmarketos-base`, `unl0kr-fbforcerefresh`.
  → a blobok (adsp/audio/modem/venus/wcnss/adreno) a pmOS firmware-csomagokban CSOMAGOLVA vannak.
- **Következmény a flash-tervhez:** boot.img → `boot` (aktív slot _a), rootfs → `userdata` (fastboot default),
  üres `vbmeta` a verifikáció kikapcsolásához. lk2nd a láncban. A `pmbootstrap flasher` ezt kezeli.

### 9.4 install hiba #1 — strict-zap kitörli a native chrootot (MEGoldva retry-jel)
- **Tünet:** `install` elhasalt a **(3/4) PREPARE INSTALL BLOCKDEVICE** lépésnél:
  `Command failed (exit code 125): (native) % busybox su pmos -c ... mkdir -p /home/pmos/rootfs`.
- **Valódi ok (a work/log.txt-ből):** `chroot: cannot change root directory to
  '.../chroot_native': no such directory`. A **native chroot eltűnt**.
- **Miért:** a rootfs csomagjai közül 3 elavult volt (gnome-desktop, networkmanager, postmarketos-base),
  ezeket az install build-elte (`cross-native2`/qemu), majd **`Zapping buildroots (strict mode by default)`**
  kitörölte a build-chrootokat — köztük a `chroot_native`-ot. A (3/4) lépés viszont a native chrootban
  csinálná a kép-mountot → nincs könyvtár → exit 125.
- **Tanulság / fix:** ha az install csomagot is buildel, a strict-zap után a native chroot hiányozhat.
  **Megoldás: futtasd újra az `install`-t** (`--zap` NÉLKÜL). Másodjára a 3 csomag már a lokális repóban van
  (43 apk a `work/packages`-ben) → nincs build → nincs zap → a `chroot_native` megmarad a (3/4)-ig.
  (Alternatíva lett volna `--lax`, de a retry biztosabb.)
- [FUT] install RETRY 22:48 — (1/4)+(2/4) gyorsan, build nélkül; (3/4)+(4/4) jön.

### 9.5 install SIKER + flash
- **install RETRY DONE (22:49:52):** (1/4)→(4/4) build nélkül; `fairphone-fp3.img` (3.0G, NEM split,
  msdos partíciós teljes-disk image; lk2nd fs-boot a rootfs `/boot`-jából indít).
- **Hiteles flash-recept (mentett wiki `~/Downloads/Fairphone 3 (fairphone-fp3) - postmarketOS Wiki.html`
  + pmbootstrap forrás egybevág):** lk2nd-es eszköznél **NEM flash-elünk külön boot/kernel partíciót!**
  1. `pmbootstrap flasher flash_lk2nd` → `fastboot flash boot_a lk2nd.img` (lk2nd a boot partícióra)
  2. `pmbootstrap flasher flash_rootfs --partition userdata` → `fastboot flash userdata fairphone-fp3.img`
  3. `fastboot reboot`
  - dtbo NEM kell (dtb a kernelhez fűzve, append_dtb=true); `fastboot flash dtbo` csak Android-visszaállításhoz.
  - **lk2nd menü:** unlocked-bootloader warning képernyőn **power 2×, majd tartsd Vol-Down**.
  - **fastboot belépés:** `adb reboot bootloader` TWRP-ből, vagy kikapcsolt tel.: Vol-Down + power/USB.
- **MONITOROZÁS TANULSÁG (a felhasználó jelezte):** a korábbi `until ! pgrep -f "<minta>"` figyelő
  **saját parancssorára illeszkedett** (a minta benne van) → SOHA nem jelzett, a hibát a felhasználó kapta el.
  FIX: ne pgrep-pel a folyamatra várj, hanem **a logfájlba írt feltétel/marker**-re
  (`until grep -q "FLASH_ROOTFS_EXIT=" log`), amit a parancs a `$?`-fel siker ÉS hiba esetén is kiír.
- **FP3 eszköz-tények (flash közben):** lk2nd → boot_a (342 KB OK); rootfs **4 sparse chunk** (~519MB/db)
  fastboot-on; userdata=mmcblk0p62 (~48.7G). fastboot product ellenőrzés: `product: FP3`.
- flash_rootfs (userdata) KÉSZ: 4 sparse chunk OK, EXIT=0.

### 9.6 COMPACT ÖSSZEFOGLALÓ + következő lépések (kontextus-tömörítéshez)
**Hol tartunk (2026-06-28 ~23:15):**
- pmOS install **KÉSZ** (phosh, no-FDE): `fairphone-fp3.img` 3.0G = **teljes-disk image** (msdos tábla +
  boot/root al-partíciók; NEM közvetlen ext4 — lk2nd a userdata al-partíciós táblájából fs-bootol).
- Flashelve: **lk2nd → boot_a** (ANDROID! image OK), **rootfs → userdata** (4 sparse chunk OK).
- **BLOKKOLÓ: nem bootol.** Tünet (user a kijelzőről): „**Fairphone powered by android → fastboot**" ~10-15 mp,
  lk2nd-képernyő NÉLKÜL. pstore üres → **hiba a kernel ELŐTT** (lk2nd/aboot szint).
- **A/B retry-count: most 5** (minden bukott boot -1; `set_active` NEM resetel; igazi reset = sikeres boot+qbootctl).
- Diag (TWRP, roncsolásmentes): boot_a=ANDROID! image (lk2nd cmdline); vbmeta=**gyári AVB0** (avbtool 1.3.0);
  userdata nem mountol ext4-ként (helyes: disk-image); boot_b üres; TWRP most RAM-ből fut.

**Két hipotézis a nem-bootra:**
- (A) gyári AVB elutasítja az aláíratlan lk2nd-t → FIX: `flash-pmos.sh vbmeta` (AVB verify OFF).
- (B) lk2nd elindul, de fs-boot/crash → mélyebb (lk2nd 22.0-r1 verzió, vagy rootfs-layout).
- ELLENÉRV (A)-ra: a hybris-korszakban aláíratlan hybris-boot ELINDULT (facts) → AVB talán nem blokkol.
- DÖNTŐ TESZT: vbmeta-disable + reboot. Boot→(A). Még mindig aboot-fastboot→(B), tovább lk2nd/rootfs irányba.

**Következő lépések (sorrend):**
1. `adb reboot bootloader` → `scripts/flash-pmos.sh vbmeta` → `boot-watch.sh from_fastboot 120 &` (user nézi a kijelzőt).
2. Ha (B): lk2nd-debug — lk2nd menü elérése (power 2× + Vol-Down a warningnál), lk2nd verzió/UART,
   esetleg újabb lk2nd build, vagy a rootfs disk-image partíció-layout ellenőrzése (mit vár a fs-boot).
3. Boot után: USB-net `$FP3_DEV_IP`, SSH `fp3/$FP3_PW`; feature-mátrix (kijelző/touch/GPU/WiFi/adat) validálása.

**ESZKÖZTÁR (új): `scripts/`** — `slot.sh`, `boot-watch.sh`, `flash-pmos.sh`, `twrp.sh`, `twrp-dd.sh`,
`diag.sh`, `sd-fsck.sh` (+ `fp3-env.sh`, `README.md`). Lásd a README táblázatot. `fastboot boot` az FP3-on
TILTOTT/megbízhatatlan → flash+reboot. boot_a=p27, boot_b=p28, userdata=p62.

### 9.7 ✅ MEGOLDVA — pmOS BOOTOL (2026-06-28 ~14:00, eszköz-idő)
**A HIÁNYZÓ LÁNCSZEM: a `dtbo` partíció flashelése volt.** A wiki ELSŐ telepítő-lépését
(`fastboot flash dtbo dtbo.img`, forrás: github.com/z3ntu/dtbo-fp3 v1.0, 190 byte, magic d7b7ab1e)
korábban kihagytam. A gyári Android dtbo-overlay-t az aboot ráhúzta az lk2nd boot-image-re →
inkompatibilis device-tree → kernel-előtti bukás vissza fastbootba, lk2nd-képernyő nélkül.

**A működő teljes szekvencia (sorrend számít):**
1. `fastboot flash dtbo dtbo.img`   (z3ntu/dtbo-fp3 — neutralizálja a gyári overlay-t)  ← EZ HIÁNYZOTT
2. lk2nd → boot_a   (`pmbootstrap flasher flash_lk2nd` / `flash-pmos.sh lk2nd`)
3. vbmeta (AVB disable) → vbmeta_a   (`flash-pmos.sh vbmeta`) — valószínűleg nem kötelező, de ártalmatlan
4. rootfs (disk-image) → userdata   (`flash-pmos.sh rootfs`, 4 sparse chunk)
5. `fastboot reboot`

**Tanulság a megosztáshoz:** a „Fairphone powered by android → fastboot, ~10-25 mp, lk2nd-képernyő
NÉLKÜL, pstore üres" tünet az MSM8953/FP3-on NEM AVB és NEM lk2nd-crash — hanem **hiányzó/rossz dtbo**.
A vbmeta-disable és a dtbo-flash közül a **dtbo** a tényleges fix (mindkettő rajta van most, de a sorrend-teszt
alapján a dtbo a döntő). Megfigyelés: a `boot-watch.sh` BACK_IN_FASTBOOT-ot jelzett, de a telefon közben
VÉGIG bootolt phoshig — a watcher korai/téves olvasat volt (a 25s ablak rövid volt a phosh-boothoz); a
**kijelző-megfigyelés** (user) volt a megbízható jel. → boot-watch ablakot növelni (≥90s a kernel+phoshhoz).

**Boot-kép sorrend (user a kijelzőről):** zöld háromszög (lk2nd splash) → „starting" → fekete →
homokóra (phosh load) → password → `$FP3_PW` unlock → **welcome**.

**FEATURE-MÁTRIX (SSH $FP3_DEV_IP, fp3/$FP3_PW, USB-net host=$FP3_HOST_IP):**
- OS: `postmarketOS edge`, kernel **`7.0.9-msm8953`** aarch64 (MAINLINE — EOL-mentes irány! ✅)
- cmdline: `console=ttyMSM0,115200 pmos_boot_uuid=… pmos_root_uuid=… quiet splash`
- **Kijelző**: DSI-1 `connected` (1a94000.dsi.0), backlight OK, phosh renderel ✅
- **Touch**: „Himax Touchscreen" (event*) — feloldás működött ✅
- **GPU/DRM**: `/dev/dri/card0` + `renderD128` (msm/freedreno render node), `phoc -v` GPU-compositor fut ✅
- **WiFi**: `wlan0` + `phy0` (rfkill: nem blokkolt) ✅ (asszociáció még nem tesztelve)
- **Bluetooth**: `hci0` (nem blokkolt) ✅; **NFC**: `nfc0` ✅
- **Modem**: ModemManager `Modem/0 [QUALCOMM]` detektálva ✅ (SIM/adat még nem tesztelve)
- **Akku**: power_supply node-ok ritkásak (csak typec látszik) — fuelgauge-driver ellenőrzendő ⚠️
- Compositor: `phoc` + `phosh` + `phosh-osk-stevia` futnak ✅

**Hátralévő finomítás (nem blokkoló):** akku-kapacitás/fuelgauge, WiFi-asszociáció, modem SIM+adat (APN),
hang/hívás, kamera; retry-count valódi reset megerősítése (sikeres boot után qbootctl persist_active_slot).

### 9.8 ⚡ TÖLTÉS — mainline-ban nincs charger driver; idle→TWRP workflow (2026-06-29)
**TÉNY:** pmOS edge (kernel 7.0.9-msm8953) alatt az EGYETLEN power_supply node a
`qcom,pmi632-typec` (Type-C port, `qcom_pmic_tcpm` driver): `USB_TYPE=[C] PD PD_PPS`, de
`CURRENT_NOW=0 CURRENT_MAX=0`, csak 5V default → **az akku NEM tölt**. Ok:
- A FP3 PMIC = **PMI632**; a mainline device-tree-ben a pmic@2 alatt NINCS charger/smb/qg/bms/fuel
  node (csak typec@1500, usb-vbus-regulator@1100, adc, vibrator, pon, rtc…).
- A kernelbe fordított `CONFIG_CHARGER_QCOM_SMBCHG` / `CONFIG_BATTERY_PMI8994_FG` MÁS PMIC-re
  (PMI8994) valók; nincs DT-binding a PMI632-höz. `dmesg`-ben semmi charger-init.
- → **Szoftveresen most NEM javítható.** Valódi fix = PMI632 charger(SMB)+QG fuelgauge mainline-port
  (DT-node + driver) — a [project-kernel-roadmap] melós része.

**MEGOLDÁS (user-jóváhagyott): idle → TWRP töltés slot-váltással.**
- TWRP (downstream 4.9, qpnp-smb5+qpnp-qg) **TÖLT**: TWRP-ből mérve
  `battery status=Charging present=1 chg_type=Fast capacity=100%` (Vnow≈4.39V, Inow≈120mA fenntartó).
- Slot-térkép: **boot_a = lk2nd→pmOS**, **boot_b = TWRP→töltés**. Toggle = `set_active a|b`.
- Új szkriptek (`scripts/`): `to-twrp.sh` (pmOS→bootloader→flash TWRP boot_b→set_active b→reboot;
  frissen flashel → a slot bootable marad), `to-pmos.sh` (set_active a→lk2nd→pmOS).
- pmOS-ből reboot bootloaderbe: `echo $FP3_PW | sudo -S reboot bootloader` (SSH-n TTY kell a sudóhoz!).
- TESZTELVE 2026-06-29 ~00:09: to-twrp lefutott, TWRP feljött (adb recovery), akku tölt, 100%.

**Apró tanulság:** SSH-n a `sudo dmesg` „A terminal is required to authenticate"-tel elhal → `echo PW|sudo -S`
vagy `ssh -t` kell.

### 9.9 CHARGER-PORT kutatás (PMI632 töltés mainline-ba) — 2026-06-29 éjszaka
**Cél:** pmOS-ben is töltsön az akku (user: „charger az első; ha nem lehet tölteni, nincs értelme a többinek").
Részletes dosszié: `charger-port/CHARGER-PORT-PMI632.md`. Staged kód: `charger-port/staging/`.

**Megállapítások (mind ellenőrizve forrásban/eszközön):**
- pmOS mainline kernelben NINCS FP3/PMI632 charger+fuelgauge driver (csak `qcom,pmi632-typec`).
- A charger driver `qcom_smbx.c` (`CONFIG_CHARGER_QCOM_SMB2`) LÉTEZIK, de csak SMB2 (pmi8998/pm660).
- PMI632 = SMB5-osztály. Az upstream „smb5 support" 11-patch sorozat hozza az SMB2/SMB5 generációkat +
  pm8150b/pm7250b-t — de PMI632-t NEM, és a sorozat **sem v7.0.9-r0-ban, sem torvalds master-ben nincs**.
- pmi632.dtsi-ben nincs charger/battery node; a configban rossz-PMIC driverek (SMBCHG, PMI8994_FG) vannak.
- Register-architektúra ismert (SMB_REG_OFFSET 0x100 SMB5-re; smb5 init_seq Type-C-vel; IRQ: bat-ov,
  usb-plugin, usbin-icl-change, wdog-bark). Downstream qpnp-smb5 bázis @1000 (chgr/dcdc/batif/usb/typec/misc).

**Port-útvonal (dossziéban kifejtve):** 11-patch smb5-sorozat forward-port v7.0.9-re + új `qcom,pmi632-charger`
variáns (gen=SMB5, pmi632 init_seq a downstreamből, Type-C-t a tcpm-re hagyva) + DTS charger+battery node
(KONZERVATÍV: 1A/4.4V/150mA term, monitored-battery-ből → biztonságos) + `CONFIG_CHARGER_QCOM_SMB2=y`.
SoC: QG-hez nincs mainline driver → kapacitás becsült (voltage/OCV), de a TÖLTÉS ettől még mehet.

**Miért nincs kész flashelhető fix az éjszakai futásban (őszinte):** (1) találgatott töltő-regisztert nem
flashelek Li-ion cellára; (2) a tiszta, alkalmazható 11-patch sorozat WebFetch-csel nem szerezhető
(lore=Anubis-block, mail-archive=HTML-mangling) → a driver-port flashelhető állapotba hozása külön menet
(b4/git-clone + downstream register-defines kell).

**ELKÉSZÜLT (biztonságos, kész a folytatáshoz):**
- `charger-port/CHARGER-PORT-PMI632.md` — teljes mérnöki dosszié + felügyelt teszt-terv + források.
- `charger-port/staging/pmi632-charger.dtsi` — DTS charger+battery draft (konzervatív paraméterek).
- `charger-port/staging/config-charger.fragment` — kernel-config delta.
- `scripts/charge-test.sh` — DUTY-CYCLE teszt-harness (user-protokoll: pmOS-burst→TWRP hő-ellenőrzés,
  hő-abort 43°C). KÉSZ, amint van flashelhető kernel.
- Karakterizáció (kód nélkül, biztonságos): pmOS merülés-mérés duty-cycle-lel (eredmény: charge-test.log).

**User-felhatalmazás:** „próbáld ki nélkülem; 10-30s pmOS futás után 1 perc TWRP (mutatja a hőmérsékletet)".
→ Ezt a `charge-test.sh` valósítja meg. Találgatott register-kód flashelése azonban kimarad (cella-biztonság);
csak forrásra alapozott charger-kódot tesztelek a duty-cycle-lel.

### 9.10 BUG+FIX: pmOS→fastboot flaky → to-twrp beragadt pmOS-be (2026-06-29)
**Tünet:** a `charge-test.sh` (és a `to-twrp.sh`) beragadt pmOS-be; a telefon pmOS-ben MERÜLT TWRP helyett.
**Gyökérok:** pmOS-ből a `reboot bootloader` NEM mindig ér el fastbootig — az lk2nd néha egyből visszabootol
pmOS-be (boot_a aktív). A `to-twrp.sh` csak EGYSZER próbálta (wait 60s) → „NEM jött fastboot" → feladta,
a telefon pmOS-ben maradt. A `charge-test` ezután garbage T0-t mért és végig pmOS-ben dwellt.
(TWRP→fastboot az `adb reboot bootloader`-rel viszont MEGBÍZHATÓ — to-pmos.sh ezért jó.)
**FIX:** `to-twrp.sh` most TÖBB PRÓBÁS (`get_fastboot`: 4×, 90s ablak, ha pmOS visszajött újra-rebootol).
Kézi mentés is ezzel működött (1. próbára fastboot). Telefon visszavíve TWRP-be: Full, 32.6°C, health Good.
**Tanulság:** minden pmOS→fastboot átmenetnél retry kell; TWRP-ben mindig ellenőrizni a tényleges állapotot
(adb get-state) mielőtt slot-műveletet adunk ki.

**9.10 FIX IGAZOLVA (2026-06-29 00:39):** javított `to-twrp.sh` pmOS→TWRP teszt SIKERES — 1. próbára
fastboot (14s), flash boot_b + set_active b + reboot → TWRP (status=Charging, 102%, 33.0°C, health Good).
Megjegyzés a teszteléshez: a `to-twrp.sh`-t HÁTTÉRBEN kell futtatni (foreground Bash 2-perc-timeout levágja
a többpróbás logikát). to-pmos+to-twrp együtt > 2 perc.

## 9.11 ⚡ CHARGER MŰKÖDIK pmOS-ben (2026-06-29 06:12) — a saját driver TÖLT

A 9.8-9.10-ben azonosított FŐ BLOKKOLÓ (pmOS-ben nincs charger) **MEGOLDVA**. A `qcom_smbx.c`-be
írt PMI632/SMB5-támogatás (lásd `charger-port/CHARGER-PORT-PMI632.md §8`) lefordult, sideload-dal
telepítve (manuális `apk add --allow-untrusted`, mert a pmbootstrap sideload kulcsos SSH-t vár; a
boot-deploy beépítette a módosított DTB-t + extlinux-ot a /boot-ba), reboot után:

```
/sys/class/power_supply/pmi632-charger:
  status=Charging  online=1  current_now=199mA  current_max=500mA(SDP)  usb_type=SDP
  health=Warm  model=200f000.spmi:pmic@2:charger@1000  manufacturer=Qualcomm
pmi632-thermal (akku-oldal) = 37°C, STABIL 75s alatt (nincs elszállás)
```

dmesg: a charger boot-kor egyszer `-EPROBE_DEFER` (várt a `qcom-spmi-adc5=m` modulra a usbin_v/i
IIO-csatornákhoz), majd sikeresen bekötött. Az `apk add` automatikusan deferred-probe-olt — helyes.

**Bizonyíték, hogy valódi**: current_now ~200mA FOLYIK az akkuba, status=Charging, az IIO-áramolvasás
működik. A 62%-os akku tölt. A host USB SDP-portja 500mA-t ad → ~200mA-t húz (AICL); fal-töltővel
(DCP) az 1A-es FCC-cap-ig menne (init_seq hardcode, konzervatív; downstream 2-2.7A).

**Megnyitott apró követők (nem blokkoló, nem veszélyes):**
- `health=Warm`: a JEITA/temp-decode "warm soft limit"-et jelez 37°C-on (valószínűleg a
  BATTERY_CHARGER_STATUS_2 dekódolás finomítandó). Warm = áramcsökkentés → konzervatív irány, nem veszély.
- Csak ~200mA SDP-ről: fal-töltővel gyorsabb (de akkor nincs USB-net/SSH). Sebesség-validáláshoz
  külön DCP-teszt kell.
- Fuel-gauge (qpnp-qg) NINCS portolva → pmOS-ben nincs akku-% (csak a charger current/status). QG-port
  = külön feladat, hogy a phosh akku-ikon %-ot mutasson.

**A duty-cycle discharge-teszt feleslegessé vált**: 200mA töltés sokkal enyhébb, mint az 5h 8-mag CPU-
terhelés, amit az akku 37°C-on túlélt. A charger biztonságos. Telefon most pmOS-ben tölt, tűzbiztos dobozban.

## 9.12 🔋 FUEL-GAUGE MŰKÖDIK — pmOS-ben van akku-% (2026-06-29 ~07:00)

A 9.11 első követője (nincs akku-%) **MEGOLDVA**. A PMI632 QG (Qualcomm Gauge) eleve **feszültség-alapú**
(nincs coulomb-counter), és a 4005 soros downstream `qpnp-qg.c` full-portja felesleges: a mainline
`power_supply` core **kész OCV→SoC interpolátort** ad (`power_supply_batinfo_ocv2cap`). Ez konceptuálisan
**ugyanaz az algoritmus**, töredék kóddal, nulla extra kockázattal (csak ADC-olvasás).

**Megvalósítás (3 fájl, mind hiteles downstream forrásból):**
- `sdm632-fairphone-fp3.dts` → `fp3_battery`-be **56 pontos `ocv-capacity-table-0`** a downstream Kayo
  profilból (`qg-batterydata-Kayo-3000mah-…-pmi632`, `pc-temp-v1-lut`, **25°C oszlop**), 100µV→µV
  konverzió. Szigorúan csökkenő. `ocv-capacity-celsius = <25>`.
- `pmi632.dtsi` → charger node `vbat` io-channel = `ADC5_VBAT_SNS`. (Megerősítve: az ADC5 `processed`
  értéke **µV** — `qcom_vadc_scale_hw_calib_volt` `result_uv`.)
- `qcom_smbx.c` → új **`pmi632-battery` power-supply (type=BATTERY)** — ez kell a UPower/phosh %-hoz
  (a charger type=USB, azt a UPower nem akku-ként nézi). Prop-ok: CAPACITY (VBAT→OCV-tábla),
  VOLTAGE_NOW, STATUS/HEALTH (a charger-ből), PRESENT, TECHNOLOGY=Li-ion. A gauge opcionális: csak ha
  van `vbat` csatorna ÉS `ocv_table[0]` (a pmi8998/pm660 variáns nem regisztrál akkut). Plug-eseménynél
  a batt_psy is `power_supply_changed`-et kap.

**Verifikálva (reboot után, töltés közben):**
```
/sys/class/power_supply/pmi632-battery:
  present=1  status=Charging  capacity=88→89→92→93%  voltage_now=4.26V  technology=Li-ion  health=Warm
UPower (= amit a phosh olvas):
  /org/.../battery_pmi632_battery  percentage=94%  energy 12.38/13.17 Wh  voltage 4.31V  state=fully-charged
```
A TWRP-ben utoljára 84% + azóta töltött → a 88-94% hihető. **A phosh akku-ikon mostantól %-ot mutat.**

**Ismert korlát (jelzett, nem blokkoló):** a pillanatnyi VBAT terhelés/töltés alatt megemelkedik →
a % töltéskor kissé felfelé olvas (89→92→93 a 200mA töltés feszültség-emelő hatása miatt). Pihenő
OCV-hez közelebbi érték kéne; jövőbeli finomítás = egyszerű IR-drop/ESR kompenzáció a charger
current_now-jából, és/vagy több hőmérséklet-oszlop a táblába. Egyelőre 1 db 25°C-os tábla.

Build rc=0 (~5 perc, ccache). Csomag: `linux-…7.0.9_p20260629065031-r0.apk`. Patch:
`charger-port/staging/implementation/pmi632-charger+fuelgauge.patch`. Verify: `scripts/fg-verify.sh`.

## 9.13 ✅ health=Warm BUG MEGOLDVA (2026-06-29 ~21:50) — a JEITA-regiszter is átköltözött SMB5-ön

A 9.11/9.12 utolsó nyitott követője. A spurious `health=Warm`-nak **KÉT** oka volt; a regmap-debugfs-szel
a telefonon kiolvasott TÉNYLEGES regiszterek (USID `0-02` = PMI632) a downstream `smb5-reg.h` ellen
földelték a gyökérokot:

1. **A temp-status regiszter ÁTKÖLTÖZÖTT** (nem csak a bitek tolódtak, ahogy elsőre véltem). MAINLINE
   (SMB2): JEITA a `BATTERY_CHARGER_STATUS_2` (0x07) alsó bitjeiben. SMB5/PMI632: a 0x07 ott **csak
   BAT_OV=BIT1**; a JEITA a `BATTERY_CHARGER_STATUS_7` (0x0D)-be került, **+2 bit-eltolással**
   (HOT_SOFT=BIT5, COLD_SOFT=BIT4, TOO_HOT=BIT3, TOO_COLD=BIT2). A mainline a rossz (0x07) regisztert
   dekódolta SMB2-szemantikával.
2. **`switch(stat)`** az egész regisztert hasonlította egyetlen bithez (latens mainline-bug) → `if (stat & BIT)` kell.

**Földelt bizonyíték (a fix erőssége):**
```
sudo grep -E "^100[7d]:" /sys/kernel/debug/regmap/0-02/registers
  1007 (STATUS_2) = 0x28  (= 0b0010_1000 → BIT3 SET)   ← naiv bit-teszt itt téves Warm-ot adna
  100d (STATUS_7) = 0x00  (a VALÓDI JEITA: nincs hiba) → helyesen Good
```
**Fix** (`qcom_smbx.c`): `smb_variant`-ba 3 mező — `ov_bit` (STATUS_2 BAT_OV: SMB2=BIT5 / SMB5=BIT1),
`temp_status_reg` (0x07 / 0x0D), `temp_status_shift` (0 / 2); `smb_get_prop_health` bit-tesztekkel a helyes
regiszterből, hard-limit elsőbbség; az OV-IRQ is `ov_bit`-et használ. SMB2-variánsok változatlanok.
Eredmény eszközön: `pmi632-battery/health=Good` és `pmi632-charger/health=Good` STATUS_2=0x28 mellett is.
Build rc=0. Csomag `linux-…7.0.9_p20260629073111-r0.apk`. Részletek: `charger-port/CHARGER-PORT-PMI632.md §11`.

## 9.14 ✅ MODEM/mobil-adat + ✅ unlock-blackout fix (2026-06-29 ~22:55)

**📱 MODEM/MOBIL-ADAT MŰKÖDIK (SIM betéve):** `mmcli -m 0` → `registered (home)`, LTE, jel 81%, **vodafone HU**,
`packet service: attached`. NM gsm-kapcsolat: `nmcli con add type gsm con-name vodafone-data gsm.apn
internet.vodafone.net connection.autoconnect no` → adat-iface `qmapmux0.0@rmnet_ipa0` (MSM8953 IPA/rmnet),
IP 100.64.x (CGNAT), `ping -I qmapmux0.0 8.8.8.8` = **3/3, 21-58ms** (routolt LTE). `autoconnect=no` (ne fogyasszon
meglepetésre). Csak `sim-pin2` lock (fixed-dialing, nem blokkol). remoteproc0 (MSS) running, `mba.mbn`+mpss betölt.

**🖥️ UNLOCK-BLACKOUT+HOMOKÓRA MEGOLDVA:** tünet = reboot utáni első kód-megadás után ~7s fekete képernyő + pár mp
homokóra. **Gyökérok:** `greetd → phrog greeter (saját phoc, user `greetd` UID 113) → phosh-session (másik phoc)`;
a két wlroots-kompozítor ~7s-ig EGYSZERRE futott, mindkettő a `DSI-1` DRM-mastert akarta → `phoc: connector DSI-1:
Atomic commit failed: Resource busy` → fekete, amíg a greeter user-session le nem állt (`Stopping User Manager for
UID 113` +5-7s a session-indulás után); utána gnome-session warm-up = homokóra. **Fix:** `/etc/phrog/
greetd-config.toml`-ban az `[initial_session]` aktiválása (`command="phosh-session"`, `user="fp3"`) → greetd
KÖZVETLENÜL phosh-t indít, ami a SAJÁT lockscreenjét UGYANABBAN a phoc-ban mutatja → nincs greeter→session
handoff → **unlock gyors, nincs blackout** (eszközön user-megerősítve; egyetlen phoc, UID-113 greeter eltűnt;
resource-busy 2 db jóindulatú indulási retryre csökkent). Backup: `greetd-config.toml.bak-prehandoff`.
**Diag-tanulságok:** (1) az RTC boot közben ugrál (Jun 27↔29) → az időbélyeg-korrelációnál figyelni; (2)
`journalctl -f > fájl` BLOKK-pufferel (~4KB) → live-capture helyett a perzisztens journalt olvasd visszamenőleg
(`journalctl -b --since/--until`); (3) `usb0` SSH a kijelző-stacktől függetlenül megy a lockscreennél is →
így a login-path távolról is biztonságosan piszkálható + visszaállítható. **Mellékhatás (ALACSONY prio, backlog-vég):**
a PIN-bekérő most a phosh egyszerű fekete-fehér lockscreenje a phrog színes UI helyett.

## 9.15 🔇 AUDIO: SLIMbus-fülhallgató fal BIZONYÍTVA + ✅ hangszóró helyreállítva (2026-06-29 ~22:00)

**Cél:** a legmélyebb fal — a WCD9326 (Tasha-lite) codec SLIMbuson keresztüli fülhallgató/in-call audiója,
ami azért néma, mert az ADSP SLIMbus-framere sosem indul.

**🔬 A FAL BIZONYÍTOTT JELLEGE (instrumentált build p20260629201302).** Debug-printeket tettem a
`qcom-ngd-ctrl.c`-be (minden RX-msg mt/mc; power_up state; ngd_status; QMI-eredmény). Döntő dmesg:
`QMI power request OK` → `ver=0x105 ngd_status=0x40c` → `waiting for capability` → `capability exchange
timed-out` **NULLA „DBG RX msg"-gel** = a framer semmit nem küld, a busz néma.

**Kemény bizonyítékkal kizárva (a teljes AP/Linux-oldal HELYES):**
- **QMI teljesen működik:** `select_instance(MASTER, inst=0)` + `power_request(active)` hibátlanul ack
  (különben nincs „SLIM controller Registered"). Az ADSP válaszol a 0x0301 SLIMBUS QMI-ra smd-edge/qrtr-en.
- **NGD base/verzió jó:** ver=0x105=v1.5.0; base=0x0c141000 (= ctrl->base + id*offset + (id-1)*size).
- **BAM pipe-offset=3** (`(0x40c & 0x3FC)>>2`), egyezik a mainline fix `dmas=<&slimbam 3>,<&4>`-gyel.
- **Pinek már lpass_slimbuson:** gpio70/71/72 TLMM ctl=0xc6 → mux=1 (a bootloader állította; /dev/mem
  python `mmap`-pal olvasva, mert busybox-ban NINCS `devmem` applet).
- **BAM DMA rx/tx lefoglalva** (slimbam=dma0, 31ch); a TX submitál (a „TX timed out" = HW nem nyugtáz =
  nincs framer-órajel).
- **Downstream AP-kód == mainline:** azonos QMI-szekvencia, azonos ADSP=MASTER mode (`qmi_init(dev,false)`),
  azonos regiszter-szekvencia. A downstream `check_framer_request` (QMI 0x0022) csak a külső-modem-SSR
  útban van, nem hiányzik.
- **FP3 lpass node azonos** a `msm8953-mainline`-éval (xo=RPM_SMD_XO_CLK_SRC, cx=VDDCX); az ADSP fut, a
  q6afe/APR audio-PD él (a MI2S-hang megy).

**PLATFORM-SZINTŰ TÉNY:** a `github.com/msm8953-mainline/linux` közös msm8953.dtsi-jében **NINCS slim-ngd
node**, egyetlen eszköz (mido/vince/tissot/daisy/potter/ocean) sem köt WCD9335/SLIMbust — csak GPIO
speaker-amp. **Senki nem oldotta meg mainline-on.** Az **Ubuntu Touch FP3** (Halium, downstream 4.9.218
kernel) viszont FULL működő audióval bír = a referencia.

**A fal egy mondatban:** az ADSP LPASS SLIMbus-mestere a QMI master+power-ack ellenére nem indítja a
framert (nulla buszórajel/capability), pedig ugyanaz az ADSP a q6afe/MI2S-t hajtja. Maradék (alacsony
konfidencia, ADSP-belső) leadek: (a) audio *user-PD* vs root-PD, amit a mainline qcom_q6v5_pas/pd-mapper
nem „start"-ol; (b) LPASS slimbus-core-clock; (c) firmware-eltérés. **Legnagyobb esélyű next step =
working downstream (UT/stock) `clk_summary` + slim-ngd dmesg trace diffje** — de az a teszt-telefon
felülírásával jár → **parkolva** (egyetlen játszós telefon, user-döntés kell a wipe-hoz).

**✅ HANGSZÓRÓ VISSZAÁLLÍTVA + TESZTELHETŐ (apk p20260629215419, flashelve).** A SLIMbus-átkötés miatt
korábban NULLA hang volt (kártya deferrált). Visszahozva, két réteg:
1. **DT** (`sdm632-fairphone-fp3.dts &sound_card`): `/delete-node/` a 2 slim dai-link; slim_msm
   `status="disabled"` (megőrizve, néma); és a DÖNTŐ `/delete-property/ audio-routing;` — a bázis msm8953
   sound-card örökölt routingja a már nem létező PM8953-widgetekre (`AMIC1`/`MIC BIAS External1`)
   hivatkozott → `snd_soc_dapm_add_routes` bukás → kártya sosem regisztrál.
2. **UCM/pipewire:** `Fairphone_3.conf` visszaállítva HiFi-only-ra (`.bak-precall`-ból); a korábbi
   call-érás `BootSequence`-em nem létező PM8953-kontrollokat csetelt (`RX1/RX2 Digital Volume`,
   `ADC1/ADC2 Volume`) → UCM import -2 → nincs sink. (`.bak-slimbus-era` mentve.)

**Igazolva:** `card 0 [F3] Fairphone 3`; pipewire sink `…HiFi__Speaker__sink` = default/unmute/70%; tiszta
660 Hz `speaker-test -D pulse` tónus lement a pulse→aw8898 (Quinary MI2S) úton; Amp Mode item#0='Speaker'.

**GOTCHA-k (audio-debughoz):** `alsaucm -c "Fairphone 3"` (teljes NÉV) működik; `-c F3` (kártya-id)
félrevezető -2-t ad; az ssh `fp3` user **uid=10000** (nem 1000); az SSH `systemctl --user`/`wpctl` MÁS
pipewire-példányt lát, mint a phosh-session → `pactl`/clean reboot a megbízható.

**Eszköz-állapot MOST:** pmOS fut, **hangszóró-hang működik és tesztelhető** a UI-ból. Fülhallgató/in-call/mic
= SLIMbus = parkolva a frontvonalon (DT/driver megőrizve: `slim_msm status="okay"` + 2 dai-link visszaadása
+ UCM VoiceCall visszatétele = folytatás). Memória: `project_fp3_audio_codec.md` — tetején a ★ DEFINITIVE
FRONTIER CHECKPOINT + speaker-restore részletek. Capture-script a downstream-trace-hez:
`scratchpad/downstream-capture.sh` (dmesg slim + `clk_summary` a kulcs-diff).

## 9.16 🔬 DOWNSTREAM-TRACE a SLIMbus-falhoz (folyamatban, 2026-06-29 ~23:00–)

A 9.15 fal feloldásához a working-oldali (downstream, működő framer) trace kell, hogy diffelhessük a
pmOS (mainline, törött) baseline ellen. User-döntés: **Stock A10 → Ubuntu Touch** (a UT FP3 audio
dok-igazoltan működik). A pmOS előbb teljesen lementve.

**(a) pmOS baseline rögzítve (a diff „törött" fele) + EGY FŐ HIPOTÉZIS LEZÁRVA:**
- `remoteproc2 adsp = running`, adsp.mbn betöltve, APR audio 4:3–4:b regisztrálva (ezért megy a MI2S
  hangszóró). `clk_summary`: minden LPASS_CLK_ID_* jelen (q6afe-provider), de **nincs külön SLIMbus-clock**
  a listában (ADSP-belső). `wcd-mclk` enable_cnt=0.
- **pd-mapper NEM a hiba (lezárva):** bár userspace-ben nincs telepítve, `CONFIG_QCOM_PD_MAPPER=y`
  (in-kernel), és a `qcom_pd_mapper.c` matchel `qcom,sdm632`→`sdm660_domains`, ami **tartalmazza az
  `adsp_audio_pd`-t** (`msm/adsp/audio_pd`/`avs/audio`). A NGD-driver `pdr_add_lookup("avs/audio",
  "msm/adsp/audio_pd")`-re vár (1665. sor), és ez fel is oldódik (ezért futott korábban a power_up a
  capability-ig). → a fal tényleg az ADSP-framer / audio-PD spawn szintjén van. Baseline:
  `/tmp/pmos-baseline` (clk_summary+dmesg) + `pmos-baseline.sh`.

**(b) Teljes, ellenőrzött pmOS-backup** (`$FP3_PMOS/pmos-backup-20260629/`): `boot_a.img`(lk2nd 64M),
`dtbo_a.img`(z3ntu 8M), `vbmeta_a.img`, `userdata-p62.img.gz`(1.5G, **GZIP_OK**, offline=konzisztens).
`LAYOUT.txt`: userdata p62 belső MBR = part1 /boot 487MiB + part2 root ext4 48.74GiB (teljes partícióra
nyújtva → fs-szintű trim nem segít, dd+gzip a biztonságos). **Backup-tanulság:** a `dd|pigz` az
`adb exec-out` alatt üres outputot ad (TWRP busybox pipe-bug); a host `pigz` itt nincs → **nyers
`adb exec-out dd` USB-n + host `gzip`** a működő recept (a 48.7G üres farok elnyelődik).

**(c) FÉLREÚT: a device-en LineageOS A15 van (nem stock A10).** `vendor_a` = `Fairphone/lineage_FP3/
FP3:15/BP1A.250505.005/eng…` — a korábbi hybris-munka A15 LineageOS bázisa system_a/vendor_a-n. A
build-fában van `out/.../FP3/boot.img` (A15 `eng.ubuntu:userdebug`). Megpróbáltam ezt boot_b helyett
**boot_a-ra** flashelni (a LineageOS slot a-n él) + set_active a → **3 próbára sem bootolt**
(`slot-unbootable:a=Yes`, retry=0; a plain build-boot.img nem-bootoló artifact; a hybris a
`hybris-boot.img`-et használta). **pmOS gyorsan visszaállítva** (boot_a=lk2nd + dtbo_a=z3ntu backupból
+ set_active a → pmOS feljött, a userdata érintetlen volt, 48G-restore NEM kellett). Tanulság: a
LineageOS A15 a SLOT A-n van (system_a/vendor_a) → bootoláshoz boot_a+matching dtbo+set_active a kell.

**(d) Stock A10 → UT, BIZTONSÁGOS flash-recept (folyamatban):**
- Image: hivatalos `FP3-REL-Q-3.A.0136-…-user-fastboot-factory.7z` (1.3G) + `ubports-installer_0.11.2`.
- A hivatalos `flash_fp3_factory.sh` **`RELOCK_BOOTLOADER="true"`** ← LANDMINE (a végén `oem lock`!).
  → saját `scripts/flash-a10.sh`: a hivatalos partíció-lista PONTOS mása (mindkét A/B slot:
  modem/sbl1/rpm/tz/devcfg/dsp/aboot/dtbo/vbmeta/boot/system/vendor/mdtp/lksecapp/cmnlib*/keymaster/
  product + userdata-wipe + erase config + `--set-active=a`), **relock NÉLKÜL**, nem-interaktívan, a
  bundled fastboottal, SHA256-ellenőrzés után (CHECKSUMS OK). **IMEI/EFS BIZTONSÁGOS:** a script a
  `modemst1/modemst2/fsg/fsc`-t SOHA nem érinti (csak `modem`=NON-HLOS.bin). A10-bootloader-downgrade
  A15-ről = a hivatalos recovery-út, FP3-on nincs anti-rollback brick.
- A10 flash felülírja a LineageOS A15-öt MINDKÉT sloton (újraépíthető hadk22-ből) + wipe userdata (mentve).
- Hátralévő: A10-boot → UBports Installer (GUI, user keze) → UT → `los-trace.sh` (adaptálva UT/sudo-ra) →
  pmOS-restore a backupból. UT-trükkök (fórum): wipe data TWRP-ből + első boot recovery-be, különben
  boot-logón fagy.

## 9.17 ✅✅ DOWNSTREAM-TRACE SIKERES — a working framer + a teljes hívás-UCM megvan (2026-06-30)

**A10 flash + UBports Installer → Ubuntu Touch fent** (Ubuntu 24.04, kernel **4.9.218-perf-ubuntutouch+**,
phablet/`sudo 1111`=root, Developer Mode→adb). **Hívás + earpiece + headset + töltés MIND MŰKÖDIK** =
a teljes working downstream referencia. Trace mind lementve: `$FP3_PMOS/pmos-backup-20260629/ut-trace/`.

**🎯 A KULCS-DIFF (pmOS mainline törött ↔ UT downstream működő):**
- `/sys/bus/slimbus/devices/`: pmOS=**ÜRES** ↔ UT=**`tasha-slim-pgd`+`tasha-slim-ifd`+`sb-1`+`msm-dai-slim`**
  (a WCD9326 enumerálva a buszon, **laddr 0xc8/0xc7** kiosztva → framer FENT).
- ADSP bring-up: pmOS=`qcom_q6v5_pas` (APR/MI2S megy, framer néma) ↔ UT=**`subsys-pil-tz`**:
  `adsp: loading…` → „Brought out of reset" → **„Power/Clock ready interrupt received"** → sysmon SSCTL QMI →
  `wcd-slim tasha-slim-pgd` probe → `wcd9335_bring_up v2.0`. (dmesg-audio.txt)
- **LEGKONKRÉTABB MAINLINE-FIX LEAD:** az ADSP-firmware ELTÉR — A10 working `adspso.bin` = **16 MB**
  (partíció-formátum) ↔ pmOS `adsp.mbn` = **9.5 MB** (mainline single-mbn). Gyanú: a pmOS adsp.mbn más
  build/PD-elrendezésű → az audio user-PD (SLIMbus-master) nem spawnol. Kísérlet: a működő A10 ADSP-fw
  átcsomagolása mainline-formátumba (mdt/bNN split) és pmOS-be töltése.
- `clk_summary` NINCS a 4.9-en (per-clock debugfs dirs); a clk-diff így nem elérhető — de a dmesg-szekvencia
  informatívabb. Regulátorok: `pm8953_l13` 3.125V mic-bias engedélyezve (codec-supply-k konfigurálva).

**🎤 A TELJES HÍVÁS-UCM RECEPT (élő hívás amixer-diff, idle→call; a natív earpiece/mic/headset audióhoz):**
- Kártya: `msm8953-tashalite-snd-card` (card0), codec WCD9326/tasha. PCM: `CS-Voice`, `VoiceMMode1`,
  `SLIMBUS_0/1 Hostless`, `VoLTE`. Mixer: 2896 kontroll, full dump = `amixer-contents.txt` (+idle/call/ear/hs).
- **EARPIECE (handset):** RX `SLIM_0_RX_Voice Mixer VoiceMMode1=on` → **SLIMBUS_0_RX** → `SLIM RX0 MUX=5` →
  `RX INT0_1 MIX1 INP0=5` → **RX INT0 INTERP=1 (EAR PA)**.
- **HEADSET (HPH):** RX `SLIM_6_RX_Voice…=on` → **SLIMBUS_6_RX** → `SLIM RX2/3 MUX=4` → **RX INT1/INT2
  (HPHL/HPHR)**. (earpiece↔headset váltás: csak az RX INT0 vs INT1/INT2 + SLIM_0 vs SLIM_6 RX flippel.)
- **MIC (mindkettő, beépített DMIC):** TX `VoiceMMode1_Tx Mixer SLIM_0_TX_MMode1=on` → **SLIMBUS_0_TX** ←
  `SLIM TX7/TX8 MUX=2` ← `DMIC MUX7=2, DMIC MUX8=3` (`ADC MUX7/8=0`). + `IIR0` sidetone (INP0 MUX=8, Band1-5),
  `GSM mode Enable=1`, `Sound Focus Voice Tx SLIMBUS_0` (fluence). Headset-mic NEM kellett (DMIC a default).
- Diffek: `call-routing-diff-EARPIECE.txt`, `-HEADSET.txt`; receptek: `mixer_paths_wcd9326.xml` (EAR PA gain stb.).

**🔋 TÖLTÉS UT-n (user kérte, ellenőrizve):** `battery status=Full 100% 4.357V`, qg fuel-gauge tisztán olvas
(downstream qpnp-smb5/qg) — a pmOS charger-portunk (9.11–9.13) ezt replikálja (ott becsült %, itt natív QG).

**pmOS-restore:** A10 felülírta a userdata-t → vissza a backupból (TWRP `gzip -dc userdata.gz | adb shell dd
of=p62`, binary-stdin md5-igazolt tiszta) + boot_a=lk2nd + dtbo_a=z3ntu + vbmeta_a=pmOS-disabled + set_active a.

## 9.18 🎯 SLIMbus GYÖKÉROK VÉGLEG AZONOSÍTVA (2026-06-30) — a framer nem keretez; az ADSP audio user-PD nem indul
A 9.15 falat pmOS-en **instrumentált `qcom-ngd-ctrl.c`-vel** pontosan bemértem (slim_msm `status="okay"` +
slim-rx/tx dai-linkek vissza, dtb-only deploy, reboot, dmesg-diff a 9.17 working-trace ellen).

**A 9.17 #1-lead (ADSP-firmware eltér 16MB vs 9.5MB) ELVETVE:** az A10 `adspso.bin` = ext4 **dsp** partíció
(csak DSP shared-libek), NEM a PIL-image. A valódi ADSP-image a `NON-HLOS.bin:/image/adsp.mdt+b00..b14`
≈9.96MB ≈ a pmOS `adsp.mbn` (mindössze 32+8 bájt eltérés 2 LOAD-szegmensben = más build, irreleváns). **Ugyanaz a fw.**
Az ADSP a pmOS-en **felbootol és fut** (`remote processor adsp is now up`), APR audio-svc él.

**A fal pontos mechanizmusa** (DBG-instrumentáció):
- NGD QMI-vezérlősík **MŰKÖDIK**: `select_inst(instance=0, ADSP=MASTER)` + `power_req(ACTIVE)` mindkettő ACK-elve
  (`QMI power request OK`, ver=0x105, ngd_status=0x40c).
- De az **ADSP SLIMbus-framer SOHA nem keretezi a buszt**: NULLA `DBG RX msg` (nincs REPORT_PRESENT/master
  capability) → `capability exchange timed-out` → az AP TX is `TX timed out:MC:0xd` → `wcd9335-slim …: Failed
  to get logical address`. A codec a DT-ből **enumerálódott** (`/sys/bus/slimbus/devices/217:1a0:0:0` + `:1:0`,
  `wcd9335-slim` bekötve), de laddr nélkül, `waiting_for_supplier` állapotban ragadt.
- **Trigger-lánc:** NGD `pdr_add_lookup("avs/audio","msm/adsp/audio_pd")`; PDR `SERVICE_STATE_UP` → `ngd_up_work`
  → power_up + capability. Az **in-kernel `qcom_pd_mapper` STATIKUSAN „audio_pd UP"-ot jelent** (sdm632→
  sdm660_domains), **függetlenül** attól, hogy az ADSP elindította-e a PD-t. A NGD elhiszi → **nem létező
  framerrel** próbál → timeout. **3 PDR-értesítés (~13/19/29s) után végleg feladja** (utolsó NGD-aktivitás 32s;
  a downstream framer ~27s-nál asszertál, a pmOS mégsem lát semmit → nem időzítés, hanem a framer sosem fut).

**KÖVETKEZTETÉS:** msm8996-on a framer az ADSP **root-PD**-jében van (mainline működik). sdm660/msm8953-on az
ADSP **audio user-PD**-jében — amit a mainline `qcom_q6v5_pas` **nem hoz fel** → a framer nem fut. Ezért nincs
egyetlen működő mainline msm8953 SLIMbus-audio sem. **Valódi fix = az ADSP audio user-PD elindítása** (q6v5_pas
user-PD támogatás / miért nem spawnolja az ADSP-root az audio_pd-t a pd-mapper domain-listájából).
**Kizárva mint NEM ok:** firmware, pd-mapper domain-config, DT codec-node, NGD-clock (msm8996 node-nak sincs),
slimbam BAM (bekötve), power_req encoding (resp_type_valid=0 helyes).

**Eszközök/állapot:** eval-artifactok: `$FP3_PMOS/pmos-backup-20260629/slimbus-resume/`. DT-editek:
`linux-fp3/.../sdm632-fairphone-fp3.dts` (jelenleg visszaállítva slim-disabled = hangszóró működik). Az enabled
dtb a telefonon `/boot/sdm632-fairphone-fp3.dtb.slimbus-enabled` néven; **dtb-only teszt-ciklus** reflash nélkül
(extlinux önállóan tölti a `/boot/…dtb`-t → fájlcsere + reboot). FIGYELEM: a slim dai-linkek bekapcsolva az EGÉSZ
hangkártyát buktatják (nincs aw8898-hangszóró), amíg a framer nem megy. Build: `./pmb build
--src=$FP3_PMOS/linux-fp3 linux-postmarketos-qcom-msm8953`. Scriptek: `scripts/deploy-dtb-and-trace.sh`.

> **MEGJEGYZÉS (2026-06-30):** a 9.18 „valódi fix = audio user-PD" következtetését a 9.19 alább
> **megcáfolja** — a framer az ADSP **root-PD**-ben van, nincs külön user-PD. A 9.18 a hipotézis-lánc
> egy állomása; a végső verdiktet a 9.22–9.23 adja. A teljes bizonyítási láncot lásd a 9.24
> összefoglaló táblában.

## 9.19 🔍 USER-PD ELMÉLET MEGCÁFOLVA (2026-06-30) — a framer a ROOT-PD-ben van, nincs külön user-PD
**Hipotézis (9.18-ból):** a SLIMbus-master egy ADSP **audio user-PD**-ben fut, amit a mainline `qcom_q6v5_pas`
nem hoz fel → ezért nem keretez. **Teszt:** a **downstream kernel-forrást a lemezen** auditáltam
(`hadk22/kernel/fairphone/sdm632/` — teljes FP3 msm-4.9 fa, incl. `drivers/slimbus/slim-msm{,-ngd}.c` + DT),
ahol a `grep` gyors (szemben a /sys-szel).
- **`grep -r 'audio_pd|userpd|user-pd|qcom,gpr|spawn-pd'` az EGÉSZ downstream DT-n = NULLA találat.** Nincs
  sehol audio_pd / user-PD / GPR node. A downstream ADSP = egyetlen `qcom,lpass@c200000` PIL (pas-id, fw="adsp").
  → **a framer az ADSP ROOT-jában fut, ugyanabból az egyetlen adsp.mbn-ből, amit a mainline is tölt.** Nincs
  user-PD, amit spawnolni kéne.
- **VERDIKT:** a 9.18 „audio user-PD spawn" terv NEM a fix (és nem is kell). Ez megválaszolja a felhasználó
  „nem cáfoltuk már meg a user-PD-t?" kérdését — IGEN, most végleg.
- **Mellék-cáfolatok ugyanitt:** (a) a downstream AP-oldali NGD-driver **NULLA clk-et enable-öl**
  (`grep clk_prepare/clk_get` = semmi), DT-node-jának nincs `clocks` → a clock-vote NEM az NGD dolga = halott
  szál. (b) BAM-msgq pipe-ek ÚJRA igazolva HW-ből: downstream `(NGD_reg & P_OFF_MASK)>>2` (RX) `+1` (TX) →
  `0x40c` → RX=3,TX=4 = pontosan a mi DT-nk `dmas=<&slimbam 3>,<&4>`. (c) downstream `ngd_slim_power_up` ==
  mainline (qmi_power_request(true) → NGD_STATUS → INT_EN+RX_MSGQ_CFG → setup → wait reconf). (d) **msm8996
  (ahol a mainline SLIMbus MŰKÖDIK) vs msm8953 power-diff:** msm8996 apr node-nak van
  `power-domains=<&gcc HLOS1_VOTE_LPASS_ADSP_GDSC>`; **msm8953 GCC-ben EGYÁLTALÁN NINCS LPASS/audio GDSC vagy
  clock** → a msm8953-on a LPASS power+clock RPM/ADSP-menedzselt, nem AP-votolható = nincs mit votolni, és a
  MI2S/hangszóró működik (a LPASS-audio fel VAN húzva). Valódi különbség, de NEM AP-fixelhető.
- **NET:** minden megfigyelhető AP-oldali faktor azonos a működő-msm8996-éval. A gap a **PIL/TrustZone-PAS
  ADSP-bring-up belsejében** van (AP-ról nem inspektálható). Forrás a lemezen: `hadk22/kernel/fairphone/sdm632`.

## 9.20 ❌ CHECK_FRAMER FIX MEGCÁFOLVA + a busz UNCLOCKED (2026-06-30, build p20260630083125)
**Hipotézis:** az AP egy még-nem-kész framert szólít meg; a downstream `CHECK_FRAMER_STATUS` QMI (0x0022) +
retry-loop hiányzik. **Teszt:** beépítettem `qcom_slim_qmi_check_framer_request()`-et + retry-loopot, és
**.ko-only hot-swappal** deployoltam (CONFIG_MODVERSIONS=n, vermagic egyezik → `slim-qcom-ngd-ctrl.ko` +
új dtb a /boot-ra, reflash nélkül; `scripts/deploy-ko-dtb-trace.sh`).
- **Eredmény (dmesg):** `QMI power request OK` → **`check_framer rc=0 after 0 tries`** (a framer AZONNAL
  „ready"-t jelent) → `ver=0x105 ngd_status=0x40c` → `NGD setup done, waiting for capability` →
  **`capability exchange timed-out`** → `TX timed out:MC:0xd,mt:0x2` → `Failed to get logical address`.
- **VERDIKT:** a hiányzó-CHECK_FRAMER hipotézis **MEGCÁFOLVA** — a framer-status az ELSŐ próbára SUCCESS, mégis
  néma a busz. Az AP NEM egy un-ready framert versenyzett le.
- **ÚJ KULCS-JEL — MINDKÉT irány döglött = a fizikai busz nincs clock-olva/keretezve.** RX: nulla `DBG RX msg`
  (a MASTER_CAPABILITY broadcast nem érkezik meg a BAM-RX DMA-n — a csatornák KIOSZTÓDTAK, nincs „Failed to
  request"). TX: `TX timed out:MC:0xd` = az AP kiírta a msg-et a TX BAM-pipe-ra, de SOHA nem kapott TX_MSG_SENT
  = a framer nem teszi a drótra = **nincs SLIMbus busz-clock a framertől.**
- **MÉRT TÉNY (clk_summary):** `bb_clk1` (RPM_SMD_BB_CLK1, 19.2MHz SLIMbus/codec-ref) **enable_count=0,
  prepare_count=0** (KI); `bi_tcxo`=4 (ADSP xo OK). De a downstream `slim@c140000` node-nak SINCS `clocks`
  property, a mainline qcom-ngd-ctrl.c-ben NULLA clk-kezelés → bb_clk1-et nem az NGD votolja. Nyitott kérdés
  maradt: a bb_clk1 a LPASS busz-clock-genbe megy-e (→ mindent magyarázna) vagy csak a codec-mclk (→ csak
  laddr UTÁN számít). Scriptek: `scripts/diag-adsp.sh` (clk_summary).

## 9.21 ✅ WORKING-FRAMER IPC-LOG A/B ÉLŐ UT-N (2026-06-30) — a QMI-réteg EKVIVALENS, nem ez a gap
Újra-flasheltem stock A10-et → a felhasználó Ubuntu Touch-ot telepített (Halium, **kernel 4.9.218-perf**),
sudo-passcode = `$FP3_PW` (lockscreen-PIN, NEM „phablet"). `scripts/ut-capture-framer.sh`. `/dev/mem` az
UT-n LETILTVA (CONFIG_DEVMEM off → nincs raw NGD-regdump; nem kritikus). Capture:
`$FP3_PMOS/pmos-backup-20260629/ut-framer-1003/`.
- **Working bring-up SORREND (dmesg + `/d/ipc_logging`):** `subsys-pil-tz lpass: adsp: Brought out of reset`
  (26.93) → `adsp: Power/Clock ready interrupt received`(26.96) → `sysmon-qmi: adsp SSCTL service up`(27.06) →
  QMI SvcId **301** (=SLIMbus): `TX MI:20`(SELECT_INSTANCE, ML=0x15)→RX ok, `TX MI:21`(POWER_REQ, ML=0xe)→RX ok
  (27.065–27.074) → **`sps:BAM 0xc104000 enabled: ver:0x19, 23 pipes` (27.090, a downstream `msm_sps` driver
  AZ ADSP-ready UTÁN)** → `c140000.slim: SLIM SAT: Rcvd master capability` + `capability exchange successful`
  (27.091) → `slimbus:1 laddr:0xc8`(27.143). Codec=tasha card0 regisztrál.
- **A QMI/indikációs réteg EKVIVALENS a mainline-nal — NEM ez a gap.** `Slimbus QMI NGD CB received event:2` =
  `QMI_SERVER_ARRIVE` (downstream) = mainline `qcom_slim_ngd_qmi_new_server`→`complete(&qmi_up)`. A POWER_REQ
  minden runtime-resume-on újra-megy (29.29/30.36/31.36…) — normális. select_inst/power_req MINDKÉT stacken sikeres.
- **VERDIKT (finomított fal):** a divergencia tisztán az **RX-oldali capability-fogadás**. Downstreamen a
  framer MASTER_CAPABILITY-je a BAM `0xc104000`-en **közvetlenül az után érkezik, hogy a SPS-driver enable-öli
  azt a BAM-ot** (ami az adsp Power/Clock-ready UTÁN történik). Mainline-on: QMI ok + check_framer ready + RX-BAM
  csatorna kiosztódik (nincs „Failed to request") + a TX is megpróbál (MC:0xd timeout) — de **NULLA `DBG RX msg`**
  = a capability sosem landol az RX-msgq-ban.

## 9.22 ✅✅ REGISZTER-SZINTŰ BIZONYÍTÉK (2026-06-30) — az AP/BAM oldal HELYES; a framer SOHA nem ír a buszra
Friss `pmb install` (build p20260630083125), pmOS bootol (7.0.9-msm8953). NGD + SLIMbus-BAM olvasás `/dev/mem`-en
(`scripts/regdump_pmos.py` + `poll_pipes.py`). BAM v1.7.0 regtábla a `drivers/dma/qcom/bam_dma.c`-ből.
> GOTCHA a flasheléshez: `pmb install` a usert stdin-en várja (`printf '$FP3_PW\n$FP3_PW\n'|pmb install`); a
> `flash-pmos.sh` NEM flashel dtbo → boot-loop „Fairphone powered by android"-on. FIX: a backup `dtbo_a.img` +
> `vbmeta_a` is kell, set-active a. Cycling-fastboot a nagyobb boot_a-n bukik → STABIL fastboot kell.
- **A BAM-CORE ÉL ÉS AZONOS A DOWNSTREAM-MEL:** `BAM_REVISION=0x..0419` (rev 0x19), `BAM_NUM_PIPES=0x17`=23 —
  pontosan a UT „ver:0x19, 23 pipes". Az ADSP a mainline-on is rendben felhúzza a BAM-ot.
- **AZ AP HELYESEN BEKÖTI AZ RX-PIPE-OT** (élőben elkapva egy újra-triggerelt power_up alatt, `poll_pipes.py`):
  power_up-kor `NGD_CFG 0→0x07` (ENABLE|RX_MSGQ_EN|TX_MSGQ_EN), `NGD_STATUS 0x40c→0x40d`, **pipe3(RX):
  P_CTRL 0→0x2a (enabled), P_DESC_FIFO_ADDR 0→0xfd8e0000 (valid DMA-fifo), P_FIFO_SIZES 0→0x7ff8,
  P_EVNT_REG→0x100.** → a „BAM-connect hiba" hipotézis **MEGCÁFOLVA** — az AP-oldali RX-msgq-pipe rendesen
  bekötve és élesítve.
- **A FRAMER SEMMIT NEM ÍR:** a `P_EVNT_REG` (a HW write-pointer, amit a framer/BAM léptet beérkező adatra) az
  init `0x100`-on marad, **sosem lép** → nulla adat → nulla `DBG RX msg` → capability-timeout. A TX-pipe(4) is
  timeoutol (MC:0xd). Mindkét irány döglött a buszon, holott adsp=ONLINE + QMI ok + check_framer=ready.
- **VERDIKT (kemény, regiszter-szintű):** az EGÉSZ AP/Linux/BAM/NGD/QMI stack HELYES. A msm8953 ADSP SLIMbus-
  framer egyszerűen nem keretezi/clock-olja a buszt a mainline `qcom_q6v5_pas` alatt, holott a downstream
  `subsys-pil-tz` alatt igen (UT: laddr:0xc8 ~1ms-mal a BAM-enable után). A maradék gap 100%-ban az ADSP
  bring-up belsejében van.

## 9.23 🎯 PDR/pd-mapper KIZÁRVA + a downstream QMI-szekvencia kibányászva (2026-06-30 resume #2)
**Hipotézis A (PDR/pd-mapper a kapu):** a NGD power_up-ot az audio_pd PDR-UP triggereli; ha a pd-mapper nem
hirdeti az audio_pd-t, nincs framer. **Teszt:** `CONFIG_QCOM_PD_MAPPER=y` (kernelbe fordítva); aux-devek
`qcom_common.pd-mapper.0/.2` BOUND a `qcom_pd_mapper`-hez; dynamic_debug (`scripts/pdr_trace.sh`).
- A **locator MŰKÖDIK:** `PDM: found msm/adsp/audio_pd / 74` + `PDM: service 'avs/audio' returning 1 domains`.
  Az msm8953+sdm632 BENNE van a pd_mapper of_match-ben (uncommitted local edit → sdm660_domains).
- **VERDIKT A:** a PDR feloldódik, **DE** a power_up valójában az **SSR AFTER_POWERUP**-ról indul (rproc-up,
  ~45ms-mal az „adsp is now up" után), NEM az audio_pd PDR-UP-ról; nulla servreg/pdr-debug fut az adsp-restartra.
  → a pd-mapper/PDR **NEM a kapu**. Kizárva.
- **Hipotézis B (rossz QMI-mode):** **Teszt:** `qcom_slim_qmi_init(ctrl,false)` → `req.mode=MASTER_V01(2)` =
  ADSP a framer. **VERDIKT B:** a mode HELYES, kizárva.
- **A DÖNTŐ LELET — a working downstream trace (`ut-framer-1003/ipc-slim.txt`) kibányászva:** a SvcId **301**
  forgalom a capability ELŐTT PONTOSAN ennyi: `MI:0x20 SELECT_INSTANCE`(TI:1,ML:0x15)→resp; `MI:0x21 POWER_REQ`
  (TI:2,ML:0xe)→resp; majd BAM 0xc104000 enable; majd **„Rcvd master capability" 1.3 ms-mal később**. A
  downstream **SOHA nem küld `MI:0x22` (CHECK_FRAMER)-t a 301-en** (a 0x22 csak a SvcId 31/34-en jelenik meg).
  → a mainline driverbe korábban (rossz feltevésen) bekerült check_framer-on-301-loop **SPEKULATÍV** (rc=0-t ad,
  de a working stack nem csinálja).
- **Időzítés-diff:** downstream NGD „up" 5.97s-nál, de select+power-t csak **27.06s**-nál csinál, amikor
  „QMI NGD CB event:2" tüzel (a SLIMbus QMI-service regisztrál = audio-PD framer kész). A mainline ~15s-nél,
  közvetlenül adsp-bootra (new_server) → valószínűleg leversenyzi a még-nem-keretező audio-PD-t.
- **Közösségi check:** a msm8953-mainline-on NINCS bizonyított SLIMbus+WCD9335 hang; a működő-audiós eszközök
  (xiaomi-vince #173) MI2S/analóg-kodek úton mennek; az FP3-speaker PR #137 ABANDONED. SLIMbus+WCD = upstream
  frontvonal. Források: github.com/msm8953-mainline/linux (issue #173/#137), linux-msm.github.io/mainline-status.
- **KÍSÉRLET ELVÉGEZVE (2026-06-30, build p20260630120047, .ko hot-swap):** a spekulatív check_framer-on-301-loop
  **eldobva** (`qcom_slim_ngd_power_up()`, qcom-ngd-ctrl.c — a függvény `__maybe_unused`-zal megtartva referenciának),
  modul újrafordítva (=m, MODVERSIONS off → `.ko` hot-swap reflash nélkül, `scripts/deploy-ko-dtb-trace.sh`),
  reboot + capture. **EREDMÉNY = VÁLTOZATLAN BUKÁS:** a power_up most egyenesen `QMI power request OK` →
  `ver=0x105 ngd_status=0x40c` → `NGD setup done` → **`capability exchange timed-out`** → `TX timed out:MC:0xd` →
  `wcd9335-slim: Failed to get logical address`, nincs soundcard. A 301-forgalom most PONTOSAN a downstream
  (SELECT_INSTANCE+POWER_REQ), a framer mégsem keretez. A capability+TX-timeout maga a bizonyíték, hogy a
  `P_EVNT` nem lépett (a framer semmit nem írt). Capture:
  `pmos-backup-20260629/drop-checkframer-1209/`.
- **VERDIKT H11 = ❌ — AZ AP-OLDALI VIZSGÁLAT VÉGLEG LEZÁRVA.** A check_framer eltávolítása semmit nem változtatott,
  mert sosem az volt a gond. Minden AP-oldali változó kimerítve (H1–H11). A maradék gap **100%-ban az ADSP PIL/PAS
  bring-up belsejében** van: a downstream `subsys-pil-tz` „Power/Clock ready interrupt received" handshake-je vs a
  mainline `qcom_q6v5_pas` PAS-SCM bring-up — ez TrustZone/ADSP-firmware-belső, AP-ról nem inspektálható. Valódi
  natív fix = vagy az ADSP-firmware/PIL reverse-engineering, vagy a subsys-pil-tz-ekvivalens ADSP-bring-up
  implementálása mainline q6v5_pas-ba — több-hetes, mainline-határ menti munka (NINCS működő mainline msm8953
  SLIMbus-audio sehol). **Earpiece/in-call/headset/mic ezen a fronton PARKOLVA**; a hangszóró (aw8898, Quinary
  MI2S) működik = az aktuálisan elérhető legjobb pmOS-audio.

## 9.24 📊 BIZONYÍTÁSI LÁNC — összefoglaló tábla (melyik feltevés melyik próbán dőlt el)
| # | Hipotézis (mi okozza a néma earpiece-t / SLIMbus-falat) | Próba | Verdikt |
|---|---|---|---|
| H1 | A PM8953 analóg WCD-kodek a fülhallgató útja | DAPM-widgetek On, mégis néma; aplay rc=0 (9.15) | ❌ a fülhallgató a **WCD9326-on SLIMbuson** van, nem PM8953-on |
| H2 | Hiányzó SLIMbus-NGD + wcd9335 DT/driver | DT+driver megírva → controller regisztrál, codec enumerál (`217:1a0:0/1`) | ✅ szükséges, de nem elég — `capability exchange timed-out` |
| H3 | `CONFIG_QCOM_PD_MAPPER` nincs beállítva | =m majd =y → pd-mapper BIND-ol boot-kor | ✅ bind javítva, de capability STILL timeout |
| H4 | A framer egy ADSP **audio user-PD**-ben fut, amit q6v5_pas nem hoz fel | downstream DT/forrás grep a lemezen (9.19) | ❌ **nincs user-PD**; a framer a ROOT-PD-ben van |
| H5 | Hiányzó eltérő/downstream ADSP-firmware (16MB vs 9.5MB) | NON-HLOS.bin adsp.mdt+bNN ≈ adsp.mbn (32+8 bájt diff) | ❌ **ugyanaz a fw** (9.18) |
| H6 | Hiányzó CHECK_FRAMER_STATUS QMI (0x0022) | beépítve+deploy → `check_framer rc=0 after 0 tries` (9.20) | ❌ framer azonnal „ready", busz mégis néma |
| H7 | Rossz BAM-msgq pipe-offset / RX-pipe nem kötődik be | `/dev/mem` regdump: P_CTRL=0x2a, valid DESC-fifo (9.22) | ❌ az AP **helyesen** beköti az RX-pipe-ot |
| H8 | `bb_clk1` (SLIMbus-ref clock) ki van kapcsolva | **force-vote az NGD-ből → bb_clk1 ON (enable_count=1, 19.2MHz); .ko+dtb hot-swap (9.26, build p20260630125436)** | ❌ **POZITÍV TESZT: clock BE, framer mégsem keretez** — a clock SZIMPTÓMA, nem ok |
| H9 | A pd-mapper/PDR-UP a power_up kapuja | dyndbg: power_up SSR-AFTER_POWERUP-ról indul, nem PDR-UP-ról (9.23) | ❌ PDR feloldódik, de NEM ez triggerel |
| H10 | Rossz QMI-mode (nem MASTER) | `qcom_slim_qmi_init(ctrl,false)`→MASTER_V01 (9.23) | ❌ a mode helyes |
| H11 | Spekulatív check_framer-on-301 zavar / rossz 301-szekvencia | check_framer eldobva → 301 = pontosan downstream; .ko hot-swap+reboot (9.23, build p20260630120047) | ❌ **VÁLTOZATLAN bukás** — capability+TX timeout marad; AP-oldal LEZÁRVA |
| **Σ** | **Hard verdikt (regiszter-szintű, 9.22):** az EGÉSZ AP/Linux/BAM/NGD/QMI stack HELYES; a `P_EVNT` sosem lép → a **msm8953 ADSP SLIMbus-framer nem keretezi a buszt `qcom_q6v5_pas` alatt** (downstream `subsys-pil-tz` alatt igen). A gap az ADSP PIL/PAS bring-up belsejében. | | |

**Eszközök (mind `scripts/` alatt):** `regdump_pmos.py`, `poll_pipes.py`, `poll2.py` (/dev/mem NGD+BAM),
`pdr_trace.sh` (PDR-dyndbg), `diag-adsp.sh` (clk/rproc/slimbus), `fdt_slim.py` (downstream FDT-parser),
`downstream-capture.sh`, `ut-capture-framer.sh` (working-trace), `deploy-ko-dtb-trace.sh` (.ko hot-swap).
Memória-tükör: `~/.claude/.../memory/project_fp3_audio_codec.md` (csillagozott blokkok).

## 9.25 🗺️ ADSP-FRONTVONAL FELTÉRKÉPEZVE (2026-06-30) — nincs AP-oldali delta; a gap ADSP-firmware-belső
Forrás-összevetés (build nélkül): a downstream `subsys-pil-tz` + a FP3 ADSP DT-node vs a mainline
`qcom_q6v5_pas` + `msm8996_adsp_resource`. Cél: van-e konkrét, a downstream által megtett ADSP-bring-up lépés,
amit a mainline kihagy (= a „több-hetes natív fix" feltevés ellenőrzése).
- **Kulcs-tény #1:** a downstream az FP3 ADSP-t a generikus **`subsys-pil-tz` (`qcom,pil-tz-generic`)** úton
  tölti, NEM a regiszter-pacskoló `pil-q6v5` úton (az csak az MSS-modemé). → **mindkét stack TZ-PAS módú**, a
  QDSP6 power/clock-szekvenciát a TrustZone csinálja, nem a Linux-driver.
- **Downstream ADSP-node (msm8953.dtsi `qcom,lpass@c200000`) votjai:** `pas-id=1`, fw="adsp", smem-id=423,
  ssctl=0x14; proxy-clockok: `xo` + 4 **crypto/SCM-clock** (core/iface/bus/src @80MHz — a PAS-**auth**hoz, NEM
  LPASS-audio); proxy-reg: **vdd_cx = pm8953_s2_level @ TURBO** (100mA); smp2p-handshake (err-ready/proxy-unvote/
  stop-ack/force-stop); proxy-timeout 10s; memory-region=adsp_fw_mem.
- **Mainline `msm8996_adsp_resource`:** `pas_id=1`, fw="adsp.mdt", `crash_reason_smem=423`, `ssctl_id=0x14`,
  sysmon="adsp", ssr="lpass", proxy_pd=["cx"]. + a driver: `pas->xo` clk_prepare_enable (DT: `xo`), crypto a
  qcom_scm-ben, **`dev_pm_genpd_set_performance_state(cx, INT_MAX)`** = cx TURBO-ekvivalens.
- **OLDALANKÉNTI VERDIKT — minden AP-oldali faktor EKVIVALENS:** mód (TZ-PAS) ✅, pas-id 1 ✅, fw (ugyanaz a
  blob) ✅, smem-423 ✅, ssctl-0x14 ✅, **xo** ✅, **crypto/auth-clock** ✅ (az ADSP bebootol → auth OK),
  **vdd_cx@TURBO≡cx@INT_MAX** ✅, smp2p-lifecycle ✅, bus-bw ✅. **Az ADSP MINDKÉT stacken teljesen online,
  APR/q6afe/MI2S fut** (hangszóró megy). Az EGYETLEN eltérő sor: a **SLIMbus-framer indulása** (downstream IGEN
  ~160ms-mal a reset után laddr 0xc8; mainline NEM).
- **FRONTVONAL-VERDIKT (végleges):** **NINCS AP-oldalról pótolható ADSP-bring-up lépés.** A korábbi
  „subsys-pil-tz extra lépésének portolása" feltevés **MEGCÁFOLVA** — a `cx@TURBO`/`xo`/crypto/smp2p/smem mind
  megvan mainline-on is, és az ADSP egyformán felbootol. A framer nem-indulása **kizárólag a futó ADSP-firmware
  futásidejű viselkedésében** van, amit NEM egyik AP-oldali clock/power/PAS-paraméter sem vezérel (mind egyezik).
  → a gap az **ADSP-firmware-belső** (build-/környezet-detekció, vagy egy a downstream audio-stack által átadott
  ADSP-oldali config), AP-ról driver-tweakkel nem nyúlható. **A natív SLIMbus-earpiece ezen a SoC-on nem
  AP-oldali fix kérdése** — ezért nincs egyetlen működő mainline msm8953 SLIMbus-audio sem. Earpiece/headset/mic
  VÉGLEG PARKOLVA a mainline-en; hangszóró (aw8898 Quinary MI2S) = az elérhető pmOS-audio.
- **Maradék (nagyon alacsony konfidencia, ha valaki tovább vinné):** (a) mainline q6afe SLIMBUS-AFE-port
  open-je tüzeli-e az ADSP framert (a downstream-evidencia ellene szól: a framer boot-kor, port-open nélkül
  indul); (b) ADSP-oldali ACDB/audio-topológia átadása (framer UTÁN töltődne → gyenge). Mindkettő ADSP-firmware
  RE-t igényelne. Forrás a lemezen: `hadk22/kernel/fairphone/sdm632/drivers/soc/qcom/subsys-pil-tz.c` +
  `.../arch/arm64/boot/dts/qcom/msm8953.dtsi` (`qcom,lpass@c200000`).

## 9.26 🧪 BB_CLK1 FORCE-VOTE KÍSÉRLET (2026-06-30, build p20260630125436) — a clock SZIMPTÓMA, nem ok
**Hipotézis (a 9.20-ból, H8):** a `bb_clk1` (RPM_SMD_BB_CLK1, 19.2 MHz SLIMbus-referencia) KI van kapcsolva, és
egy csirke-tojás miatt senki nem kapcsolja be időben (a codec votolná, de laddr nélkül nem probe-ol; a laddr-hoz
framer kell; a framerhez a clock) → ha az AP korán force-voteol, megtörhet a kör. **Egy(koncepciójú)
változtatás, két fájl:** (1) `qcom-ngd-ctrl.c` probe: `devm_clk_get_optional(dev,"slimbus_ref")` +
`clk_prepare_enable` (early, unconditional; + `#include <linux/clk.h>` — a mainline NGD-nek NULLA natív
clock-kezelése volt, ezt kellett pótolni); (2) DT `slim_msm` node: `clocks=<&rpmcc RPM_SMD_BB_CLK1>;
clock-names="slimbus_ref";`. Modul=m → `.ko`+dtb hot-swap, reboot, capture.
- **A vote SIKERES:** dmesg `DBG slimbus_ref (bb_clk1) force-enabled: yes`; `clk_summary` →
  **`bb_clk1  enable_count=1  prepare_count=1  19200000  consumer=c140000.slim-ngd  slimbus_ref`** (a 9.20-as
  `0/0`-ról). A 19.2 MHz referencia mostantól FUT, AP-ról hajtva.
- **EREDMÉNY = VÁLTOZATLAN BUKÁS:** `capability exchange timed-out` → `TX timed out:MC:0xd` →
  `Failed to get logical address`, nincs soundcard. A framer a bekapcsolt referencia-clock mellett SEM keretez.
- **VERDIKT H8 = ❌ POZITÍV TESZTTEL:** a `bb_clk1`-OFF **szimptóma volt, nem ok**. A SLIMbus-referencia-clock
  hiánya nem a kapu. Ez **élesen szétválasztja a (3) clock-követelményt a (4) ADSP-framer-init-triggertől:**
  a (3) most teljesül (bb_clk1 ON), a framer mégsem indul → **a (4) az EGYETLEN maradék hiányzó elem, és az
  NEM AP-votolható erőforrás.** Az ADSP a QMI-ACK + futó referencia-clock ellenére sem kezd keretezni.
- **Megerősíti a 9.21/§4-magyarázatot:** a hiányzó input nem clock/power/PAS-paraméter (mind megvan/teljesíthető),
  hanem az ADSP-firmware futásidejű **framer-init triggere** — a legvalószínűbben a downstream vendor-userspace
  (acdb/HAL/adsprpc) által tolt ADSP-config/parancs. A következő lépés tehát NEM újabb AP-vote, hanem a **működő
  rendszer megcsapolása** (teljes ipc_logging APR-diff a framer előtt; UT clock-állapot; vendor-userspace strace),
  hogy kiderüljön, pontosan milyen ADSP-bemenetet kell pmOS-en pótolni. Capture: `pmos-backup-20260629/bbclk1-1300/`.
  A telefon most ezt a build-et futtatja (bb_clk1 ON, diagnosztikai állapot, nincs soundcard).

## 9.27 🎯 A DÖNTŐ EMPIRIKUS LÉPÉS DEFINIÁLVA — APR-control-plane diff (pmOS-baseline kész)
A (4)-es trigger megtalálásához a működő (UT) és törött (pmOS) rendszer **ADSP-control-plane**-jét kell diffelni
a framer-indulás körül. Az interfész-megcsapolás módszertana (teljes lista a script-fejlécben):
- **UT-oldal (működő):** a downstream `/d/ipc_logging/` buffer-ek. KULCS: az `ipc_logging-list.txt` igazolja, hogy
  UT-n LÉTEZIK **`apr`** csatorna (+ `ipc_rtr_q6_ipcrtr`, `smem`, `smsm`, `smp2p`, `sps_bam_0x...c104000_*`), de a
  korábbi capture (`ut-framer-1003/`) **csak a `c140000.slim` csatornát fogta**, az `apr`-t nem. → a döntő adat
  (mit kap az ADSP APR-en a framer ELŐTT) **kapturálható**, csak eddig nem volt elkapva. `ut-capture-framer.sh`
  [1b] szakasz FRISSÍTVE: most az apr/q6-router/smd/smem/smsm/smp2p + c104000 BAM-pipe csatornákat is menti.
- **pmOS-oldal (törött) BASELINE (mérve, build p20260630125436):** mainline-on **NINCS `ipc_logging`**
  (downstream-only feature) → a pmOS-felet ftrace/dynamic_debug-gal kell csapolni (apr/q6afe/q6adm/q6core).
  Az APR fent: aprsvc 4:3..4:b (q6core/afe/asm/adm/voice mind regisztrálva), `/d/asoc/{dais,components}` megvan,
  a teljes q6-driverkészlet betöltve — **de egyetlen AFE-port sincs elindítva** (a SLIMBUS-DAI-k idle-ben, a codec
  deferred). Tehát: a teljes APR-stack jelen van, de **semmi nem utasítja az ADSP-t a SLIMbus felhozására**.
- **HIPOTÉZIS, amit a diff eldönt:** a downstream a capability ELŐTT küld egy ADSP-parancsot (q6afe/q6adm/q6core
  AFE/ADM/CORE), ami a framert indítja; a mainline q6afe semmit nem küld boot-kor (port-open csak PCM-re). HA a
  diff ilyen parancsot mutat → kernel-oldalról (q6afe boot-time SLIMBUS-port-init) pótolható. HA nem → a trigger
  a vendor-userspace (acdb/HAL/adsprpc) ioctl-szekvenciája → minimal pmOS-tool kell. **Időzítés-jel ehhez:** a
  downstream a QMI select+power-t 27s-nál küldi (amikor az ADSP SLIMbus-QMI-szolgáltatása regisztrál), a mainline
  13s-nél — vagyis az ADSP **14s-cel később hirdeti meg a SLIMbus-QMI-szolgáltatást downstream-en** = több
  ADSP-belső init fut a meghirdetés/keretezés előtt; ezt a többletet keressük az APR/SMEM-diffben.
- **BLOKKOLÓ:** a döntő UT-capture-höz UT kell felbootolva → pmOS fölé UT újraflashelés, ami a GUI-only UBports
  Installert (nincs headless) + UT-wizard + SSH-engedélyezés igényli → **felhasználói kéz kell**. A capture-tool
  készen áll, egy UT-boot mindent egyben elkap. pmOS-restore: `flash-pmos.sh` + `pmos-backup-20260629`.

## 9.28 ✅✅✅ A DÖNTŐ CAPTURE KÉSZ (2026-06-30, UT 24.04-1.x, kernel 4.9.218) — AFE-trigger MEGCÁFOLVA; az AP-oldal MINDKÉT rendszeren regiszter-szinten TELJES; a gap tisztán ADSP-belső
A felhasználó visszaflashelte az UT-t (`fut UT`); lefutott a `ut-capture-framer.sh` → `pmos-backup-20260629/ut-framer-1406/`.
A `c140000.slim` ipc-log időrendbe rakva (`ipc-slim.txt`, 5–30 s ablak) **a teljes working-framer szekvenciát** megadja:

```
t=6.161  NGD SB controller is up!                 ← AP NGD kész, majd 20 s SEMMI
t=26.487 Slimbus QMI NGD CB received event:2       ← ★ A TRIGGER: ADSP→AP QMI-indikáció (a SLIMbus-QMI-szolgáltatás feláll)
t=26.489 QCCI TX MI:20 (SELECT_INSTANCE) SvcId:301
t=26.497 QCCI RX MI:20 ack
t=26.497 QCCI TX MI:21 (POWER_REQ)      SvcId:301
t=26.510 QCCI RX MI:21 ack
t=26.510 sps_bam 0xc104000 register+enable (RX-msgq pipe connect)
t=26.512 SLIM SAT: Rcvd master capability          ← ★ a power_req-ACK után 2 ms-mal!
t=26.512 capability exchange successful
```

**Az AP TISZTÁN REAKTÍV:** nem kezdeményez, hanem megvárja az ADSP `event:2` indikációját (a SLIMbus-QMI-szerver
felállását = mainline-ban a `new_server`/`qmi_up` completion), és csak utána küld select+power-t. A 20 s rés = az ADSP
a saját SLIMbus-szolgáltatását bootolja.

### A perdöntő A/B: ugyanaz a QMI-szekvencia, MÉGIS más eredmény
A pmOS-baseline dmesg (`bbclk1-1300/dmesg-slim.txt`) **pontosan a most elolvasott mainline `qcom_slim_ngd_power_up()`
kódúthoz illeszkedik** (a DBG-sorokat én tettem be):

```
power_up: enter state=3
power_up: QMI power request OK         ← select_inst(MASTER)+power_req(ACTIVE) MINDKETTŐ sikeres+ACK-olt
power_up: ver=0x105 ngd_status=0x40c   ← NGD_STATUS, NGD_LADDR=BIT(1) NINCS (0x40c & 0x2 = 0)
NGD setup done, waiting for capability (reconf)   ← BAM RX-pipe connect kész, arm NGD_INT_EN
capability exchange timed-out          ← 1 s múlva; a framer SOHA nem írta a MASTER_CAPABILITY-t
... (3–5 mp-enként ismétlődik, mindig ugyanaz)
```

→ **A pmOS AP-oldal regiszter-szinten TELJES és HELYES:** select_inst(MASTER) ✅ + power_req(ACTIVE) ✅ (mindkettő
ACK-olva az ADSP-től) + NGD armed ✅ + BAM RX connected ✅. UT-n ugyanez **2 ms alatt** framert eredményez,
pmOS-en **1000 ms** alatt timeout. **Ugyanaz a firmware, ugyanaz a QMI, ugyanaz a sorrend → a rés 100%-ban ADSP-oldali.**

### Az AFE-port-trigger hipotézis MEGCÁFOLVA
A kérdés volt: a downstream küld-e az ADSP-nek egy AFE/ADM/CORE parancsot a framer ELŐTT, ami beindítja?
- Az UT `apr` ipc_logging-csatornája **TELJESEN ÜRES** (`ipc-adsp-ctrl.txt`: `## apr ##` után rögtön a következő
  fejléc). A framer-up (t=26.5 s) ELŐTT az `ipc-adsp-ctrl.txt`-ben **egyetlen APR/AFE/ADM/CORE-bejegyzés sincs** —
  csak smem/smsm/smp2p (board-config + subsystem-up handshake).
- A working timeline szerint a `Rcvd master capability` a `power_req`-ACK után **2 ms-mal** jön → **nincs idő és
  nincs nyoma** semmilyen apr/AFE közbeiktatott parancsnak. **A framer tiszta QMI(select+power)-ből áll fel** — és
  **pont ezt a QMI-t küldi a pmOS is.** ➡️ A (4)-es trigger **NEM** AFE-port-megnyitás, **NEM** AP→ADSP üzenet.

### Mi marad — a differenciáló az ADSP boot-idejű belső állapota
Ugyanaz a firmware azonos QMI-bemenetre csak akkor reagálhat eltérően, ha a **belső állapota** más a power_req
pillanatában. Ezt az ADSP a saját bootján tölti. Megvizsgált forrásváltozók:
- **socinfo/board-id (UT-n mérve):** `machine=SDM632 soc_id=349 rev=1.0 platform_subtype_id=3 (strange_2a)
  raw_id=186 build_id=8953A-JAASANAZA`. **DE** ezt az **XBL/SBL bootloader írja SMEM-be**, amit az ADSP közvetlenül
  olvas — és az **XBL-t NEM flasheltük újra** → az ADSP **azonos socinfo-t lát pmOS és downstream alatt** is. ⇒ a
  devcfg/audio-cal-variáns-választás azonos ⇒ **board-id-mismatch hipotézis gyengítve** (nem ez, hacsak pmOS más
  adsp.mbn-t nem tölt — pmOS-oldalon ellenőrizendő).
- **A maradék élő hipotézis:** a mainline `qcom-ngd-ctrl` **nem voteol egy slim interface/core/AHB-clockot**, amit a
  downstream `slim-msm` igen (a driverben NULLA natív clk-kezelés volt — a bb_clk1-et is nekünk kellett bedrótozni).
  Ha az ADSP-felőli framer-PHY/c140000-blokk egy AP-által gate-elt interface-clockot igényel a ref-clock MELLETT,
  az hiányozhat. **Köv. lépés:** downstream `msm8953/sdm632` slim-node clock-lista vs mainline DT összevetése.

**Konklúzió-frissítés:** a 9.22/9.25/9.26/9.27 mind megerősítve és LEZÁRVA: AP-oldal kész, QMI ekvivalens, clock
szimptóma, AFE-trigger cáfolva. A vizsgálat egyetlen nyitott frontja: **(a) tölt-e pmOS más adsp-image-et**, és
**(b) hiányzik-e egy slim interface-clock vote** a mainline DT/driverből. Mindkettő pmOS-oldali, ezért pmOS-restore kell.

## 9.29 🧩 SZINTÉZIS (2026-06-30, UT kimerítve) — a (b) clock-hipotézis HALOTT; a modell: az ADSP audio-core nincs inicializálva; a viható pmOS-út = q6afe SLIMBUS AFE-port (a chicken-egg megtörése)
További UT-mérések a frontvonal lezárásához:
- **`subsys2/firmware_name = adsp`** (modem=modem, gpu=a506_zap) → a downstream a **standard `adsp.mbn`-t** tölti,
  azonos néven a pmOS-szal. (Bináris-azonosság pmOS-oldalon ellenőrizhető, de a név/mechanizmus azonos.)
- **`slim@c140000`-nek NINCS `clock-names` property-je** a downstream DT-ben, és a **downstream `clk_summary`-ban
  NULLA `slim/lpass/q6/audio` órajel** → a downstream AP **egyetlen** slim/lpass-clockot sem ad a controllernek; az
  összes LPASS-audio-órajel **ADSP/LPASS-belső**. ➡️ **(b) hipotézis VÉGLEG MEGCÁFOLVA**: nincs AP-votolható slim
  interface-clock se downstream-en, se mainline-on; a bb_clk1-force-vote-unk már így is **több**, mint a downstream.

### A paradoxon és a feloldó modell
Ha minden, amit az ADSP érzékelhet **azonos** (socinfo XBL-ből, QMI bitre ugyanaz, smp2p, és NINCS AP-clocking),
mégis downstream-AP alatt keretez, mainline-AP alatt nem — akkor a különbség az **ADSP belső audio-core
inicializációja**. Az összes bizonyítékkal konzisztens modell:
- Az ADSP **SLIMbus-QMI-szervere KÖNNYŰSÚLYÚ és MINDIG fut** (boot-tól), ezért ACK-olja a select_inst+power_req-et
  **mindkét** rendszeren (pmOS: `QMI power request OK`). Ez **NEM** jelenti, hogy a framer-eszköz aktív.
- A tényleges **keretezést az ADSP audio-core-ja / belső slimbus-device-driver-e** végzi, ami **csak akkor inicializál**,
  ha az ADSP-audio felhozódik. A downstream ezt **boot-időben ACDB/audio-cal betöltéssel** éri el (az AP audio-HAL
  ~20 s-nál tolja az ADSP-be — **EZ a 6 s→26 s rés**), amitől az ADSP audio + slim-framer ready lesz → AP `event:2` →
  handshake → keretezés. pmOS-en **nincs HAL/ACDB** → az ADSP audio-core sosem inicializál → a könnyűsúlyú QMI ACK-ol,
  de a busz néma.
- **A korábbi AFE-cáfolat pontosítása:** igaz, hogy az UT a keretezést NEM AFE-porton át indítja (ACDB-úton megy),
  DE ez **nem zárja ki**, hogy pmOS-en egy **q6afe `AFE_PORT_START(SLIMBUS_x)`** a MÁSIK úton inicializálja az ADSP
  slim-device-ét. Két külön út ugyanahhoz az ADSP-eredményhez: UT=boot-ACDB, pmOS=AFE-port-start.

### KÖVETKEZŐ KONKRÉT KÍSÉRLET (pmOS-oldali, egy változtatás)
**Egy q6afe SLIMBUS backend-DAI + dai-link megnyitása**, hogy egy PCM-indítás `AFE_PORT_START(SLIMBUS_0_RX)`-et
küldjön → az ADSP inicializálja a slim-device-ét → keretez → megjelenik a laddr → a wcd9335 enumerálhat. **Ez töri
meg a chicken-egg-et** (a codec eddig laddr nélkül nem probe-olt). Az AFE-port-open **nem igényli a codec-et** (dummy
codec-dai is elég a backend-hez). Lépések pmOS-restore után: (1) ellenőrizni a pmOS sound-card DT-t — van-e bármilyen
q6afe SLIMBUS dai-link (valószínűleg nincs); (2) hozzáadni egy SLIMBUS_0_RX backend-DAI-t (dummy/`snd-soc-dummy`
codec-kel); (3) PCM-trigger → dmesg: jön-e `Rcvd master capability` / eltűnik-e a `capability exchange timed-out`.
Ha igen → a framer feláll, és a wcd9335-bring-up folytatható. Ha nem → marad az ACDB-injektálás (vendor-userspace).

## 9.30 ❌ P1 (codecless SLIMBUS AFE-port) VÉGREHAJTVA és MEGCÁFOLVA + ✅ DUAL-SLOT INFRA ÉL (2026-06-30, resume)
**Dual-slot KÉSZ és BIZONYÍTOTT:** UT=slot_a (érintetlen, mentve), pmOS=slot_b a **system_b**-ről rootolva. A pmOS
bootol slot_b-ről, root=`/dev/loop0p2` (a 2-subpart image losetup-mountja a system_b-n) — az initramfs
`mount_subpartitions` autodetektálta. OS-váltás mostantól egysoros: `fastboot set_active a|b` + reboot. Script:
`scripts/setup-dualslot.sh` (one-time). A 3050 MiB rootfs befér a 3072 MiB system_b-be (22 MiB tartalék).

**KRITIKUS BUILD-BUG (a fő tanulság):** a `pmb build linux-postmarketos-qcom-msm8953` az **upstream tarballt**
fordítja (`source=$url/archive/v7.0.9-r0.tar.gz`), NEM a lokális `$FP3_PMOS/linux-fp3` fát → **nincs benne sem a
slim-node, sem semmilyen DTS-módosítás**. A működő baseline mindig `--src $FP3_PMOS/linux-fp3`-mal épült (ezért
`_pYYYYMMDDHHMMSS` verziósuffix). EZENTÚL KÖTELEZŐ: `pmb build --src $FP3_PMOS/linux-fp3 linux-...`. (A plain
`7.0.9-r0` apk = upstream, slim-node NÉLKÜL; ellenőrzés: `strings <dtb> | grep slim-ngd`.)

**P1 eredmény (codecless slim-rx/tx-dai-link → dummy codec):** a kártya REGISZTRÁL (card F3, `SLIM RX` mint dev6),
DE: `SLIM RX: ASoC: no backend DAIs enabled ... missing routing` — a codec törlése **megszüntette a DAPM-sink-et**,
így a SLIMBUS_0_RX backend-et a DAPM SOHA nem tudja bekapcsolni → `AFE_PORT_START` SOHA nem indul. **P1 elvi okból
cáfolt:** mainline DAPM-modellben codec-sink nélkül a SLIMBUS AFE-port nem bootstrap-elhető.

**AP-oldal KIMERÍTŐEN igazolva (forráskód, qcom-ngd-ctrl.c):** new_server→`complete(qmi_up)` (=event:2); PDR/SSR
`STATE_UP`→`schedule_work(ngd_up_work)` (boot-on 2× lefut); up_worker várja qmi_up-ot (nincs "QMI wait timeout");
`qcom_slim_qmi_init(ctrl,false)`→`req.mode=SLIMBUS_MODE_MASTER_V01` (HELYESEN MASTER-t kér); power_req ACTIVE ACK-olt;
mégis a `wait_for_completion(reconf,HZ)` timeout → az ADSP SOHA nem küld `SLIM_USR_MC_MASTER_CAPABILITY`-t →
SOHA nem keretez. `ngd_status=0x40c` (NGD_LADDR nincs), `wcd9335-slim: Failed to get logical address`.

**ÚJ perdöntő adat:** a hangszóró MEGY (aw8898 a QUINARY_MI2S-en) → az ADSP **audio-core ÉL** (MI2S AFE_PORT_START
működik). Tehát nem a teljes audio-core halott, hanem **specifikusan a slim-framer al-komponens** nem aktiválódik.
Downstream ezt a HAL ACDB/audio-cal bring-up részeként aktiválja (~20s); mainline-ban nincs HAL/ACDB → a slim-framer
sosem indul. **Következő irány: ACDB/audio-cal injektálás (vendor-userspace), VAGY a slim-framert egy nem-slim úton
nudge-olni** — mivel az audio-core MI2S-re már él, kérdés, mi a slim-framer specifikus aktiváló feltétele.
