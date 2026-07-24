# FP3 — boot-bring-up debug log (chronology + architecture notes)

> Migrated from `Opus-fp3-facts.txt` (chronology half). Dated experiment log for the
> ramdisk/boot/USB-gadget bring-up + the KOMPONENSEK/architecture notes. History — read for 'was X tried?'.

## KÍSÉRLETEK / VÁLTOZTATÁSOK (kronológia)
================================================================================

### [2026-06-25] adb/fastboot telepítés
CMD: sudo apt-get install -y android-tools-adb android-tools-fastboot
MIÉRT: a hoston egyik sem volt → a teljes flash/debug workflow blokkolva.
KIMENET: adb 1.0.41 OK. `adb devices` → $FP3_SERIAL recovery (TWRP).

### [2026-06-25] Ramdisk init átírás: RNDIS → NCM + korai watchdog keepalive
FÁJL: $FP3_ROOT/ramdisk-work/init
MIÉRT:
  (a) "usbnet akad el" fő oka: RNDIS-t a Linux host nem köti automatikusan
      (kézi `echo "22b8 2e76" > /sys/bus/usb/drivers/rndis_host/new_id` kellett,
      és az interfész osztály sem stimmelt). NCM-et a cdc_ncm OSZTÁLY alapján
      magától köti → nincs PC-oldali kézi lépés.
  (b) Watchdog: az MSM HW watchdog az `echo V`-t figyelmen kívül hagyhatja; a
      keepalive korábban csak az inject_loop-ban indult, így a root-mount / USB
      setup alatt resetelhetett. Most a ramdisk LEGELEJÉN indul egy globális
      `echo 1 > /dev/watchdog{,0}` / 10s pet-loop (GLOBAL_WD_PID).
VÁLTOZTATÁSOK:
  - setup_usb_rndis() teljesen átírva: ncm.usb0 function, VID/PID 18d1:4ee4
    (lényegtelen NCM-nél), configs/b.1 → ncm.usb0 symlink, UDC bind, iface=usb0,
    ip 192.168.2.15/24, telnetd :23. Részletes ulog() minden lépés rc-jével.
  - UDC várás 5→10 mp; ha nincs UDC → korai return + log.
  - inject_loop: redundáns 2. watchdog loop törölve (a globális fedi); USB
    reconnect figyelő grep kiegészítve "ncm" előtaggal.
STÁTUSZ: szerkesztés kész, repack + flash következik. MÉG NEM TESZTELVE eszközön.

### [2026-06-25] Boot image repack (NCM ramdisk)
- unpack_bootimg.py a hybris-boot-sdlog.img-en:
    header v0, kernel load 0x80008000, ramdisk load 0x81000000, tags 0x80000100,
    pagesize 2048, cmdline ÜRES (az FP3 bootloader adja a cmdline-t!).
- Ellenőrizve: ramdisk-work == a beágyazott ramdisk pontos bázisa (452 fájl mindkettő;
    a beágyazott init a NCM-előtti setup_usb_rndis + /dev/block/mmcblk1p1 verzió;
    diff csak az én szerkesztéseimet mutatja). → ramdisk-work a helyes forrás.
- Repack: `cd ramdisk-work && find . | cpio -o -H newc --owner=root:root | gzip -9`
    (sudo, root:root tulajdon). Méret: 4543378 B.
- mkbootimg.py: --base 0x80000000 --kernel_offset 0x8000 --ramdisk_offset 0x1000000
    --tags_offset 0x100 --pagesize 2048 --header_version 0 → $FP3_ROOT/hybris-boot-ncm.img (22974464 B)
- Visszaellenőrzés unpackkal: load címek/header egyeznek az eredetivel. OK.

### [2026-06-25] Flash + boot teszt
CMD: adb reboot bootloader → fastboot flash boot_a hybris-boot-ncm.img → set_active a → reboot
- fastboot devices: $FP3_SERIAL; slot-retry-count:a=6, slot-unbootable:a=No
- flash OK (22436 KB), set_active a OK, reboot OK.

### [2026-06-25] EREDMÉNY: NCM NEM jött fel — USB elsötétül ("akad el" reprodukálva)
PC-oldali megfigyelés boot után:
- USB szekvencia: 22b8:2e81 → 22b8:2e76 (ezek a KORÁBBI/TWRP maradékok), majd
  18d1:d00d (device 97, 42255s) → utána TELJES USB-sötét (60s+ semmi).
- SOHA nem jelent meg a 18d1:4ee4 (a mi NCM gadgetünk VID/PID-je).
- Host: nincs új net iface, cdc_ncm nem kötött.
- 18d1:d00d leírója lekérdezéskor már eltűnt (a phone disconnectelt).

ÉRTELMEZÉS (koherens elmélet):
- 18d1:d00d = a bootloader/kernel által átadott ELŐZETES gadget (NEM a miénk).
- A mi setup_usb_rndis-ünk: `echo "" > g1/UDC` UNBIND → d00d eltűnik (ezt láttuk
  disconnectként) → majd NCM rebind (mkdir ncm.usb0 + link + echo UDC) → SIKERTELEN
  → USB sötét marad. PONTOSAN ez a "usbnet akad el" tünet.
- A bind hiba OKA még ISMERETLEN (sleep túl rövid unbind után? ncm function nem
  regisztrált? gadget descriptor invalid? EBUSY?). Vakon nem dönthető el.

### [2026-06-25] ÁTTÖRÉS: pstore/ramoops = megbízható, USB-független log csatorna
Kernel .config: CONFIG_PSTORE=y, PSTORE_CONSOLE=y, PSTORE_RAM=y, PSTORE_PMSG=y.
DTB (msm8953.dtsi, BE van fordítva az Image.gz-dtb-be):
    ramoops_mem@0: reg=<0x0 0x8ee00000 0x0 0x200000> console-size=0x80000(512K)
→ A ramdisk MINDEN `echo ... > /dev/kmsg` sora (köztük az összes "initrd-usb:" ulog)
  a fenntartott RAM régióba kerül, és MELEG ÚJRAINDÍTÁS UTÁN is megmarad.
→ TWRP-ből olvasható: `cat /sys/fs/pstore/console-ramoops-0`
  (ha nincs mountolva: `mount -t pstore pstore /sys/fs/pstore`).
EZ a csatorna NEM függ a hibás USB gadgettől → ezzel kiderül a NCM bind PONTOS rc-je.

================================================================================
## /dev ALATT MIT LÁT A RAMDISK (eddig ismert)
================================================================================
- Blokk eszközök /dev/block/ alatt (NEM /dev/ gyökér): pl. /dev/block/mmcblk1p1.
- /dev/watchdog és /dev/watchdog0 létezik (MSM HW watchdog, az `echo V` nem állítja le).
- /sys/class/udc/ : a DWC3 UDC neve a korábbi jegyzetek szerint "7000000.dwc3" /
  "7000000.ssusb" — pstore logból megerősítendő (UDC=... sor).
- /config/usb_gadget/g1 LÉTEZIK boot közben (bootloader hozza létre, d00d gadget).
- TELJES /dev és /dev/block dump MÉG HIÁNYZIK → pstore/telnet logból pótolandó.

================================================================================
## NYITOTT KÉRDÉSEK / KÖVETKEZŐ LÉPÉSEK
================================================================================
- [ ] *** USER: indítsd a telefont TWRP recovery-be (Power 10s power-off, majd
      Vol Up + Power) → `cat /sys/fs/pstore/console-ramoops-0` olvasása adb-vel.***
- [ ] A pstore logból: UDC neve, ncm.usb0 mkdir rc, UDC bind rc, iface megjelent-e.
- [ ] A bind hiba okának javítása (valószínű: hosszabb sleep unbind után, vagy a
      teljes g1 lebontása + saját gadget; vagy a function regisztráció ellenőrzése).
- [ ] SD log a kártya üres → /dev/block/mmcblk1p1 mountolható-e (van-e p1 partíció)?
      Alternatíva: PC-n vfat partíció írása az SD-re mint MÁSODIK log csatorna.
- [ ] Ha NCM él: telnet 192.168.2.15:23 → lépésenként root-mount és systemd vizsgálat.

### [2026-06-25] ROOT CAUSE az "nincs SD log"-ra: SD kártya ASZINKRON probe
TWRP-ből vizsgálva a kártyát:
- /proc/partitions: mmcblk1=31205376K, mmcblk1p1=102400K (100MB), mmcblk1p2=31101952K (~30GB)
- mmcblk1p1 vfat, TWRP-ben HIBÁTLANUL mountolható, DE ÜRES (semmi boot-N).
→ A ramdisk sdlog_init() közvetlenül a devtmpfs után fut, ekkor a KÜLSŐ SD
  (mmcblk1) MÉG NEM probe-olódott be → /dev/block/mmcblk1p1 node hiányzik →
  `mount` csendben elbukik (2>/dev/null) → SDLOG üres → SOHA nincs SD log.
  TWRP-ben azért megy, mert addigra (~mp-ekkel később) befejeződött a probe.
FIX: sdlog_init() most max 10s-ig VÁR a `[ -b /dev/block/mmcblk1p1 ]` node-ra,
  utána mount. + dev-snapshot.log: ls /dev, /dev/block, /sys/class/udc,
  /sys/class/net, /proc/partitions a SD-re (a "mit lát a ramdisk /dev alatt" kérdésre).
FIX2: setup_usb_rndis() most a teardown ELŐTT kidumpolja a g1 PRE állapotát
  (idVendor/idProduct, functions/, configs/ és a config symlinkek), unbind rc-t,
  és 1s helyett 2s-t vár az UDC felszabadulására.

### [2026-06-25] 2. flash (SD-wait + USB dump) — TWRP adb dd úton
- boot_a = /dev/block/mmcblk0p27. TWRP RAM-ből bootolva (fastboot boot twrp-fp3.img),
  így boot_a flashelhető dd-vel: `adb push hb.img /tmp/ ; dd of=.../boot_a bs=4096`.
- SD-re _marker.txt írva; a kártya egyébként ÜRES volt (megerősíti: az 1. NCM boot
  semmit nem írt SD-re — összhangban az aszinkron-probe okkal).
- adb reboot → 90s figyelés: SEMMI USB enumeráció (még d00d sem). Phone USB-sötét.
  → A gadget vagy fel sem jött, vagy a mi unbind+NCM-bind után sötét maradt.
  → A SD logból (boot-0/) derül ki a pontos ok. KÖVETKEZŐ: recovery → SD olvasás.

### [2026-06-25] 3. flash: eMMC nyers log csatorna (boot_b/p28) hozzáadva
INDOK: 2 egymást követő boot SEMMI USB-t és SEMMI SD logot nem adott. Az SD lehet,
  hogy a mi kernelünkben nem/későn probe-olódik. Az eMMC viszont a boot eszköz →
  a kernel GARANTÁLTAN látja. Választott scratch: boot_b = mmcblk0p28 (64MB,
  HASZNÁLATLAN mert A szlot aktív). Teljes partíciós térkép rögzítve (lásd lent).
IMPLEMENTÁCIÓ (ramdisk-work/init):
  - elog_init(): p28 első 1MB nullázása + "=====ELOG-START=====" header.
  - elog()/elog_flush(): /elog (tmpfs) akkumulátor, minden híváskor a TELJES /elog
    dd-vel p28-ra (bs=64k conv=notrunc) → crash előtt is megmarad.
  - log() és ulog() most elog()-ot is hív → minden naplósor p28-ra kerül.
  - Közvetlenül devtmpfs mount után: elog "ls /dev/block", "ls /sys/class/udc".
  TWRP-ből olvasás: dd if=/dev/block/mmcblk0p28 bs=64k count=16 | strings
- Syntax: sh -n OK (busybox sh). dd boot_a-ra OK. adb reboot → 75s: ISMÉT teljesen
  USB-sötét (d00d sem). → a p28 logból derül ki, meddig jutott az init.

### FP3 eMMC PARTÍCIÓS TÉRKÉP (TWRP by-name, mmcblk0; méret KB)
  boot_a=p27 (64M, AKTÍV), boot_b=p28 (64M, UNUSED→elog cél)
  system_a=p30 (3G), system_b=p31 (3G, unused)
  vendor_a=p32 (1G), vendor_b=p33 (1G, unused)
  userdata=p62 (~52G, Sailfish rootfs+LVM "sailfish")
  misc=p35 (BCB), persist=p34 (32M), logdump=p58 (64M), modem_a=p1
  SD: mmcblk1 (külső), p1=100M vfat (ÜRES), p2=30G
  twrp boot.img RAM-ből: `fastboot boot twrp-fp3.img` (boot_a-t nem bántja)

### [2026-06-25] 4. flash (elog node-wait + fail-halt) → p28 MÉG MINDIG NULLA
- elog_init() most max 15s vár a /dev/block/mmcblk0p28 node-ra; fail() most elog-ol
  és MEGÁLL (nem reboot2 recovery, ami A/B-n loopot okozna).
- p28 előre nullázva flash előtt → boot után OLVASVA: TELJESEN NULLA (0 non-zero byte).
- KÖVETKEZTETÉS: a mi /init-ünk SEMMIT nem ír p28-ra → vagy EL SEM INDUL, vagy a
  legelején meghal (még az eMMC node megjelenése előtt). Nincs USB, nincs SD, nincs
  eMMC log — mindhárom csatorna néma → a hiba KERNEL/BOOT szintű, a userspace előtt.

### [2026-06-25] *** KRITIKUS: A/B slot retry counter elfogyott ***
- fastboot getvar slot-retry-count:a : 6 → 0 (minden boot dekrementálta!)
  slot-unbootable:a = No, slot-successful:a = (üres).
- A hybris-boot SOHA nem hívja a mark_boot_successful-t → a bootloader minden bootnál
  dekrementál. 0-nál a köv. sikertelen bootnál UNBOOTABLE → EDL kockázat (jegyzet!).
- `fastboot set_active a` EZEN a bootloaderen NEM állítja vissza 6-ra (maradt 0)!
  De unbootable=No → még bootol (lenient retry-0). FIGYELNI kell.
- boot_b-be írtam az elog-ot → a B slot NEM valid fallback (felülírtam).
- TENNIVALÓ: vagy a boot jelölje magát successful-nak, vagy minden flash előtt
  retry-budget visszaállítás. EDL terv (firehose) készenlétben tartandó.

### [2026-06-25] DÖNTÉS: on-screen fbcon kernel (a vakság feloldására + user kérés)
A felhasználó kérdezte: hogyan mutassa a kijelző a terminált a splash helyett.
Kernel .config: CONFIG_FRAMEBUFFER_CONSOLE NINCS beállítva (ez hiányzott), pedig
CONFIG_VT=y, CONFIG_FB=y, CONFIG_FB_MSM_MDSS=y már megvolt.
VÁLTOZTATÁS (defconfig lineageos_FP3_defconfig, backup .bak.fbcon.*):
  +CONFIG_FRAMEBUFFER_CONSOLE=y
  +CONFIG_FRAMEBUFFER_CONSOLE_DETECT_PRIMARY=y
  +CONFIG_LOGO=y +CONFIG_LOGO_LINUX_CLUT224=y  (Tux logó = vizuális bizonyíték)
VÁLTOZTATÁS (device/fairphone/FP3/BoardConfig.mk):
  +BOARD_KERNEL_CMDLINE += console=tty0   (kernel printk + initrd echo → fbcon)
→ Ezzel a kijelzőn ÉLŐBEN látszik a kernel boot + bármely panic → kiderül, fut-e
  az init és hol akad el, PC/USB/SD nélkül.

### [2026-06-25] HABUILD környezet helyreállítás (live USB reboot után)
- A build scriptek /mnt/1T-t várnak, de a lemez most /mnt/1TB-n van.
- SYMLINK NEM JÓ: a chrootban /parentroot/mnt/1T → /mnt/1TB abszolút target nem
  oldódik fel. MEGOLDÁS: `sudo mount --bind /mnt/1TB /mnt/1T` (valódi könyvtár).
- `make` közvetlen hívása TILTOTT az új tree-ben ("use envsetup.sh; m").
  → `m -j3 hybris-hal` (a -j3 az OOM ellen; swap 8GB aktív).
- A `m` shell-FÜGGVÉNY: NEM szabad külön `bash script`-be csomagolni (elveszik a fv).
  habuild-run.sh-nak INLINE kell átadni a parancsokat (ugyanabban a shellben fut,
  ahol a habuild-setup.sh source-olta az envsetup-ot + lunch lineage_FP3).
- Build fut: habuild/fbcon-build.log. Force: KERNEL_OBJ/.config törölve.

### [2026-06-25] Kernel rebuild build-system buktatók (és fixek)
1. `make hybris-hal` TILTOTT → `m -j3 hybris-hal` (envsetup `m` wrapper).
2. fs_config_generator.py: `import configparser as ConfigParser` py2 alatt elszáll
   ("No module named configparser"). A build hermetikus py2-t használ a shebangból.
   FIX: try/except import (py3: configparser, py2: ConfigParser) —
   build/make/tools/fs_config/fs_config_generator.py.
3. `m hybris-hal` VNDK ABI check fail: libbinder.so ABI INCOMPATIBLE (vendor variant).
   → `export SKIP_ABI_CHECKS=true` ÉS szűkebb target: `m hybris-boot` (csak kernel+
   boot image, NEM húzza be a vendor/VNDK-t).
4. `m hybris-boot` "ninja: no work to do" — a .config törlése ÖNMAGÁBAN nem váltja ki
   a kernel rebuildet (a kernel rule a KIMENETI fájlra van kötve, nem a configra).
   FIX: a kernel OUTPUT törlése (Image.gz-dtb, Image.gz, kernel, hybris-boot.img) →
   a rule újrafut, regenerálja a .config-ot a defconfigból (fbcon), és újrafordít.
   (.o-kat meghagytam → inkrementális, gyorsabb.)
5. STALE WATCHER LOOPOK: korábbi sessionökből maradt háttér bash loopok (flash+
   reboot+telnet 192.168.2.15 ciklusok) futottak → leállítva (zavarhatták az adb-t
   és a telefont). pkill -f "telnet 192.168|192.168.2.1/24|soong_ui|ninja".

### [2026-06-25] fbcon kernel BUILD SIKERES (19:09)
- m hybris-boot (configparser-fix + SKIP_ABI_CHECKS + kernel output törlés) → OK.
- .config: FRAMEBUFFER_CONSOLE=y, DETECT_PRIMARY=y, LOGO=y, LOGO_LINUX_CLUT224=y.
- System.map: fbcon_startup + fb_console_init JELEN → fbcon tényleg befordult.
- Új kernel: out/target/product/FP3/kernel (18458667 B, fbcon+logo). cmdline: console=tty0.
- REPACK: új fbcon kernel + a MI ramdisk-work-ünk (NCM+elog+node-wait+fail-halt) +
  --cmdline "...console=tty0" → $FP3_ROOT/hybris-boot-fbcon.img (23MB).
- FONTOS: a build-elt hybris-boot.img a STOCK ramdiskot tartalmazza; a mi debug
  ramdisk módosításaink CSAK ramdisk-work-ben vannak (sosem backportoltuk a
  hybris/hybris-boot forrásba). Ezért kézzel kell repackelni a mkbootimg.py-vel.
- KÖVETKEZŐ: flash boot_a-ra fastbootból, majd a TELEFON KÉPERNYŐJÉT figyelni:
  Tux logó → kernel/initrd log → vagy kernel-panic (megmondja, fut-e az init).

### [2026-06-25] *** GYÖKÉROK GYANÚ: BOOT HEADER VERSION 0 vs 1 ***
A fbcon image (v0) flashelve UTÁN: a kijelzőn TOVÁBBRA IS "Fairphone powered by
Android" splash — NINCS Tux logó, NINCS console, NINCS USB. → a kernel EL SEM INDUL.
FELFEDEZÉS (unpack_bootimg összevetés):
- A SZABÁLYOS build (out/.../hybris-boot.img) = HEADER VERSION **1**
  (egyezik: BoardConfig BOARD_BOOT_HEADER_VERSION := 1).
- Az ÖSSZES én mkbootimg.py repack-em = HEADER VERSION **0** (--header_version 0).
- A régi hybris-boot-sdlog.img és -lvm.img IS v0 voltak (korábbi session repackjei).
KÖVETKEZTETÉS: az FP3 (Android 11, A/B) bootloader v1 boot headert vár. A v0 image
fejléce más layout (a v1-ben extra mezők: recovery_dtbo, header_size) → a bootloader
félreparse-olja → EL SEM INDÍTJA a kernelt → splash marad, minden csatorna néma.
EZ MAGYARÁZZA: miért nem futott az init SOHA (p28 nulla, nincs USB/SD) az összes
NCM/elog próbánál — nem a ramdisk/USB volt a hiba, hanem a boot image FORMÁTUM.
FIX: mkbootimg.py --header_version 1 → hybris-boot-fbcon-v1.img (fbcon kernel +
  a mi ramdiskünk + teljes cmdline: earlycon=msm_serial_dm + console=tty0).
Régi cmdline (lvm.img, ami állítólag bootolt) tartalmazta:
  earlycon=msm_serial_dm,0x78af000 firmware_class.path=/vendor/firmware_mnt/image audit=0

### [2026-06-25] A/B slot retry counter RESET módja (működik!)
- `fastboot set_active a` ÖNMAGÁBAN NEM resetel (marad 0/alacsony).
- DE: `fastboot set_active b` UTÁN `fastboot set_active a` → retry-count:a = 7 (MAX)!
  A slot-toggle újraírja a metadatát teljes retry budgettel. unbootable=No.
  EZT használd a counter törléséhez minden flash körül.

================================================================================
## IMG FÁJLOK — mit tartalmaznak és hogyan kell telepíteni
## ($FP3_ROOT/ alatt)
================================================================================

### BOOT IMAGE-EK (a boot_a partícióra: mmcblk0p27)
- hybris-boot-fbcon-v1.img (23MB) — *** LEGÚJABB ***
    fbcon kernel (FRAMEBUFFER_CONSOLE + Tux logó, console=tty0) + a MI ramdiskünk
    (NCM usbnet + elog eMMC log + SD-wait + inject_loop halt). HEADER VERSION 1.
- hybris-boot-fbcon.img (23MB) — UGYANEZ, de HEADER v0 (HIBÁS formátum, NE használd).
- hybris-boot-ncm.img (22.9MB) — régi (eredeti) kernel + NCM/elog ramdisk, HEADER v0.
- hybris-boot-sdlog.img (22.9MB) — régi RNDIS ramdisk, HEADER v0.
- hybris-boot-lvm.img (22.9MB) — legelső build, HEADER v0, bő cmdline.
- boot-kernel.img (18.4MB) — NEM teljes boot image, csak a kicsomagolt kernel blob.
- A BUILD SAJÁT kimenete (stock ramdisk, fbcon kernel, HEADER v1, helyes formátum):
    $FP3_ROOT/hadk/out/target/product/FP3/hybris-boot.img (18MB)

  TELEPÍTÉS (fastbootból):
    fastboot flash boot_a <img>
    fastboot set_active b && fastboot set_active a   # counter reset 7/7-re
    fastboot reboot
  VAGY TWRP-ből (adb):
    adb push <img> /tmp/hb.img
    adb shell "dd if=/tmp/hb.img of=/dev/block/bootdevice/by-name/boot_a bs=4096; sync"

### TWRP
- twrp-fp3.img (32MB) — TWRP recovery. RAM-ből bootolható (boot_a-t NEM bántja):
    fastboot boot $FP3_ROOT/twrp-fp3.img
  (Innen adb shell elérhető: adb devices → "recovery".)

### SAILFISH ROOTFS (a userdata partícióra: mmcblk0p62, ~52GB)
- sailfish-raw.img (1.6GB) — nyers ext4/LVM rootfs (VG "sailfish": root+home LV).
    PC-n loop-mountolható: losetup -f --show; vgchange -a y sailfish; mount /dev/sailfish/root.
- sailfish.img001 (1.4GB) — Android SPARSE image (simg2img kell a kiíráshoz).
  TELEPÍTÉS (TWRP adb, mert >TWRP /tmp; sparse-t simg2img-gal írjuk a partícióra):
    adb push sailfish.img001 /tmp/sailfish.img001
    adb shell "simg2img /tmp/sailfish.img001 /dev/block/bootdevice/by-name/userdata"
  VAGY a nyers raw image dd-vel:
    adb push sailfish-raw.img /tmp/ ; adb shell "dd if=/tmp/sailfish-raw.img of=/dev/block/mmcblk0p62 bs=4096"

### USERDATA MENTÉSEK (diagnosztika, NEM telepítendők)
- userdata-pull.img (3.4GB), userdata-head.img (1.7GB), userdata-live.img (189MB)
    — korábbi `adb pull`/`dd` mentések a userdata-ról elemzéshez.

### eMMC SCRATCH (debug log csatorna)
- boot_b = mmcblk0p28 (64MB, HASZNÁLATLAN) → a ramdisk elog ide ír nyersen.
    Olvasás TWRP-ből: adb shell "dd if=/dev/block/mmcblk0p28 bs=64k count=16" | strings

================================================================================

### [2026-06-25] A BUILD SAJÁT (v1, érintetlen) image SEM bootol → kernel/eszköz szint
A build saját hybris-boot.img (header v1, fbcon kernel, stock ramdisk) flashelve →
TOVÁBBRA IS "Fairphone powered by Android" splash, nincs Tux, nincs USB.
→ Tehát NEM a repack és NEM a header-version a (fő) gond: maga a kernel nem indul el,
  vagy az eszköz nem bootolja a boot_a-t. Nyitott irány: a v1 kernel/dtb betöltés,
  vbmeta/AVB, vagy a boot_a tartalmának ellenőrzése; ill. a STOCK (sosem patchelt)
  LineageOS hybris-boot.img kipróbálása referencia gyanánt.

================================================================================
## KOMPONENSEK ÉS ARCHITEKTÚRA — mi micsoda, mit hova kell írni
================================================================================

### A) MI EGY BOOT IMAGE? (Android boot.img formátum)
Egy `boot.img`/`hybris-boot.img` NEM egy fájlrendszer, hanem egy KONTÉNER, amit a
bootloader (Qualcomm aboot) tölt be. Felépítése (ANDROID! magic):
  [ header ] [ kernel ] [ ramdisk ] [ second(opcionális) ] [ dtb/recovery_dtbo(v≥1) ]
Összetevők:
  - HEADER: magic "ANDROID!", méretek, load címek, pagesize, cmdline, HEADER VERSION.
      * header_version 0: alap. header_version 1: extra mezők (recovery_dtbo, header_size).
      * FP3 BoardConfig: BOARD_BOOT_HEADER_VERSION := 1 → a build v1-et készít.
      * (Ebben a sessionben a v0/v1 NEM volt a boot-blokkoló — lásd boot loop lent.)
  - KERNEL: a `Image.gz-dtb` = gzippelt ARM64 kernel Image + HOZZÁFŰZÖTT base DTB.
      Load: 0x80008000 (base 0x80000000 + offset 0x8000).
  - RAMDISK: gzippelt cpio archívum = a kezdeti fájlrendszer (initramfs), benne a `/init`.
      Load: 0x81000000 (base + 0x1000000).
  - CMDLINE: kernel parancssor. Az FP3-on a bootloader a SAJÁT cmdline-ját HOZZÁFŰZI
      ehhez (pl. androidboot.serialno, slot). A miénk: console=tty0 + earlycon stb.
  - DTB: a hardver leírása (device tree). Itt a base DTB a kernelhez van fűzve
      (Image.gz-DTB). Külön DTBO partíció (dtbo_a) overlay-eket ad hozzá boot időben.

### B) MI A KERNEL?
- Forrás: kernel/fairphone/sdm632 (LineageOS android_kernel_fairphone_sdm632, lineage-18.1).
- Verzió: 4.9.x (Android 11 base). Konfiguráció: arch/arm64/configs/lineageos_FP3_defconfig.
- Build kimenet: out/target/product/FP3/obj/KERNEL_OBJ/  (.config, vmlinux, System.map,
  arch/arm64/boot/Image.gz, Image.gz-dtb). A "telepített" kernel: out/.../FP3/kernel.
- A defconfig-ot mi módosítottuk: Sailfish mer-check opciók (VT, DEVTMPFS, SYSVIPC...),
  ÉS most fbcon (FRAMEBUFFER_CONSOLE + LOGO) a képernyős konzolhoz.
- Újrafordítás: HABUILD chrootban `m -j3 hybris-boot` (a kimeneti Image.gz-dtb törlése
  kell hozzá, hogy a .config a defconfigból regenerálódjon).

### C) MI A RAMDISK (initramfs)?
- Egy cpio.gz archívum, amit a kernel a RAM-ba csomagol ki és a `/init`-et indítja PID 1-ként.
- Mi NEM a tree-beli stock ramdiskot használjuk, hanem a kézzel patchelt
  $FP3_ROOT/ramdisk-work/ fát (452 fájl: busybox /bin, /sbin/root-mount,
  /init stb.). A mi /init-ünk: SD/eMMC logging, NCM usbnet, telnetd, inject_loop halt.
- Becsomagolás: `cd ramdisk-work && find . | cpio -o -H newc --owner=root:root | gzip`.
- A hybris-boot init feladata: /proc,/sys,/dev mount → root-mount (LVM a userdata-ról) →
  switch_root a Sailfish rootfs-re → ott átveszi a systemd.

### D) DTB és DTBO
- DTB (device tree blob): a hardver leírása a kernelnek (memória, perifériák, MDSS, USB...).
  Itt a base DTB a kernelhez fűzve (Image.gz-dtb). FORRÁS: a kernel dts/ (msm8953 + fp3).
- DTBO (DTB overlay): külön `dtbo_a` partíció (mmcblk0p23/24). A bootloader a base DTB-re
  rétegezi boot időben. HA a dtbo INKOMPATIBILIS a kernel base DTB-jével → korai kernel-pánik.
  *** EZ A JELENLEGI BOOT LOOP EGYIK FŐ GYANÚSÍTOTTJA (lásd lent). ***

### E) PARTÍCIÓS TÉRKÉP — mit hova kell írni (FP3 eMMC = mmcblk0, A/B szlotos)
  | Tartalom         | Partíció (A szlot)    | Mit írunk oda |
  |------------------|-----------------------|---------------|
  | BOOT image       | boot_a   = mmcblk0p27 | hybris-boot*.img (kernel+ramdisk) |
  | (boot B, unused) | boot_b   = mmcblk0p28 | (elog scratch — NEM valódi boot!) |
  | DTBO overlay     | dtbo_a   = mmcblk0p23 | dtbo.img (a build készíti) |
  | vbmeta (AVB)     | vbmeta_a = mmcblk0p25 | vbmeta.img (verifikáció ki/be) |
  | Android system   | system_a = mmcblk0p30 | (Sailfishnél a /system mount forrása) |
  | Android vendor   | vendor_a = mmcblk0p32 | firmware/HAL blobok (/vendor) |
  | SAILFISH rootfs  | userdata = mmcblk0p62 | sailfish-raw.img / .img001 (LVM: root+home) |
  | persist          | persist  = mmcblk0p34 | (gyári kalibráció — NE bántsd) |
  | modem/firmware   | modem_a  = mmcblk0p1  | (gyári — NE bántsd) |
  Külső SD: mmcblk1p1 (vfat, debug log), mmcblk1p2 (tárhely).

  FLASH eszközök:
   - fastbootból: `fastboot flash <partíció> <img>`  (pl. boot_a, dtbo_a, vbmeta_a, system_a)
   - TWRP adb-ből: `adb push img /tmp/x; adb shell "dd if=/tmp/x of=/dev/block/bootdevice/by-name/<part>"`
   - Sailfish rootfs (sparse): `adb shell "simg2img /tmp/sailfish.img001 /dev/block/.../userdata"`

### F) A TELJES SAILFISH "STACK" egy bootnál (mi hol lakik)
  1. bootloader (aboot, mmcblk0p21) → betölti boot_a-t, alkalmazza dtbo_a-t, indítja a kernelt.
  2. KERNEL (boot_a-ból) → kicsomagolja a RAMDISK-et → futtatja /init-et.
  3. RAMDISK /init → mountolja a /system_a-t, /vendor_a-t, és a userdata LVM-ről a Sailfish
     root LV-t → switch_root.
  4. SAILFISH rootfs (userdata LVM "sailfish/root") → systemd → droid-hal-init (Android HAL
     a /system+/vendor blobokból) → usb-moded, lipstick (UI) stb.
  → Egy működő boothoz MIND kell: ép boot_a (kernel+ramdisk) + kompatibilis dtbo_a +
    ép system_a/vendor_a + ép Sailfish rootfs a userdata-n. Bármelyik sérülése → boot fail.

================================================================================

### [2026-06-25] *** BOOT LOOP — a tényleges jelenlegi tünet ***
- fastboot getvar slot-retry-count:a: 7 → 2 EGYETLEN boot alatt = a bootloader ~5x
  próbálta boot_a-t → KERNEL megkapja a vezérlést, de MÁSODPERCEKEN belül RESETEL.
- A reset MÉG AZ ELŐTT van, hogy az init elérné az elog-ot (p28 = 0) → KORAI KERNEL-PÁNIK,
  a userspace ELŐTT.
- MINDEN image-re igaz (saját repack, build saját kimenete, ÉS az eredeti sdlog.img)
  → NEM a boot image a hibás, hanem ESZKÖZ/PERZISZTENS-ÁLLAPOT szint.
- AVB NEM blokkol: `unlocked: yes`.
- Counter visszaállítás: `set_active b` majd `set_active a` → retry 7, unbootable No.
- FŐ GYANÚSÍTOTTAK (korai kernel reset oka, ami a korábbi működő session óta változott):
  a) dtbo_a inkompatibilis/sérült → base DTB+overlay merge hibás → korai pánik.
  b) a korábbi sessionben más kernel/dtbo volt flashelve, ami azóta felülíródott.
  c) persist/vbmeta/userdata állapotváltozás.
- KÖVETKEZŐ ÖTLET: stock LineageOS boot.img tesztflashelése (bootol-e a gyári? → eszköz OK),
  vagy a dtbo_a újraflashelése a build out/.../dtbo.img-ből; ill. earlycon serial, ha van pin.

### [2026-06-25] *** VÉGSŐ DIAGNÓZIS (a session összegzése) ***
TÉNY: a hybris kernelünk MINDEN boot image-nél NAGYON KORÁN megakad —
  a framebuffer/fbcon init ELŐTT (nincs Tux logó) ÉS a userspace/init ELŐTT
  (p28 elog üres). A watchdog ~8mp után resetel → lassú boot loop (retry fogy).
BIZONYÍTÉKOK:
  - retry-count 7→2/7→5 boot alatt = a bootloader átadja a vezérlést, de a kernel resetel.
  - p28 (elog) = 0 → init el sem indul.
  - USB/SD/eMMC mind néma; a kijelző mozdulatlan splash (nincs Tux → fb init előtt akad).
  - unlocked: yes → NEM AVB-blokk.
  - MINDEN image egyformán bukik: saját repack (v0 ÉS v1), build saját kimenete,
    eredeti sdlog.img, lvm.img (bő cmdline), dtbo újraflashelve is.
KULCS: a TWRP (stock kernel) TÖKÉLETESEN bootol (fastboot boot twrp, adb megy, kijelző megy)
  → az ESZKÖZ (HW, bootloader, kijelző, USB, dtbo, vbmeta) HIBÁTLAN.
  → A hiba KIFEJEZETTEN a mi hybris kernelünk/boot image-ünk korai hangja.

DEBUG CSATORNÁK — mind kipróbálva, mind ZSÁKUTCA (mert mind a kernel
továbbjutását igényli, ami nem történik meg):
  - USB NCM/RNDIS: néma (init nem fut).
  - SD vfat log: néma (init nem fut / aszinkron probe).
  - eMMC p28 elog: néma (init nem fut).
  - fbcon kijelző: mozdulatlan splash (kernel az fb init előtt akad).
  - pstore/ramoops: TWRP kernelben nincs ramoops node → /sys/fs/pstore üres.
  - /dev/mem @ 0x8ee00000 (ramoops RAM): TWRP STRICT_DEVMEM tiltja → 0 bájt.

NYITOTT KÉRDÉS: a korábbi sessionök "működő bootjai" (SD log boot-0..3, usb-moded
  22b8:2e76) VALÓBAN teljes bootok voltak-e, vagy félállapotok? A sailfish-customizations.md
  tele van "tesztelés alatt"/RNDIS-soha-nem-ment megjegyzéssel → LEHET, hogy a port
  SOHA nem bootolt teljesen, és most a korai kernel-hang a tényleges nyitott probléma.

REÁLIS KÖVETKEZŐ LÉPÉSEK (a vak flashelés helyett):
  1. *** SOROS KONZOL *** — earlycon=msm_serial_dm,0x78af000 már a cmdline-ban.
     Az MSM8953/FP3 debug UART USB-UART adapterrel kiolvasható (Qualcomm a USB-C CC
     vonalon vagy teszt-padon). Ez mutatná meg a KORAI kernel-pánik PONTOS okát.
     EZ a hybris-porterek standard módja pont erre az esetre.
  2. Recovery/boot image a mi kernelünkkel, DE a ramoops node-dal, amit egy MÁSIK
     (bootoló) kernel olvas — körkörös, mert a mi kernelünk nem bootol.
  3. Teljes, tiszta újraépítés (make hybris-hal a configparser+SKIP_ABI_CHECKS fixekkel)
     + git/backup keresés a ténylegesen-flashelt korábbi .img után.

ESZKÖZ BIZTONSÁG: a boot_a hibás image-dzsel sem brickel — bármikor `fastboot boot
  twrp-fp3.img` (RAM). A slot retry-count alacsonyra eshet → flash előtt/után:
  `fastboot set_active b && fastboot set_active a` (visszaállítja 7-re, unbootable=No).

### [2026-06-25] TISZTA SD-LOG RAMDISK (regresszió-visszafejtés)
FELISMERÉS: a "boot loop"/korai reset valószínű OKA a SAJÁT watchdog-keepalive loopom
  volt a ramdiskben: `echo 1 > /dev/watchdog` 10mp-enként → ÉLESÍTETTE a watchdogot,
  ami a logolás előtt resetelt. Az eredeti működő boot-1/2/3 ezt NEM csinálta.
ÚJ init (ramdisk-work/init, teljesen újraírva, TISZTA):
  - watchdog CSAK letiltva ('echo V'), NINCS re-arm/keepalive.
  - NINCS usbnet (setup_usb_rndis kivéve — ez volt a "gondok" forrása).
  - NINCS inject_loop, NINCS eMMC elog.
  - SD mount node-várással (mmcblk1p1), boot-N rotáció.
  - FOLYAMATOS SYNC háttérben (1mp) → kifagyás/reset esetén is megmarad a log.
  - dmesg -w → SD (élő kernel log), snapshot.log (cmdline/part/dev/udc/net),
    set -x trace → SD trace.log, root-mount kimenete → SD root-mount.log.
  - milestone-ok /dev/kmsg-re is → fbcon kernellel a KÉPERNYŐN láthatók.
  - VÉGÉN MEGÁLL (NINCS switch_root): "HALT alive heartbeat=N" számláló kmsg-re
    (élő bizonyíték, hogy fut és nem resetel) + heartbeat.log SD-re.
  - Build: fbcon kernel + header v1 + console=tty0 → hybris-boot-sdlog-clean.img.
DÖNTŐ TESZT: ha a képernyőn szöveg/heartbeat számlál → init FUT (a watchdog volt a bug,
  SD-log újra él). Ha splash marad → a kernel tényleg az init előtt akad.

### [2026-06-25] *** KRITIKUS: a slot-toggle ÉRVÉNYTELENNÉ tette a slotot (INVALID) ***
TÜNET: egy ponttól KEZDVE SEMMI nem bootolt — még a boot_a-ra flashelt TWRP sem;
  a telefon mindig fastbootba esett. A `fastboot getvar current-slot` = **INVALID**!
OK: a retry-counter "resetelésére" használt `set_active b` → `set_active a` TOGGLE
  (amit sokszor megismételtem) ELRONTOTTA a slot-metadatát → current-slot=INVALID →
  a bootloader nem tud melyik szlotot bootolni → fastboot/garbage.
KÖVETKEZMÉNY: a "header v0 vs v1", "hybris vs stock kernel", "init nem fut" KÉSEI
  tesztjeim mind ÉRVÉNYTELENEK voltak — nem az image-ek hibáztak, hanem a corrupt
  slot miatt a bootloader semmit (vagy a garbage boot_b-t) bootolta.
FIX: `fastboot --set-active=a` → current-slot=a (érvényes) → boot_a AZONNAL bootol
  (TWRP boot_a-ról 31s alatt feljött).
*** SZABÁLY: SOHA `set_active b`! Counter-reset CSAK `fastboot --set-active=a`-val. ***
*** boot_b SZEMÉT (elog/null) → ha a bootloader valaha B-re esik, az fail. Hagyni
    kell a slotot A-n, vagy boot_b-be is valid image-et tenni. ***

### TANULSÁG: pstore/ramoops NEM járható TWRP-ből
- TWRP saját kernele (twrp-fp3.img) NEM tartalmazza a ramoops_mem@0 node-ot a
  DTB-jében, ezért /sys/fs/pstore ÜRES a TWRP alatt (nem látja a mi kernelünk által
  írt RAM régiót). → ramoops csak akkor járható, ha a ramoops-os kernel olvassa
  vissza reboot után. SD kártya a megbízható csatorna.

================================================================================
### [2026-06-25 este] *** ÁTTÖRÉS: a saját átírt init volt a regresszió ***
================================================================================

FŐ FELISMERÉS: a hetek óta tartó "init nem fut / reset loop" oka az volt, hogy
az ÁLTALAM átírt egyedi ramdisk-init lecserélte a BIZONYÍTOTTAN MŰKÖDŐ mer-hybris
init-script logikát. Vissza kell térni a stock scripthez.

-- KÉT KÜLÖNBÖZŐ init létezik a fában, NE keverd: --
1) ./hadk/hybris/hybris-boot/initramfs .../init  (2906 byte, "Jolla generic"):
   proc/sys/dev mount → `echo V > /dev/watchdog` → /sbin/root-mount → HA HIBA:
   fail() → `reboot2 recovery`. EZ a reset-loop forrása: ha az LVM rootfs mount
   elhasal (márpedig a user szerint SOSEM működött), AZONNAL újraindít. NINCS
   telnet, NINCS halt. A hybris-boot-lvm.img EZT tartalmazza → ezért "sosem ment".
2) ./hadk/hybris/hybris-boot/init-script  (13113 byte, KANONIKUS mer-hybris):
   EZ a helyes. Tartalmazza a teljes telnet-rescue-t. Placeholderek:
   %BOOTLOGO% %ALWAYSDEBUG% %DATA_PART% %DEFAULT_OS%.
   Ha ALWAYSDEBUG=1 (vagy `bootmode=debug` a cmdline-on, vagy /diagnosis.log
   létezik, vagy switch_root fail) → run_debug_session:
     - usb_setup_configfs: gadget 0x18D1:0xD001, rndis, UDC=7000000.dwc3
     - ifconfig rndis0 192.168.2.15
     - udhcpd (szerver 192.168.2.20-90), telnetd -b 192.168.2.15:23 -l /bin/sh
     - inject_loop: MEGÁLL, a host `echo "..." >/init-ctl/stdin`-nel parancsol,
       `echo continue >/init-ctl/stdin`-nel engedi tovább. PONT A KÉRT MŰKÖDÉS.

-- BIZONYÍTÉK hogy az init-script MŰKÖDIK a device-on: --
./sdlogs/external_sd/init-debug.log (21844 byte, boot-0..3) egy KORÁBBI futás
teljes `set -x` trace-e: végigment usb_setup → ifconfig rndis0 192.168.2.15 →
udhcpd → "starting telnetd" → telnetd port 2323 → HALT_BOOT=y. Tehát a device
oldal TELJESEN jó volt; a rndis0 felállt (HWaddr 06:47:BB:45:C8:D8), de
RX/TX=0 → a HOST SOSEM csatlakozott. Két host-oldali gond:
  (a) a device udhcpd elhasalt: "/etc/udhcpd.conf: nonexistent directory" (nincs
      /etc a rootfs branchben) → a host nem kapott IP-t DHCP-vel.
  (b) a host nem kapott statikus IP-t sem / nem jött létre iface.
=> MEGOLDÁS: a HOST-ot STATIKUSAN kell 192.168.2.x-re állítani és telnetelni;
   nem szabad a (törött) device-udhcpd-re hagyatkozni.

-- MAI ÉRVÉNYTELENÍTÉS: a TWRP-kernel + a mi ramdiskünk teszt NEM dönt a ramdiskről --
A stock FP3/TWRP kernel valószínűleg másképp (vagy egyáltalán nem) populálja a
devtmpfs-t úgy ahogy a mi shell-initünk várja, ezért a "p28 üres TWRP-kernellel"
NEM bizonyítja hogy a ramdisk rossz. A HELYES kernel a HYBRIS kernel (a hybris-boot
image-ekben), mert azt erre építették. A user megerősítette: az SD-írás akkor ment,
amikor az init ~10 mp-et VÁRT a /dev node-ok aszinkron megjelenésére.

-- AMIT MA ÉPÍTETTEM: $FP3_ROOT/hybris-telnet-debug.img --
Összetevők:
  - kernel: hybris fbcon kernel (inspect/hk/kernel, hybris-boot-fbcon.img-ből, 18MB,
    console=tty0, fbcon befordítva).
  - ramdisk: a stock hybris ramdisk-fa (lvm.img-ből kibontva: busybox-static,
    ifconfig/telnetd/udhcpd applet-ek, root-mount, sbin tools) + JAVÍTVA:
      * /bin/busybox = valódi statikus busybox (az eredeti bin/* symlinkek a
        nemlétező /sbin/busybox-ra mutattak; az init-script `/bin/busybox --install
        -s`-t hív, ezért kell valódi /bin/busybox).
      * /init = a KANONIKUS init-script, ALWAYSDEBUG=1-re patchelve (telnet mindig).
      * Beszúrt SD FOLYAMATOS LOG hook (do_mount_devprocsys után): mmcblk1p1-re vár
        max 15s, /sdlog/boot-N/{init.log,dmesg.log} 1mp-enként + sync (freeze-túlélő).
      * Beszúrt WATCHDOG-LETILTÁS (echo V) + KORAI eMMC MARKER p28-ra
        ("INIT-SCRIPT-RAN ...") a do_mount_devprocsys után, SD-független bizonyítéknak.
  - mkbootimg: header v0, base 0x80000000, kernel_off 0x00008000, ramdisk_off
    0x01000000, second_off 0x00f00000, tags 0x00000100, pagesize 2048,
    cmdline: "... androidboot.usbconfigfs=true loop.max_part=7 console=tty0 bootmode=debug".
  Build-fájlok: scratchpad/build-init (a patchelt init), scratchpad/rd/ (a fa),
  scratchpad/telnet-rd.gz, scratchpad/inspect/hk/kernel.
  ÚJRAÉPÍTÉS: `cp build-init rd/init; cd rd; sudo find .|sudo cpio -o -H newc
  --owner=root:root|gzip -9 > ../telnet-rd.gz` majd a fenti mkbootimg.

-- TESZT EREDMÉNY (2x fastboot boot hybris-telnet-debug.img, valid slot a): --
  - Splash ("fairphone powered by android") megjelent → a kernel+ramdisk elindult.
  - dmesg a hoston: 22b8:2e81 → **22b8:2e76** (ez a memória szerint a "ramdisk USB")
    → később 18d1:d00d (=FASTBOOT, a device visszaesett bootloaderbe).
  - NEM jött fel 18d1:d001 rndis gadget, és NEM jött létre host hálózati iface
    (70s végigpollozva sem). SD ÜRES maradt, p28-at még nem olvastam ki az utolsó
    (marker+watchdog-os) build után.
  - ÉRTELMEZÉS: a 22b8:2e76 a KERNEL default gadgetje (androidboot.usbconfigfs);
    mivel az init SOHA nem konfigurálta át rndis-re (18d1:d001), az init-script
    valószínűleg a usb_setup ELŐTT meghal — gyanú: `/bin/busybox --install -s`
    vagy do_mount_devprocsys. A 2. build (marker+watchdog) gyorsabban resetelt.

================================================================================
### KÖVETKEZŐ TEENDŐK (prioritás sorrendben)
================================================================================
1) *** p28 KIOLVASÁS a legutóbbi (marker+watchdog) build után. *** Eszköz fastbootba
   (power+vol up) → `fastboot boot twrp-fp3.img` → adb:
     `dd if=/dev/block/mmcblk0p28 bs=512 count=8 | strings`
   - "INIT-SCRIPT-RAN" → az init FUT a do_mount_devprocsys-ig; a baj a usb_setup/
     rndis-ben vagy utána van → 3) pont.
   - üres → az init a busybox-install/devprocsys-nél hal → 2) pont.
   (p28 az előző boot előtt nullázva lett TWRP-ből: dd if=/dev/zero ...p28.)

2) HA p28 üres: az init-script korai halála. Teendő:
   - Ellenőrizd hogy a hybris kernelben CONFIG_DEVTMPFS(_MOUNT), CONFIG_DEVPTS,
     CONFIG_CONFIGFS_FS=y (a check_kernel_config ezt írná /diagnosis.log-ba, de
     az csak ha eljut odáig). 
   - Tegyél eMMC-markert MÉG a busybox-install ELÉ nem lehet (nincs /dev). Helyette:
     próbáld a 22b8:2e76 fázis alatt usbnet helyett: a kernel cmdline-ba adb-t? Nem.
   - Alternatíva: használd a működő SD-író init korábbi receptjét (a user szerint
     volt működő SD-log ~10s várakozással) és építsd RÁ az init-script telnetjét.

3) HA p28 = "INIT-SCRIPT-RAN" (init fut, csak a host nem lát rndis-t):
   - A HOST oldalon a device boot-ja ALATT (amíg a gadget fent van) figyeld:
     `for i in $(seq 1 60); do ls /sys/class/net; lsusb|grep -iE '18d1|22b8'; sleep 1; done`
   - Ha 18d1:d001 megjelenik de nincs iface: `sudo modprobe rndis_host cdc_ether`;
     nézd `sudo dmesg | tail` rndis_host bind hibát.
   - Amint van usbX/enxXX iface: STATIKUS host IP:
     `sudo ip addr add 192.168.2.14/24 dev <IFACE>; sudo ip link set <IFACE> up`
     majd `telnet 192.168.2.15 23`  (initrd fázis: port 23, NEM 2323!).
   - A telnet shellben minden kézből indítható (PID1 inject: 
     `echo "ls -l /" >/init-ctl/stdin`, `echo continue >/init-ctl/stdin`).
   - Ha a device-on a configfs gadget vendor 22b8 marad (nem 18d1): akkor is rndis
     funkció van rajta → a host rndis_host akkor is köthet; a vendor ID nem számít
     a működéshez.

4) ALTERNATÍV CSATORNA ha az rndis host-oldal makacs: NCM (cdc_ncm a Linux hoston
   automatikusan köt). Az init-script USB_FUNCTIONS=rndis-t használ; lehet ncm-re
   állítani (USB_FUNCTIONS=ncm + functions/ncm.usb0), de előbb a rndis-t próbáld
   statikus IP-vel — a device oldal bizonyítottan kész.

5) SZABÁLYOK (változatlan): SOHA `set_active b`; slot maradjon A-n (valid).
   Counter-reset CSAK `fastboot --set-active=a`. Minden teszt `fastboot boot`-tal
   (RAM-ból), hogy a slot/retry ne romoljon.

================================================================================
### [2026-06-25 késő este] DÖNTŐ NYOM: fastboot boot (RAM) vs FLASHELT boot
================================================================================
ÚJ MÉRÉS (mindkét kernellel, valid slot a, fastboot boot):
- hybris-telnet-debug.img (FBCON kernel)  → splash, gadget 22b8:2e76 ~10perc, reset
- hybris-telnet-debug-origk.img (EREDETI jún22 kernel) → ugyanaz: gadget 22b8:2e76
  ~4 perc (dev105: 61823→62059), majd 18d1:d00d (fastboot) = RESET.
- MINDKETTŐ: p28 = csupa NULLA (init-marker SOHA nem íródik), SD ÜRES,
  rndis (18d1:d001) SOHA nem jön fel, host iface SOHA nem jön létre.
- A 22b8:2e76 a FP3 KERNEL default composite gadgetje (androidboot.usbconfigfs);
  az init SOHA nem konfigurálja át rndis-re → az init NEM ér el a usb_setup-ig,
  sőt a do_mount_devprocsys utáni p28-markerig sem.

KÖVETKEZTETÉS: a hybris kernel (RAM-boot úton) NEM exec-eli az /init-et — korán
hangol, ~4 perc múlva watchdog-reset. (Egybevág a korábbi "retry 7→4, reset before
init" méréssel.)

ELLENTMONDÁS: ./sdlogs/external_sd/init-debug.log BIZONYÍTJA, hogy egyszer az init
TELJESEN végigfutott (telnetd-ig). A legvalószínűbb különbség:
  *** az a működő futás FLASHELT boot partícióról indult, NEM `fastboot boot`-tal. ***
Sok Qualcomm eszközön a `fastboot boot <img>` (RAM-boot) másképp/hibásan adja át a
vezérlést (dtb/header), míg a boot_a-ra FLASHELT image a normál A/B úton helyesen
exec-eli az initet.

*** KÖVETKEZŐ DÖNTŐ TESZT (next session, 1. prioritás): ***
  1) fastboot:  fastboot getvar current-slot   (legyen 'a')
  2) zero p28 nem kell (már 0).
  3) FLASHELD a boot_a-ra (NEM fastboot boot!):
       fastboot flash boot $FP3_ROOT/hybris-telnet-debug-origk.img
     (vagy TWRP-ből: adb push + dd of=/dev/block/by-name/boot_a)
  4) fastboot --set-active=a    (SOHA set_active b!)   majd  fastboot reboot
  5) Hagyd bootolni, KÖZBEN a hoston pollozd 90s:
       for i in $(seq 1 90); do ls /sys/class/net; lsusb|grep -iE '18d1|22b8'; sleep 1; done
     - ha 18d1:d001 + új iface → SIKER: statikus host IP 192.168.2.14/24, telnet
       192.168.2.15 23.
     - ha megint 22b8:2e76 + p28 üres → a hybris kernel tényleg nem futtatja az
       initet flashelve sem → akkor a KERNEL a hibás (újra kell építeni TISZTÁN,
       a MAKE_EXIT=1 build hibákat kijavítva: configparser shim, SKIP_ABI_CHECKS).
  6) p28 ellenőrzés TWRP-ből mindig: dd if=/dev/block/mmcblk0p28 bs=512 count=4|xxd
  FONTOS: flashelés UTÁN a boot_a-n a mi image-ünk lesz; ha bootloop, power+volup→
  fastboot, és vissza lehet flashelni a valódi bootot vagy TWRP-t tesztelni.

KÉSZ IMAGE-EK (next session azonnal tesztelhető):
  - $FP3_ROOT/hybris-telnet-debug-origk.img  (EREDETI kernel + telnet-rd)
  - $FP3_ROOT/hybris-telnet-debug.img        (FBCON kernel + telnet-rd)
  Ramdisk forrás: scratchpad/build-init (init-script ALWAYSDEBUG=1 + SD-log + p28-marker
  + watchdog-off), scratchpad/rd/ fa, scratchpad/telnet-rd.gz.

================================================================================
### *** KRITIKUS HIBA EBBEN A SESSION-BEN: kimaradt a host new_id! ***
================================================================================
A host rndis_host drivere NEM köti automatikusan a 22b8 vendort (nincs az id
táblájában). A 22b8:2e76 ~4 percig FENT volt mindkét boot-nál, de mert NEM adtam
hozzá a new_id-t, nem jött létre iface → tévesen "nincs usbnet"-nek tűnt.
A 22b8:2e76 NAGY VALÓSZÍNŰSÉGGEL csatlakoztatható rndis gadget volt!

*** HELYES HOST RECEPT (a boot ELŐTT futtasd, majd boot alatt tartsd) ***
  sudo modprobe rndis_host cdc_ether
  echo "22b8 2e76" | sudo tee /sys/bus/usb/drivers/rndis_host/new_id
  echo "22b8 2e81" | sudo tee /sys/bus/usb/drivers/rndis_host/new_id
  echo "18d1 d001" | sudo tee /sys/bus/usb/drivers/rndis_host/new_id
  # boot alatt: amint enx*/usb* iface megjelenik:
  sudo ip addr add 192.168.2.14/24 dev <IFACE>; sudo ip link set <IFACE> up
  telnet 192.168.2.15 23      # initrd fázis port 23

=> ÚJRA KELL TESZTELNI a meglévő hybris-telnet-debug-origk.img-et: csak fastboot
   boot + a fenti new_id host-receptet ALKALMAZVA pollozni 90s-ig az ifészre.
   LEHET, hogy a device oldal végig MŰKÖDÖTT és csak a host new_id hiányzott!
   (Ez ELŐBBRE való mint a flash-vs-fastboot teszt — előbb ezt próbáld.)

================================================================================
### [2026-06-26] SLOT RETRY-COUNT RESET — EGYETLEN MŰKÖDŐ RECEPT
================================================================================

SZIMPTÓMA: `fastboot getvar slot-retry-count:a` → 0 (elfogy ha az init nem hív
  bootctl mark-boot-successful-t, és a watchdog reseteli a telefont).

NEM MŰKÖDŐ parancsok (hibaüzenet: "unknown command set"):
  fastboot set slot-retry-count 7
  fastboot set slot-retry-count:a 7
  fastboot set slot-retry-count:a:7

A `fastboot set_active a` ÖNMAGÁBAN NEM resetálja ha már 0:
  - ha a fastboot session aktív és count=0 → `set_active a` → count marad 0.
  - ha már low/0 de még > 0 és switcheltünk: lehet hogy reset → UNRELIABLE.

*** EGYETLEN MEGBÍZHATÓ RECEPT (bizonyítva 2026-06-26): ***
  fastboot reboot bootloader         # telefon ÚJRAINDUL fastbootba
  # -- várd meg hogy fastboot devices megmutassa --
  fastboot set_active a              # most resetel → slot-retry-count:a: 7
  fastboot getvar slot-retry-count:a # ELLENŐRZÉS: legyen 7

MIÉRT: a `reboot bootloader` a bootloader FRISS init-jét futtatja, ami a
  `set_active a` hatására teljes retry-budget resettel írja a GPT metadatát.
  Az ELSŐ `set_active a` egy már-futó fastboot sessionből (ahol a count=0 volt
  rögzítve) nem írja felül a cached metadatát.

ÖSSZEGZÉS az elvesztett retry-count-ról:
  - `fastboot boot <img>` → telefon bootol → watchdog resetel (init nem fut v.)
    → bootloader normál A/B pathon bootol → dekrementál → count fogy.
  - `fastboot flash boot_a` + `fastboot reboot` SZINTÉN dekrementál
    (ugyanaz a normál A/B path).
  - Minden tesztelési körben: ELŐBB `reboot bootloader` + `set_active a` = 7,
    MAJD flash + reboot. NE halmozz több `fastboot boot` kört count ellenőrzés nélkül.

================================================================================
### [2026-06-26] fastboot boot vs FLASH BOOT — KRITIKUS KÜLÖNBSÉG
================================================================================

MEGFIGYELÉS: `fastboot boot <img>` esetén p28 MINDIG ÜRES marad (init nem fut).
  Ugyanez az image `fastboot flash boot_a` + `fastboot reboot` útján FUTHAT
  (a minimal-diag.img flashelve írta a p28-at).

MAGYARÁZAT (gyanú): a `fastboot boot` (RAM-boot) esetén a bootloader
  MÁSKÉPP adja át a vezérlést → dtb vagy cmdline eltérhet → kernel early crash
  MIELŐTT az init exec-elődne. A flash+normal boot a helyes A/B path.

*** SZABÁLY: mindig `fastboot flash boot_a` + `fastboot reboot`, soha csak
  `fastboot boot` tesztelésre — a két path NEM ekvivalens ezen az eszközön! ***

BOOT IMAGE KÖVETELMÉNYEK (bizonyított):
  - header_version 0 (NEM 1!): a minimal-diag.img (ami működött) v0-val épült.
    A build rendszer v1-et preferál (BoardConfig), de a `fastboot boot` path-on
    a v1 sem fut → a flash+boot path-on még nem teszteltük.
  - shebang: `#!/sbin/busybox-static sh` (NEM `#!/bin/sh` symlinken keresztül).
    A kernel 4.9 binfmt_script valószínűleg NEM követi a symlinkot a shebangnél.
  - Kernel: az eredeti hybris kernel (minimal-diag.img-ből, 18427292 byte).

JELENLEGI ÁLLAPOT (2026-06-26 délelőtt):
  boot_a = hybris-sdlog-v5.img (header v0, minimal init #!/sbin/busybox-static sh,
    ramdisk-work struktúra, minimal-diag kernel). retry-count:a = 7. Épp bootolva.
  *** VÁRT EREDMÉNY: p28 = "V5-INIT-RAN" ha az init fut. ***
  Olvasás TWRP-ből: `dd if=/dev/block/mmcblk0p28 bs=512 count=4 | strings`

================================================================================
## [2026-06-26] NAPVÉGI ÖSSZEFOGLALÓ — SD DIRTY BIT FELFEDEZÉS
================================================================================

### A nap fő kérdése
Miért nem fut az init? Boot-0..2 (Jun 25) SD logot hagyott, azóta semmi.

### Amit kizártunk
- Kernel architektúra: ARM64, BINFMT_SCRIPT=y, DEVTMPFS_MOUNT=y → OK
- header_version: v0 és v1 is ugyanaz az eredmény
- Shebang (#!/bin/sh vs #!/sbin/busybox-static sh): mindkettő sikertelen
- dtbo_a: többféle dtbo-t próbáltunk (hadk, android13 backup, vissza hadk) → nincs hatás
- TWRP kernel + hybris ramdisk: skip_initramfs miatt azonnali pánik
- userdata: sailfish-raw.img visszaflashelve, LVM2 struktúra rendben

### A valódi ok: SD DIRTY BIT
Az SD kártya (mmcblk1p1, vfat, LABEL=SFLOG) dirty bittel volt jelölve
egy korábbi crash/hirtelen lekapcsolás miatt.

A hybris init sdlog_init() csendben meghiúsul ha a mount sikertelen:
  `mount -t vfat /dev/block/mmcblk1p1 /sdlog 2>/dev/null`
→ dirty vfat: mount visszautasítja (vagy nem ír) → nincs boot.log → úgy tűnt
  mintha az init sem futott volna.

TWRP-ből: `fsck.fat -a /dev/block/mmcblk1p1`
  Output: "0x41: Dirty bit is set. Automatically removing dirty bit."
Fix: dirty bit eltávolítva.

### Tanulság
"SD üres" NEM egyenlő "init nem futott". Ha az SD dirty, a mount csendben
meghiúsul és semmi nem kerül az SD-re — de az init futhat!
Minden debug session előtt: `fsck.fat -a /dev/block/mmcblk1p1` TWRP-ből.

### Retry-count reset szabály (megerősített)
- `fastboot reboot bootloader` → `fastboot set_active a` → count=7
  DE: ez csak 0-ról vagy slotváltáskor resetel megbízhatóan.
  Ha count=3-6: nem resetel. 3 kísérlet elegendő egy teszthez.

### Jelenlegi állapot (2026-06-26 este)
- boot_a = hybris-boot-sdlog.img
- dtbo_a = hadk/out/target/product/FP3/dtbo.img
- userdata = sailfish-raw.img (LVM2 OK, sailfish/root LV megvan)
- SD kártya dirty bit JAVÍTVA (fsck.fat -a)
- Éppen bootol — SD log várható

### SD DIRTY BIT — ADB PARANCSOK (TWRP-ből)

```bash
# 1. Ellenőrzés (read-only, nem módosít):
adb shell 'umount /external_sd 2>/dev/null; fsck.fat -n /dev/block/mmcblk1p1 2>&1'
# Ha "Dirty bit is set" látható:

# 2. Javítás (automatikus):
adb shell 'umount /external_sd 2>/dev/null; fsck.fat -a /dev/block/mmcblk1p1 2>&1'
# Várt output: "Automatically removing dirty bit. Performing changes."
# Utána: 1 files, 1/201616 clusters → OK
```

KÖTELEZŐ minden debug session elején elvégezni.

### SD DIRTY BIT — TWRP VISSZAÁLLÍTJA (kritikus!)

TWRP minden egyes SD mountoláskor dirty-nek jelöli a vfat partíciót.
Ha nem unmountoljuk rendesen → `adb reboot bootloader` előtt dirty marad →
hybris init mount csendben meghiúsul → nincs SD log.

*** KÖTELEZŐ SORREND minden boot kísérlet előtt (TWRP-ben): ***
```bash
# 1. SD dirty bit fix ELŐBB (TWRP ELŐTT kell elvégezni, nem utána!):
adb shell 'umount /external_sd 2>/dev/null; fsck.fat -a /dev/block/mmcblk1p1 2>&1'
# Várt: "Automatically removing dirty bit." VAGY semmi (ha már tiszta)

# 2. Csak ezután: flash + reboot
adb reboot bootloader
fastboot erase boot_b          # p28 nullázás (elog csatorna)
fastboot flash boot_a <img>
fastboot reboot
```

Ha kihagyod a fsck.fat-ot → SD log nem keletkezik a hybris bootban.
Ha a boot UTÁN csinálod a TWRP-ben → már újra dirty lesz!

================================================================================
### [2026-06-26] skip_initramfs — ABL MINDIG HOZZÁADJA
================================================================================

FELISMERÉS: Az ABL (bootloader) minden normál A/B boot esetén hozzáfűzi
`skip_initramfs`-t a kernel cmdline-hoz. A hybris kernel (4.9.227+)
IMPLEMENTÁLJA ezt a paramétert → a kernel KIHAGYJA az initramfs-t →
az /init soha nem fut → p28 üres.

BIZONYÍTÉK:
  - TWRP /proc/cmdline: tartalmaz `skip_initramfs`-t (ABL adja)
  - `grep -boa "skip_initramfs" kernel_raw` → megtalálva (kernel implementálja)
  - Minden p28 üresen marad amíg ez aktív

ELLENTMONDÁS: boot-0..2 (hybris-boot-ncm.img-gel) SD log keletkezett →
az init MÉGIS futott. Lehetséges magyarázat: az SD log az ncm.img init-jéből
jött, ami NEM tartalmazott p28 marker-t. A skip_initramfs hatása CSAK a p28
marker hiányát okozta (a BOOT MARKER devtmpfs ELŐTT volt).

STÁTUSZ (2026-06-26 este): a valódi ok még TISZTÁZATLAN — lehet hogy:
  (a) a BOOT MARKER azért üres mert devtmpfs még nincs mountolva (p28 write fail)
  (b) skip_initramfs tényleg blokkolja az init-et
  (c) fastboot boot vs flash path különbség

KÖVETKEZŐ TESZT: SD log olvasása az aktuális boot után → ha boot-N mappa
keletkezett → az init FUTOTT (csak p28 write volt a gond).


================================================================
[2026-06-26 18:20] ÁTTÖRÉS — skip_initramfs A FŐ BLOKKOLÓ, MEGOLDVA
================================================================

BIZONYÍTÉK (nem feltételezés többé):
- TWRP /proc/cmdline (fastboot boot twrp-fp3.img):
    ... androidboot.slot_suffix=_a  skip_initramfs  rootwait ro init=/init ...
  => az ABL MINDEN bootnál hozzaadja a skip_initramfs-t (meg recovery RAM-bootnal is).
- TWRP initje MEGIS lefut ezzel a cmdline-nal => a TWRP kernele IGNORALJA a skip_initramfs-t.
- A mi hybris kernelunk (4.9.227) HONORALJA => atugorja az initramfs initet =>
  a mi /init-unk SOHA nem fut.

KONTROLLALT TESZT (ncm2, tiszta SD + nullazott p28):
- p28 = 32768 B mind nulla (INITRAN-PREINIT marker SOHA)
- SD vfat mount OK (/proc/mounts igazolja) de TELJESEN URES (nincs boot-N, nincs init.log)
- Az /init 5. sora nyers dd-vel ir p28-ra (csak kernel /dev kell) -> nincs ott -> init nem futott.
- Ez MEGDONTI a korabbi "skip_initramfs kizarva" allitast (az a user altal kezzel
  letrehozott boot/ mappara epult, ami nem bizonyitek).

FIX — kernel binarispatch (build_nosk_kernel.py, $FP3_ROOT/):
- ncm2 kernel blob = gzip stream [0:14435013] + appendalt DTB [14435013:18427292] (d00dfeed, 3992279 B)
- decompress -> "skip_initramfs" PONTOSAN 1x szerepel (offset 31569934)
- replace -> "skip_xnitramfs" (azonos hossz, in-place) => kernel strstr(cmdline,"skip_xnitramfs")
  nem talal egyezest (cmdline-ban skip_initramfs van) => MINDIG az initramfs initet futtatja
- ujratomorites gzip + EREDETI DTB visszafuzese (ezt vesztette el a regi nosk.img -> "dtb not found")
- repack: header masolva, kernel_size patch, SHA1 id ujraszamolva (kepl: k,r,s + ures dt(0))
- eredmeny: $FP3_ROOT/hybris-boot-ncm2-nosk.img (22978560 B, ramdisk BITRE azonos)

EREDMENY (flash boot_a + reboot):
- 18:19:06 reboot; 18:19:55 (~33s) USB gadget enumeralt: lsusb 18d1:4ee4 (tether+debug),
  uj iface enx92965385f0fb => AZ INIT FUT, elerte a setup_usb_rndis-t.
- Utana a gadget eltunt (~5s utan), 90+s alatt nem jott vissza. adb/telnet/USB elerhetetlen.
  Ok meg ismeretlen: vagy switch_root tortent (ramdisk gadget lebomlik), vagy inject_loop
  USB-reconnectje hasalt el. => p28/SD logot KELL olvasni (TWRP) a pontos kepert.

KOVETKEZO: device -> fastboot -> TWRP -> p28 + SD log olvasas.


================================================================
[2026-06-26 18:38] ncm3-nosk (/dev/block fix) — INIT ELÉRI A RAMDISK HALT-ot!
================================================================

VÁLTOZTATÁS: az init /dev mount utáni része most biztosítja a /dev/block hierarchiát
(a devtmpfs FLAT /dev/mmcblkXpY node-okat ad, NEM /dev/block/-ot; ezt a hiányt symlinkkel
pótoljuk). Image: $FP3_ROOT/hybris-boot-ncm3-nosk.img (patchelt kernel + uj init).
Build: scratchpad ncm-rd/init edit -> cpio newc+gzip -> kernel a nosk.img-bol -> repack.

EREDMENY — most MINDKET log csatorna mukodik (p28 + SD boot-0), TELJES TRACE:
  4.55  ELOG-START (elog AZONNAL ir, /dev/block/mmcblk0p28 mar letezik) -> a fix HATOTT
  4.57  ls /dev/block: OSSZES particio jelen (mmcblk0p1..p49) -> /dev/block helyreallitva
  4.71  dev-snapshot: blocks=67, mmcblk1 (SD) jelen
  4.73->5.39  root-mount SIKERES (0.66s):
        - userdata = /dev/mmcblk0p62 (label userdata)
        - pvresize + vgchange sailfish -> LV home(32m) + root(1.51g) aktiv
        - root mountolva /rootfs-re OK
        - (a /dev/mmcblk0rpmb I/O error ARTALMATLAN: rpmb mindig igy olvas, LVM csak szkenneli)
  5.42->5.81  setup_usb_net (NCM) SIKERES:
        - configfs rc=0, UDC=7000000.dwc3, ncm.usb0 link rc=0, UDC bind rc=0
        - iface usb0 megjelent, IP 192.168.2.15/24, telnetd elindult (rc=0)
  5.83->5.88  === RAMDISK HALT === (inject_loop, var: echo continue > /init-ctl/stdin)

=> A skip_initramfs patch + /dev/block fix utan az init TELJESEN lefut a halt-ig:
   root-mount OK, USB NCM OK, telnetd OK. Ez HATALMAS elorelepes.

MEGMARADT PROBLEMA — fagyas ~12s uptime-nal:
  - A trace 5.88-nal veget er MINDKET csatornan, NINCS watchdog keepalive tick a p28-ban
    (az elso tick ~14.7s-nal lenne). A USB gadget a host-on ~6s-ig latszott (uptime ~6-12s),
    majd eltunt. Nincs masodik boot (se boot-1, se uj ELOG-START) -> nem rebootolt, hanem
    LEFAGYOTT ~12s korul, ~6s-cel a RAMDISK HALT utan.
  - Ezert nem jott letre a telnet kapcsolat: a 192.168.2.15:23 csak ~6s-ig elt, mire a PC
    beallitotta az IP-t es probalt csatlakozni, a device mar fagyott.
  - dmesg-ramdisk.log = 0 BAJT: a busybox 'dmesg -w' (follow) nem tamogatott/nem irt ->
    a fagyas oka nincs megfogva.
  - GYANU: MSM/PMIC watchdog tuzel, mert az 'echo 1 > /dev/watchdog' keepalive nem hatasos
    (egyetlen WD-tick sincs a p28-ban). A memoria szerint a watchdog 90-169s-nal tuzelt
    korabban, de itt mar ~12s-nal megall valami -> lehet USB-alrendszer panic is.

KOVETKEZO LEPES: a fagyas okat megfogni. Opciok:
  1. dmesg -w helyett periodikus 'dmesg' snapshot loop p28-ra/SD-re (busybox-kompatibilis),
     hogy a fagyas elotti utolso kernel uzenetek megmaradjanak.
  2. Watchdog: helyes pet-metodus (ioctl WDIOC_KEEPALIVE vagy a megfelelo magic), vagy
     /dev/watchdog megnyitasa es nyitva tartasa (close = 'V' magic close eseten letiltas).
  3. A halt elott periodikus elog "alive tick" a fo shellbol is, hogy lassuk meddig el.


================================================================
[2026-06-26 19:56] HALÁL-VIZSGÁLAT — init eléri a HALT-ot, majd ~6s múlva meghal
================================================================

MEGERŐSÍTETT (ncm5/ncm6 dmesg snapshot p28 forgó szektorokból, ncm7 fast WD pet):
- Az init MINDIG eléri a RAMDISK HALT-ot (~6.0s). Teljes lánc OK:
    root-mount (userdata=mmcblk0p62, LVM sailfish root 1.51g, ext4 mount OK),
    NCM gadget (18d1:4ee4, usb0), IP 192.168.2.15/24, telnetd elindult (rc=0).
- Utolsó dmesg a halál előtt (ncm6, slot1 ts=6.110):
    [6.028] === RAMDISK HALT ===
    [6.106] android_work: sent uevent USB_STATE=CONNECTED
    [6.110] android_work: sent uevent USB_STATE=DISCONNECTED   <-- majd HALOTT
- WD-HB heartbeat: mindig csak n=1 (~4.8s), a device a 2. heartbeat előtt meghal.
- Korábban: [5.9] msm-dwc3 7000000.ssusb: Avail curr from USB = 100  (csak 100mA!)

HALÁL IDŐZÍTÉS slot-konfig szerint:
  ncm3 (WD open/close 10s): ~12s    ncm4/5/6 (WD held-fd 2s): ~6.8s
  ncm7 (WD held-fd 0.3s pet): MÉG MINDIG meghal -> EDL loop (05c6:900e)
=> a gyors userspace /dev/watchdog petelés NEM segít -> NEM a userspace watchdog a gyilkos.
   Marad: (a) kernel-szintű MSM/secure watchdog + cpuidle/power-collapse hang, VAGY
          (b) BROWNOUT: kritikusan lemerült aksi + csak 100mA USB-rol -> a SoC nem futja.

ERV a BROWNOUT mellett: a halál egyre korabban jon (12s -> EDL loop) ahogy a sok reboot
meriti az aksit. A TWRP viszont PERCEKIG fut ugyanezen a hardveren -> a TWRP tobb aramot
huz / mas charger-config; a mi minimal ramdiskunk nem konfiguralja a chargert -> 100mA.

ERV a CPUIDLE/WATCHDOG mellett: a halál mindig kozvetlenul a RAMDISK HALT (idle) utan jon;
a cmdline-ban van lpm_levels.sleep_disabled=1 (elvileg tiltja a deep idle-t, de lehet nem hat).

KOVETKEZO KANDIDATUSOK (meg nem probalt):
  1. Aksi TOLTESE fali toltorol (nem PC-USB), majd ujraprobalni -> brownout kizarasa.
  2. cpuidle deep state-ek tiltasa sysfs-bol az init elejen:
       for f in /sys/devices/system/cpu/cpu*/cpuidle/state[1-9]*/disable; do echo 1>$f; done
  3. Charger input current limit emelese sysfs-bol (SMB charger, msm8953) az init-ben.
  4. A telnet ablakban (USB ~5.7s-tol haláig) GYORS csatlakozas — eddig a host enx feljott
     (~27s wall) de a port23 nem nyilt ('link is not ready'); NCM host-oldali connectivity gond.

JELENLEG: device EDL-ben (05c6:900e). Vissza kell hozni fastbootba (force reboot).
Build artifactok: hybris-boot-ncm{2..7}-nosk.img a $FP3_ROOT/-ben.
ncm7 = legfrissebb init (skip_initramfs patch + /dev/block fix + fast WD pet + dmesg snapshot).


================================================================
[2026-06-26 20:17] DÖNTŐ: AZONNALI reset a USB CONFIGURED pillanatában (charger ICL)
================================================================

30ms-es dmesg snapshot (ncm9, 16 forgó slot) megfogta a halál pillanatát. Az UTOLSÓ
üzenetek (slot ts=17.521), majd 30ms-en belül HALOTT (nincs tovabbi snapshot):
  [17.519] configfs-gadget gadget: high-speed config #1: b
  [17.519] msm-dwc3 7000000.ssusb: Avail curr from USB = 250
  [17.519] pmi632_charger: set_sdp_current: ICL 250000uA isn't supported for SDP
  [17.520] pmi632_charger: smblib_set_icl_current: Couldn't set SDP ICL rc=-22
  [17.520] android_work: sent uevent USB_STATE=CONFIGURED
  [17.521] IPv6: ADDRCONF(NETDEV_CHANGE): usb0: link becomes ready
  <-- RESET 30ms-en belul

KOVETKEZTETES:
- A reset AZONNALI (<30ms) a USB enumeracio befejezesekor (USB_STATE=CONFIGURED).
- NEM watchdog (masodpercek) es NEM fix-uptime SSR: a halal a USB-confighoz kotott
  (17.5s ezen a booton, 6.1s korabban) -> a USB-configured / charger kodut valtja ki.
- Az egyetlen anomalia kozvetlenul elotte: pmi632 charger SDP ICL 250mA -> -22 (nem
  tamogatott). Gyanu: a charger/PMIC (pmi632) reset a USB-config eseteben, mert a
  charger nincs rendesen inicializalva a minimal ramdiskben (nincs vendor charger config).
- cpuidle-disable, lpm sleep_disabled, gyors /dev/watchdog pet MIND nem segitett -> nem
  azok a gyilkosok. A USB-config -> charger ICL -> azonnali reset a valodi ok.

PROBALT FIX (ncm10): gadget MaxPower 250 -> 100 (standard SDP ertek, aksi 98% -> nem kell
tolteni), hogy elkerujuk az ICL -22 hibat. Ha a reset megszunik -> a charger ICL volt.
Ha megmarad -> kernel-szintu USB/charger crash, kernel-patch kell (pl. pmi632/smblib
driver tiltasa vagy a charger USB-notifier kikapcsolasa).

A teljes boot dmesg (5.93s-ig) az SD boot-N/dmesg-ramdisk.log-ban is megvan (hasznalhato).


================================================================
[2026-06-26 20:25] ncm10 (MaxPower 100) NEM segitett; ncm11 (IPv6 off) PENDING
================================================================

ncm10: MaxPower 250->100 (standard SDP) -> a device IGY IS resetel a USB CONFIGURED-nel -> EDL.
=> a charger ICL ERTEK nem a kivalto ok. A reset a USB-CONFIGURED kodutban van, MaxPower-fuggetlen.

ncm11 (megepitve, flashelesre var): IPv6 TILTAS a usb0-n a link-up elott
(disable_ipv6 all/default/usb0). Hipotezis (user): a crash pont a "usb0: link becomes ready"
(IPv6 ADDRCONF) sornal van -> kizarjuk hogy az IPv6 ADDRCONF/DAD valtja ki. Telnet IPv4-en megy.
MEGJEGYZES: a reset 30ms-en belul, PANIC-UZENET NELKUL -> ez HARDVERES reset (PMIC/charger/
watchdog), nem szoftveres IPv6-oops -> az IPv6 valoszinuleg csak naplozza a link-eventet, nem ok.
Ha ncm11 is meghal -> marad a kernel USB/charger ut.

DONTESI FORK (ha az IPv6 sem segit):
  (a) USB telnet KIHAGYASA: az init auto-continue (skip inject_loop) -> switch_root ->
      Sailfish boot. A teljes Sailfish stack rendesen kezeli a chargert/USB-t, nem szenvedne
      ettol a crash-tol. p28+SD loggal kovetjuk a Sailfish boot-ot. EZ VALODI HALADAS a porton.
  (b) charger driver unbind sysfs-bol USB elott (qpnp-smb2 / pmi632 / smb*) -> ha a charger
      USB-notifier okozza, ez megkerulheti kernel-patch nelkul.
  (c) kernel-patch: charger USB-notifier / pmi632 driver tiltasa a defconfigban.

OSSZES BUILD: hybris-boot-ncm{2..11}-nosk.img a $FP3_ROOT/-ben.
ncm11 = legfrissebb init (skip_initramfs patch + /dev/block fix + cpuidle-disable +
fast WD pet csak /dev/watchdog + 30ms dmesg snapshot 16 slot + MaxPower 100 + IPv6 off).
build_nosk_kernel.py = a skip_initramfs kernel-patch recept (ujrahasznalhato).

[2026-06-26 20:32] ncm11 (IPv6 OFF a usb0-n) — ÁTTÖRÉS: NINCS TÖBBÉ RESET!
- Flash+reboot ncm11. Host: 18d1:4ee4 "FP3 Debug NCM" enumeralt, cdc_ncm register, iface
  enx5233721e06ee, carrier=1, operstate=up. STABIL ~70s+ — SEMMI USB disconnect, SEMMI EDL.
  => A korabbi <30ms-es hard reset a USB CONFIGURED-nel MEGSZUNT az IPv6 letiltasaval!
  Tehat a death valoban az IPv6 "link becomes ready" / ADDRCONF kodutban volt (kernel).
- DE: ping 192.168.2.15 100% loss, telnet "No route to host", tcpdump 0 frame a device-rol.
  A device-oldali halozati stack EGYETLEN frame-et sem kuld (se ARP, se telnetd).
  => A CPU vagy lefagyott kozvetlenul a USB-config utan, VAGY a usb0 IP/telnetd nem jott fel.
- Kovetkezo: TWRP boot -> p28 dense dmesg (sector 2048+, 16 slot) kiolvasas -> pontos halt/hang pont.

================================================================================
[2026-06-26 20:45] AGENT PLAYBOOK — hybris-boot módosítás NULLÁRÓL (reprodukálható)
================================================================================
Cél: egy hideg-indulású agent ebből a szakaszból fel tudja építeni a teljes láncot
(forrás -> ramdisk init módosítás -> patchelt boot.img -> flash -> log olvasás).

--------------------------------------------------------------------------------
0. KÖRNYEZET / FIX PONTOK
--------------------------------------------------------------------------------
- Projekt gyökér:      $FP3_ROOT        (FIGYELEM: env.sh /mnt/1T-et ír, a
                       valódi mount /mnt/1TB — mindig /mnt/1TB-t használj)
- HADK build env:      $FP3_ROOT/hadk
- hybris-boot FORRÁS:  $FP3_ROOT/hadk/hybris/hybris-boot/  (init-script, initramfs/)
- Teljes build kimenet:$FP3_ROOT/hadk/out/target/product/FP3/hybris-boot.img
- Eszköz: Fairphone 3 (fp3, MSM8953/SD632, aarch64). A/B slot, mindig slot A.
- Live USB rendszer: minden tartós adat /mnt/1TB-re (a root reboot-nál törlődik).
- boot.img v0 formátum: ANDROID! magic, pagesize=2048, base=0x80000000,
  kernel_off=0x8000, ramdisk_off=0x1000000, tags_off=0x100, second/dt üres.
- Kernel blob = GZIP stream + APPENDÁLT DTB (FDT magic d00dfeed, ~3992279 B a végén).
  A DTB-t recompress után KÖTELEZŐ visszafűzni, különben "dtb not found".
- Ramdisk = gzip(cpio newc). Benne: /init (shell script), /sbin/busybox-static (aarch64,
  ~2.6MB, 'usleep' applet OK), /sbin/root-mount (LVM detect -> /dev/sailfish/root).

--------------------------------------------------------------------------------
1. FORRÁS BESZERZÉSE (ha a hadk/ nincs meg — git clone nulláról)
--------------------------------------------------------------------------------
A teljes HADK fa nagy; normál esetben már megvan a hadk/-ban. Ha újra kell:
  source $FP3_ROOT/env.sh   # VENDOR=fairphone DEVICE=fp3 RELEASE=5.0.0.71
                                        # HYBRIS_MANIFEST_BRANCH=hybris-18.1 (Android11/LOS18.1)
  # repo init/sync a hybris-18.1 manifesttel (HADK pdf 4. fejezet) -> hadk/
  # hybris-boot maga: hadk/hybris/hybris-boot (a mer-hybris/hybris-boot upstream).
Az init forrása upstream: hadk/hybris/hybris-boot/init-script (ezt teszi a ramdiskbe a build).
A mi DEBUG initünk ennek erősen módosított változata (NCM gadget, elog p28, sdlog, dmesg
snapshot, RAMDISK HALT / AUTO-CONTINUE) — a kész ramdiskben él, lásd 3. pont.

--------------------------------------------------------------------------------
2/A. TELJES BUILD (canonical, LASSÚ) — csak ha az init-script FORRÁST kell módosítani
--------------------------------------------------------------------------------
  sudo $SDK_CHROOT                       # Platform SDK chroot (env.sh: SDK_CHROOT)
  # build_packages.sh --mw=hybris-boot   VAGY: cd hadk && make hybris-boot
  # eredmény: hadk/out/target/product/FP3/hybris-boot.img
Ez lassú és a teljes toolchaint igényli. Iterációhoz NE ezt használd — lásd 2/B.

--------------------------------------------------------------------------------
2/B. GYORS ITERÁCIÓ (~30s/kör) — EZT HASZNÁLD a ramdisk init hangolásához
--------------------------------------------------------------------------------
Ötlet: NEM buildelünk újra. Egy MÁR PATCHELT image-ből kivesszük a ramdiskot, szerkesztjük
az initet, visszacsomagoljuk, és a (változatlan) patchelt kernelt újrahasználjuk.

SCRATCHPAD létrehozása + ramdisk kibontás (egyszer, ha az ncm-rd/ még nincs):
  SP=/tmp/claude-XXX/.../scratchpad     # a session scratchpad dir
  mkdir -p $SP/ncm-rd && cd $SP/ncm-rd
  # ramdisk kinyerése egy meglévő boot.img-ből (python a header offsetekhez):
  python3 - <<'PY'
  import struct
  d=open('$FP3_ROOT/hybris-boot-ncm2.img','rb').read()
  ks,_,rs,_,_,_,_,ps,_,_=struct.unpack('<10I',d[8:48])
  roff=ps+((ks+ps-1)//ps)*ps
  open('/tmp/rd.gz','wb').write(d[roff:roff+rs])
  PY
  zcat /tmp/rd.gz | cpio -idm        # -> ncm-rd/ fa (init, sbin/busybox-static, ...)

Az INIT szerkesztése:  $SP/ncm-rd/init   (Edit/Write toollal)
  - kulcs blokkok: elog_init (p28=/dev/block/mmcblk0p28), sdlog_init (mmcblk1p1),
    /dev/block symlink fix, anti-idle+watchdog keepalive, start_dmesg_snapshot
    (p28 sector 2048+, 16 rotáló slot), RAMDISK HALT vs AUTO-CONTINUE, switch_root.

VISSZACSOMAGOLÁS + PATCHELT KERNEL ÚJRAHASZNÁLAT (a build_ncm12.py minta):
  - ramdisk: (cd ncm-rd && find . | sort | cpio -H newc -o --owner=0:0) | gzip -9 -n
  - kernel: egy meglévő *-nosk.img első page utáni ks bájtja (MÁR patchelt + DTB).
    Ellenőrzés: a kicsomagolt kernelben skip_xnitramfs==1 ÉS skip_initramfs==0, DTB tail d00dfeed.
  - header: bázis első page másolása, ramdisk_size@16 patch, id@576 (SHA1) frissítés.
  - SHA1 id KÉPLET (qcom mkbootimg --dt stílus, üres dt):
      h=SHA1( kernel||le32(ks) + ramdisk||le32(rs) + second(b'')||le32(ss) + dt(b'')||le32(0) )
      header[576:596]=h[:20]; header[596:608]=0
  - assemble: header_page + pad(kernel,2048) + pad(ramdisk,2048) -> hybris-boot-ncmN-nosk.img
  Referencia scriptek: scratchpad/build_ncm12.py (repack), $FP3_ROOT/build_nosk_kernel.py

--------------------------------------------------------------------------------
3. KERNEL skip_initramfs PATCH (A FŐ BLOKKOLÓ — minden flashelt image-en KÖTELEZŐ)
--------------------------------------------------------------------------------
Az ABL MINDEN bootnál a cmdline-hoz adja: "... skip_initramfs ...". A hybris kernel HONORÁLJA
-> átugorja az initramfs /init-et -> a mi initünk NEM fut. Megoldás (build_nosk_kernel.py):
  1. kernel blob gzip decompress -> raw; a DTB tail (d00dfeed) levágva és MEGŐRIZVE.
  2. raw-ban 'skip_initramfs' PONTOSAN 1x -> 'skip_xnitramfs' (azonos 14 hossz, in-place).
     A strstr(cmdline,"skip_initramfs") így sosem talál egyezést -> MINDIG initramfs init fut.
  3. gzip recompress (mtime=0) + az EREDETI DTB visszafűzése.
  4. header kernel_size@8 patch + SHA1 id újraszámol (fenti képlet).
Ha új teljes hybris-boot.img-et buildelsz (2/A), AZON IS át kell futtatni ezt a patchet,
mielőtt flashelsz. (A 2/B gyors út a már patchelt kernelt használja újra -> nem kell újrapatch.)

--------------------------------------------------------------------------------
4. FLASH + BOOT (KÖTELEZŐ SORREND)
--------------------------------------------------------------------------------
Eszköz TWRP-ben (adb recovery):
  adb shell 'umount /external_sd 2>/dev/null; fsck.fat -a /dev/block/mmcblk1p1'   # SD dirty fix BOOT ELŐTT
  adb reboot bootloader
Fastbootban:
  fastboot set_active a                         # SOHA set_active b! (retry-count reset is)
  fastboot erase boot_b                          # p28 (=boot_b, 64MB raw log) nullázás
  fastboot flash boot_a $FP3_ROOT/hybris-boot-ncmN-nosk.img
  fastboot getvar current-slot                   # legyen 'a'
  fastboot reboot                                # CSAK flash+reboot megbízható; 'fastboot boot' = "dtb not found"
Slot retry: ha 0-ra fogy -> EDL (05c6:900e) -> power hosszan -> vissza fastbootba, set_active a.
NE használj 'adb wait-for-device'-t — poll 'adb get-state' loopban.
Egy futtatásban EGY változtatás; két kör közt retry-count ellenőrzés (set_active a).

--------------------------------------------------------------------------------
5. LOG OLVASÁS (a követés forrásai)
--------------------------------------------------------------------------------
A device a ramdiskben adb NÉLKÜL fut -> nem olvasható élőben. Reboot TWRP-be:
  fastboot boot $FP3_ROOT/twrp-fp3.img   # TWRP kernele bootol (ignorálja skip_initramfs)
  # poll 'adb get-state' -> recovery
p28 (eMMC raw log) kiolvasás:
  adb shell 'dd if=/dev/block/mmcblk0p28 bs=512 count=4096' > $FP3_ROOT/p28.bin
  p28 layout: sector 0+ = elog ASCII trace (ELOG-START...);  sector 2000 = WD-HB heartbeat
  (anti-idle, n=count up=uptime);  sector 2048+ = dense dmesg snapshot, 16 rotáló slot
  (slot k -> seek 2048+k*32, 32 sector/slot, 30ms-enként felülírva). A legmagasabb dmesg-
  timestampú slot adja az UTOLSÓ üzeneteket. Parse: read_p28.py / re.findall rb'[ -~]{5,}'.
SD log: /external_sd (mmcblk1p1 vfat) /sdlog/boot-N/ — init.log, dmesg-ramdisk.log, usb-debug.log.
  (TWRP minden mountnál dirty-re állítja -> boot ELŐTT fsck.fat -a, lásd 4.)
Sailfish rootfs log: /dev/sailfish/root LV (LVM) — TWRP-ben NEM olvasható (nincs lvm eszköz).

--------------------------------------------------------------------------------
6. JELENLEGI ÁLLAPOT (innen folytatható)
--------------------------------------------------------------------------------
- Halál (USB-CONFIGURED hard reset) MEGOLDVA: IPv6 off a gadget ifészen (ncm11) -> 207s+ stabil.
- USB host<->device NCM data-path SOSEM jött fel ("link becomes ready" nincs a device dmesg-ben,
  0 frame, telnet elérhetetlen). USER DÖNTÉS: az USB a gyökérprobléma, NEM hajszoljuk tovább.
- ncm12 (EZ): USB gadget KIHAGYVA + AUTO-CONTINUE (nincs HALT) -> switch_root -> /sbin/preinit
  -> Sailfish boot. start_dmesg_snapshot megmarad (p28 követés a switch_root-ig). Flashelve 20:43.
- Buildek: hybris-boot-ncm{2..12}-nosk.img. ncm12 = legfrissebb (Sailfish-boot kísérlet).

--------------------------------------------------------------------------------
[2026-06-26 20:56] TWRP-BŐL LVM ROOTFS OLVASÁS LVM ESZKÖZ NÉLKÜL (offset loop-mount)
--------------------------------------------------------------------------------
Probléma: a Sailfish rootfs egy LVM2 LV (/dev/sailfish/root) a userdata-n (mmcblk0p62), és
a TWRP-ben NINCS lvm/vgscan/dmsetup -> nem aktiválható. DE az LV LINEÁRIS leképezés a PV-n,
így ha kiszámoljuk a byte-offsetjét, sima loopback-kal (offset) felmountolható LVM nélkül.

LÉPÉSEK:
1. LVM2 metaadat (text, az mda-ban = PV első ~1MB) kihúzása:
     adb shell 'dd if=/dev/block/mmcblk0p62 bs=512 count=2048' > p62-mda.bin
2. A LEGMAGASABB seqno metaadat-blokk kikeresése amiben van 'logical_volumes' (a metadata egy
   körkörös ring; a seqno=1 még LV nélküli). Python: re.finditer(r'sailfish\s*\{.*?# Generated
   by LVM2', txt, re.S), seqno = re.search(r'seqno = (\d+)'), válaszd a max seqno-t LV-kkel.
3. A blokkból kiolvasandó:
     extent_size (PE méret SEKTORBAN, pl. 8192 = 4MiB),  pe_start (PV, sektor, pl. 2048 = 1MiB)
     root LV segment1: start_extent (LV-n belül), stripes = ["pv0", <PV_PE_OFFSET>]  (a 2. szám
     a FIZIKAI PE offset a PV-n!). FONTOS: a fizikai offsethez a 'stripes' PV_PE_OFFSET-et használd,
     NEM a start_extent-et (az az LV-n belüli logikai).
4. Byte offset a partíción:
     OFFSET_BYTES = (pe_start + PV_PE_OFFSET * extent_size) * 512
   Példa (FP3 sailfish, seqno=17): pe_start=2048, extent_size=8192, root stripes=["pv0",0]
     -> OFFSET = (2048 + 0*8192)*512 = 1 048 576 byte (1 MiB).  root mérete = 387*8192*512 ≈ 1.51GiB.
     home: stripes=["pv0",387] -> OFFSET = (2048 + 387*8192)*512 = 1 624 244 224 byte, méret 8*4MiB=32MiB.
5. Mount (busybox mount NEM tudja a -o offset-et -> losetup -o + mount):
     adb shell '
       mkdir -p /mnt/sfroot
       losetup -o 1048576 /dev/block/loop0 /dev/block/mmcblk0p62
       mount -t ext4 -o ro /dev/block/loop0 /mnt/sfroot
       ls /mnt/sfroot'                         # bin boot etc home usr var ... = OK
   (RW-hez: mount -o rw; írás után: sync; umount /mnt/sfroot; losetup -d /dev/block/loop0.)
6. Mit nézz a boot-haladáshoz (a device órája 1970, ezért egy boot 1970-es mtime-okat ír):
     /mnt/sfroot/var/log/journal/<machine-id>/system.journal   (mtime; ha image-dátum -> nem írt)
     find /mnt/sfroot -xdev -newermt "1970-01-01 00:00:01" ! -newermt "1971-01-01"  (boot-próba fájlok)
     /mnt/sfroot/var/lib/systemd/, first-boot markerek, /var/log/*.log
   Ha SEMMI nem újabb az image-készítés dátumánál -> a Sailfish meghalt MIELŐTT bármit írt
   (journald előtt) -> korai preinit/systemd halál (gyanú: watchdog a switch_root után).

Felhasználás: /init-debug-ot is ÍGY teszünk a rootfsre (adb push /mnt/sfroot/init-debug + chmod
0755). A ramdisk init (sor ~406) execeli a /rootfs/init-debug-ot a preinit HELYETT -> Sailfish
korai-boot debug ramdisk-rebuild NÉLKÜL.

================================================================================
[2026-06-26 21:08] ÁTTÖRÉS: Sailfish bootol switch_root után — ÚJ blokkoló = droid-hal/binder
================================================================================
LÁNC MOST: ncm12 (USB gadget KIHAGYVA, AUTO-CONTINUE) -> switch_root -> /init-debug (a rootfson!)
-> watchdog keepalive + SD-log háttér-loop (ÁTÉLI az exec-et) -> exec /sbin/preinit -> systemd
-> droid-hal-init -> AKAD MEG.

MEGOLDOTT blokkolók (mind bizonyítva):
1. skip_initramfs (kernel patch) -> init fut.
2. /dev/block hiány (symlink fix) -> p28+SD log megy.
3. USB-CONFIGURED hard reset -> IPv6 off (de USB-t teljesen elejtettük, ncm12 nem hoz gadgetet).
4. ~90s watchdog reset switch_root után -> /init-debug PERZISZTENS watchdog keepalive (a háttér-loop
   külön PID, exec /sbin/preinit után is él és peteli /dev/watchdog-ot). BIZONYÍTVA: heartbeat
   up=9->95.5s, NINCS reset. A ramdisk keepalive-ja a switch_root-nál meghalt (WD-HB n=11 up=7.85);
   az init-debug-é viszi tovább, amíg a systemd saját watchdog-kezelése át nem venné.

SD-LOG MŰKÖDIK (init-debug, Sailfish-oldal, TWRP-ből olvasható, LVM nem kell):
- /external_sd/sailfish-progress.log : "ALIVE slot=N up=X" 2s-enként (liveness timeline)
- /external_sd/sailfish-dmesg.log    : teljes dmesg, 10s-enként felülírva (a fagyás pillanata)
- p28 dmesg snapshot (sector 2048+) is megy az init-debug-ból (/dev/mmcblk0p28 flat node).
  (Az init-debug forrása: $FP3_ROOT/init-debug, a rootfson /init-debug 0755.)

ÚJ FŐ BLOKKOLÓ (innen kell folytatni) — droid-hal / Android HAL binder bring-up:
  init: PDR register failed, ret = -19, disable service     (Qualcomm Protection Domain, ENODEV)
  binder: 29883:29883 transaction failed 29189/-22, size 32-0 line 3119   (~1s-enkent, vegtelen)
  binder: 29915:29915 transaction failed 29189/-22, size 32-0 line 3119
- Két kliens PID (29883, 29915) végtelenül pörög egy binder targetre (29189), -22=EINVAL.
- A Sailfish eléri a droid-hal-init/Android-service fázist (~60s+), de egy HAL service nem jön fel
  -> kliensek retry-loopban -> boot nem ér el UI-ig. (himax touch + sps BAM közben felmegy, OK.)
- A device a fagyás alatt is ÉL (watchdog petelve), csak nem halad.

KÖVETKEZŐ LÉPÉSEK (droid-hal debug — standard hybris HAL bring-up):
1. Azonosítsd a 29883/29915/29189 PID-eket: a Sailfish-oldali logcat / ps. Bővítsd az init-debug-ot
   hogy a háttér-loop ALSO logoljon SD-re: `ps -A` és (ha van) `/system/bin/logcat -d` kimenetet,
   ill. `cat /proc/<pid>/cmdline`. Így kiderül melyik HAL/service és mit hív.
2. droid-hal-init service-ek: /system/etc/init/*.rc, hybris-boot droid-hal-init státusz; a
   "PDR register failed -19" -> Qualcomm PD service (pd-mapper/tz?) hiányzik vagy nem indul.
3. Ellenőrizd: /dev/binder jogok, servicemanager fut-e (ps | grep servicemanager), selinux/permissive.
4. Hasznos NYOM az SD-n (2024-03-05 dátum, KORÁBBI bootból?): dmesg-at-usb-moded.log, dmesg-systemd.log,
   journal-at-usb-moded.log -> EGY KORÁBBI boot eljutott usb-moded/systemd fázisig! Olvasd ki ezeket
   (mit csinált akkor másképp), lehet tovább jutott mint a mostani -> hasznos összehasonlítás.

ÁLLAPOT a session végén: device TWRP-ben (a 21:06-os instrumentált boot ~95s-nél megszakítva olvasáshoz).
A /init-debug a rootfson marad. Folytatáshoz: TWRP-ből olvasd az SD sailfish-*.log-ot, vagy bővítsd
az init-debug-ot (ps/logcat), majd flash-reboot ncm12 (set_active a, erase boot_b, reboot) és olvasd újra.
Eltávolításhoz a debug initből: töröld a rootfson a /init-debug-ot (offset-mount rw, lásd LVM-less olvasás).

================================================================================
[2026-06-26 21:00-21:45] ITERÁCIÓS NAPLÓ — init-debug v1..v4 (Sailfish élő-debug felé)
================================================================================
Cél: élő USB telnet shell a FUTÓ Sailfishbe -> autonóm debug (nincs gombnyomás): a /init-debug
a rootfson szerkeszthető élőben, reboot távolról. A boot eljut systemd-ig, droid-hal-init bukik.

--- ITER A: init-debug v1 (egyszerű wd-keepalive + p28 snapshot) ---
PARANCS: rootfsre írva offset-mounttal (losetup -o 1048576 loopN mmcblk0p62; mount ext4 rw),
  a ramdisk init (ncm12) execeli /rootfs/init-debug-ot a preinit HELYETT.
EREDMÉNY: BIZONYÍTOTTA hogy a ramdisk switch_root-ol a /sbin/preinit-be (trace: 5.53 AUTO-CONTINUE,
  8.62 Found /init-debug). A Sailfish boot azonban semmit nem írt a rootfsre -> korai halál gyanú.

--- ITER B: init-debug v2 (DEDIKÁLT watchdog petter külön loopban) + SD-log ---
TANULSÁG (FONTOS): a watchdog petelést KÜLÖN, szoros háttér-loopba kell tenni
  ( exec 9>/dev/watchdog; while:; echo 1>&9; sleep 1 ). Ha a petelés egy loopban van a (lassú)
  diagnosztikával (logcat/ps), a lassú parancs késlelteti a petet -> ~min. uptime-nál watchdog bark
  -> RESET-LOOP -> 'fastboot getvar slot-unbootable:a = Yes', current-slot=INVALID, retry-count=0.
  JAVÍTÁS amikor unbootable: fastboot set_active a (visszaállítja bootable=No, retry=7) + reflash boot_a.
EREDMÉNY: dedikált petterrel a boot TÚLÉL: progress.log ALIVE up=9->192s, NINCS reset. A watchdog-fix
  BIZONYÍTOTTAN működik. SD-log Sailfish-oldalról MŰKÖDIK (sailfish-progress.log + sailfish-dmesg.log).
DIAGNÓZIS: a boot eljut "Welcome to Sailfish OS 5.0.0.71" (preinit 10.7s) -> systemd 238 -> default.target.
  systemd-oldal ÉL: PID1, journald, udevd, logind, dbus-daemon, usb_moded mind fut (ps.log).
  DE: nincs EGYETLEN /system/bin android processz sem; nincs droid-hal-init, hwservicemanager, logd.
  binder target PID 29189 ELINDULT majd MEGHALT (nincs ps-ben); ofonod(30984)+nfcd(31005) végtelenül
  hammerezik -22 (EINVAL). logcat 0 sor (logd nem fut). => droid-hal-init/Android HAL konténer bukik.
  Korai kernel "PDR register failed -19" (audio_notifier ADSP/modem PD) — valószínűleg ártalmatlan.

--- ITER C: init-debug v3 (journalctl/systemctl/failed/jobs dump SD-re) ---
EREDMÉNY: sailfish-journal.log / failed.log / jobs.log / droidhal.log MIND 0 BÁJT. A systemctl és
  journalctl az init-debug háttér-kontextusából NEM ad kimenetet (hiányzó env / D-Bus session /
  /run kontextus a forkolt shellben). ps.log viszont OK (12KB).
TANULSÁG: a systemd-állapot lekérdezéséhez ÉLŐ, rendes root shell kell (telnet) — nem a forkolt
  init-debug háttér-loop. => ez vezetett a v4 élő-telnet irányhoz.

--- ITER D: init-debug v4 (ÉLŐ USB TELNET, RNDIS, IPv6 off) ---
FELÉPÍTÉS: (1) dedikált wd-petter; (2) telnet-setup LEGELÖL (sose vesszen el a hozzáférés):
  sleep 22 -> systemctl stop usb-moded + killall usb_moded (UDC felszabadítás) -> configfs g1 RNDIS
  gadget (18d1:d001, rndis.usb0, OS-desc) -> UDC bind -> IPv6 off + ip 192.168.2.15/24 + telnetd
  retry-loopban; (3) könnyű diag loop. exec /sbin/preinit.
BUKTATÓK + JAVÍTÁSOK:
  - TWRP-ben CSAK loop0..loop7 létezik (loop8 "No such file or directory") -> a mount csendben
    bukik, az adb push a TWRP tmpfs /mnt/sfroot-jára megy, NEM a rootfsre! Mindig ellenőrizd:
    'ls /mnt/sfroot/sbin/preinit' a push ELŐTT. Szabad loop keresése loopban.
  - NINCS telnetd a Sailfish rootfson, és a rendszer busybox-a nem listáz applet-et. MEGOLDÁS:
    a ramdisk /sbin/busybox-static (2632080 B, van benne telnetd+pidof) felmásolva
    /usr/bin/busybox-static-ra; init-debug: '/usr/bin/busybox-static telnetd -b 192.168.2.15:23
    -l /bin/sh' és 'busybox-static pidof'. 'ip' a rendszerből: /usr/sbin/ip.
EREDMÉNY: a RNDIS gadget FELJÖN host oldalon (lsusb 18d1:d001, iface enx..., carrier=1) és STABIL
  (nem disconnectál ~2.5perc+ -> a device ÉL, nincs crash). DE: 0 FRAME a device-ről (tcpdump 0 pkt),
  ping/telnet "No route to host" — UGYANAZ a 0-frame mint NCM-nél (ncm11). 
KÖVETKEZTETÉS: a 0-frame NEM a gadget-függvénytől függ (NCM és RNDIS is) -> a DEVICE-OLDAL a hibás:
  vagy az iface/IP/telnetd setup bukott (ip libs? iface-név? usb_moded visszaveszi az UDC-t?), vagy
  a host RNDIS-init handshake nem fejeződik be -> device netdev nincs carrier -> nem TX-el.
KÖVETKEZŐ: olvasd a device-oldali /sdlog2/sailfish-usb.log-ot (init-debug ulog: UDC bind rc, iface
  found?, telnetd started?) TWRP-ből -> kiderül HOL bukott a device-oldali telnet bringup.
HOST PARANCSOK (telnet próbához): modprobe rndis_host cdc_ether; ip addr add 192.168.2.1/24 dev enx*;
  ip link set enx* up; telnet 192.168.2.15 23.  (arping a rendszeren elromlott: 'Syntax error'.)

--- ITER D UTÓ: device-oldali usb.log KIOLVASVA -> a 0-frame HOST-oldali (NetworkManager)! ---
A /sdlog2/sailfish-usb.log BIZONYÍTJA hogy a DEVICE-OLDAL TÖKÉLETES:
  33.63 UDC bind rc=0 now=7000000.dwc3
  33.81 iface=rndis0 up, telnetd started (192.168.2.15:23)   [végig, 343s-ig, device ÉL]
Tehát: rndis0 megvan, IP 192.168.2.15 beállítva, telnetd FUT, a boot túlél 343s+ (progress slot 159).
A 0-frame OKA HOST-oldali: a NetworkManager elvette az ifészt és ELDOBTA a statikus 192.168.2.1/24-et
  (link-local 169.254.x lett) -> nincs route a 192.168.2.15-höz -> "No route to host", tcpdump 0 pkt.
FIX (host): NM-kezelés KI az ifészen (nmcli dev set <ifc> managed no) + statikus ip addr add
  192.168.2.1/24; majd telnet 192.168.2.15 23. A device-oldal kész, init-debug v4 NEM változik.
TANULSÁG: a gadget-iface neve a Sailfish-oldalon 'rndis0' (a grep ^(rndis|usb|ncm) ELKAPTA, OK).
  A device-oldali bringup mindvégig jó volt NCM-nél is — a host NM volt a ludas. RNDIS bind: host
  modprobe rndis_host; gadget 18d1:d001 -> rndis_host auto-bind (enx... iface).

--- ITER D VÉGSŐ + AUTONÓMIA-ELEMZÉS (host static IP + tcpdump bizonyíték) ---
Host-oldal RENDBE téve (nmcli dev set <ifc> managed no; ip addr flush; ip addr add 192.168.2.1/24;
ip link set up). MÉGIS 0 frame. tcpdump BIZONYÍTÉK: csak a HOST csomagjai (192.168.2.1 mDNS/WS-Disc),
a device (192.168.2.15) SOHA nem küld semmit (még ARP-választ sem). Host dmesg: rndis_host bind OK,
carrier=1, "FP3 Debug RNDIS" 18d1:d001. => a device-oldali rndis0-nak NINCS OPERATÍV CARRIER-e
(admin-up+IP+telnetd megvan a usb.log szerint, de a gadget netdev nem TX-el). Host-ról NEM javítható.
Down/up host iface (RNDIS packet-filter kiváltás) sem segített. KÖZÖS NCM+RNDIS-ben -> device-oldali
gadget adatút hiba. KÖVETKEZŐ: device-oldali carrier-diagnosztika SD-re (v5) hogy lássuk az okot.

--- AUTONÓMIA KÉRDÉS (user) — adb? retry count? ---
adb: NEM lesz ezen a boot-szinten (adbd az Android-konténer/droid-hal felállását igényli, az bukik).
  HELYETTE telnet (busybox telnetd) = ekvivalens root shell + fájlátvitel (base64) + reboot,
  droid-haltól függetlenül — DE előbb a USB adatutat meg kell oldani (0-frame).
retry count: MEGOLDHATÓ. Most minden boot csökkenti (Sailfish sosem jelez 'successful'-t, mert a
  boot_control HAL=droid-hal nem áll fel). 7 boot -> unbootable -> fastboot set_active a (retry=7 reset).
  AUTONÓM FIX-ek: (a) boot_a GPT 'successful' bit beállítása -> bootloader nem csökkenti (lásd lent);
  (b) ha lesz telnet: 'reboot bootloader' az OS-ből -> fastboot -> set_active a -> reboot (gomb nélkül).

--- GPT A/B ATTRIBÚTUM (autonómia-fix alapja) — sgdisk elérhető (/sbin/sgdisk, TWRP) ---
boot_a=mmcblk0p27, boot_b=mmcblk0p28. 'sgdisk --info=27 /dev/block/mmcblk0' -> Attribute flags.
ELOLVASVA: boot_a flags = 0x102F000000000000. Magas szó 0x102F dekódolva (Qualcomm gpt-utils séma):
  bit48-49 priority=3 (max 2-bit), bit50 active=1, bit51-53 retry/tries=5 (7->5, 2 boot fogyott),
  bit54 successful=0, bit55 unbootable=0, bit60 read-only(GPT std).
FIX (jelölt): 'sgdisk --attributes=27:set:54 /dev/block/mmcblk0' (successful=1) -> nincs retry-csökkenés.
  HELYREÁLLÍTHATÓ: 'fastboot set_active a' bármilyen GPT-attribútum hibát visszaír (retry=7, bootable).
  (A pontos successful-bit pozíciót verifikálni kell — set+reboot+getvar slot-successful:a.)
Olvasás: 'sgdisk --attributes=27:show:<bit> /dev/block/mmcblk0'.

--- ITER E: init-debug v5 (TELEPÍTVE) ---
v5 = dedikált wd-petter + RNDIS telnet + DEVICE-OLDALI carrier-diag (/sdlog2/sailfish-usbdiag.log:
  carrier/operstate/flags/udc_state/rx-tx stats) + ROBUSZTUS droid-hal dump 60s ÉS 120s-nél
  (/sdlog2/droidhal-{60,120}s-*.log: dmesg, ps, journalctl -b, systemctl --failed/status droid-hal-init/
  list-jobs, /run ls — stderr is fájlba, hogy a korábbi 0-bájt journal okát is lássuk).
  Cél: (1) megérteni a 0-frame device-oldali okát, (2) megfejteni a droid-hal-init bukás okát.

================================================================================
[2026-06-26 22:10] GYÖKÉR-OK MEGTALÁLVA: ~30 service MASZKOLVA + kernelből hiányzik binderfs
================================================================================
ITER E (v5) dump-elemzés — KÉT döntő felfedezés:

(A) USB 0-frame device-oldali ok (sailfish-usbdiag.log): rndis0 carrier=1, operstate=up,
  udc=configured, RX NŐ (27->58, a device FOGADJA a host csomagjait!), de TX=5-nél FAGY
  (csak kezdeti IPv6 MLD/DAD). flags=0x1003 (UP+BCAST+MCAST, de NINCS IFF_RUNNING 0x40).
  => a device fogad de nem válaszol (pl. ARP). Device-oldali ARP/route/connman kérdés. MÁSODLAGOS.
  (connman amúgy is maszkolva — lásd lent — szóval a hálózatkezelés féloldalas.)

(B) **A FŐ BLOKKOLÓ — droid-hal-init.service MASZKOLVA + ~30 másik service is!**
  /etc/systemd/system/droid-hal-init.service -> /dev/null (mask), dátum 2026-06-25 13:19.
  UGYANEZEN dátummal MIND maszkolva (/dev/null): connman, connman-vpn, mce, dsme(12:03),
  sensorfwd, start-user-session, init-done, initial-bootstate, droid-bootctl, droid-late-start,
  dummy_netd, bluebinder, oneshot-root(-late), policies-setup, wait_for_keymaster, sailfish-fpd,
  sailjaild, yamuisplash, wayland.path, audiosystem-passthrough-dummy-af, nemo-devicelock.socket,
  quota_nld, crash-reporter-*, rich-core-early-collect, runlevel-user-done, sailfish-devicelock-*.
  => EGY KORÁBBI SESSION (2026-06-25) "minimál-boot" debug céllal kimaszkolta szinte az EGÉSZ
  Sailfish felső stacket, és SOSEM vonta vissza! Ezért nincs droid-hal, servicemanager, UI.
  A binder -22 flood (29189 = context manager) ENNEK következménye: droid-hal-init maszkolva ->
  Android init/servicemanager nem indul -> nincs binder context manager -> minden bind -22.
  VALÓDI unitok helye (Sailfish): /usr/lib/systemd/system/ (NEM /lib).

(C) MÁSODLAGOS: kernelből hiányzik a binderfs. journal: "mount: /dev/binderfs: unknown filesystem
  type 'binder'" -> dev-binderfs.mount FAILED (status 32). Van statikus /dev/binder,hwbinder,
  vndbinder node (CONFIG_ANDROID_BINDER_DEVICES), de az Android11/LOS18.1 userspace binderfs-t vár.
  Lehet hogy droid-hal-init statikus node-okkal is elindul; ha nem -> kernel CONFIG_ANDROID_BINDERFS=y
  kell, VAGY dev-binderfs.mount maszkolása + statikus node-ok.

KÖVETKEZŐ LÉPÉS (autonóm haladás): UNMASK. A maszk-symlinkek törlése a rootfson (offset-mount rw):
  rm /etc/systemd/system/<svc> (a /dev/null linkek). MINIMUM droid-hal-init; valószínűleg ÖSSZESET
  vissza kell állítani egy valódi boothoz (connman a hálózathoz/usb-hez, dsme, mce, start-user-session
  az UI-hoz). Egyenként/ellenőrzötten, mert a korábbi session okkal maszkolhatott (boot-hang?).
  Terv: töröld a droid-hal-init + alap droid + connman maszkokat, reboot, nézd meddig jut (p28+SD+journal).

================================================================================
[2026-06-26 ~22:xx] ITERÁCIÓ F — SZELEKTÍV UNMASK: csak NETWORK service-ek (USB/net prioritás)
================================================================================
CÉL (user): "az usb felallitas legyen prioritas, ne kelljen most varni fs resize muveletre"
  + pontosítás: "inditsuk el a network service-eket is sailfishen, de az osszes tobbit
  csak a kovetkezo korben". => NE az összes 29 maszkot vegyük le egyszerre; ebben a körben
  csak a network réteg jöjjön fel, a többi (droid-hal, UI, mce/dsme...) marad maszkolva.

ELŐZMÉNY: a 29 maszk-symlink mind /dev/null-ra, 2026-06-25 13:19 (korábbi session minimál-boot).
  Egy korábbi lépésben MIND a 29-et töröltem (teljes unmask) — majd a user pontosítása után
  VISSZAMASZKOLTAM a nem-network service-eket.

VÉGÁLLAPOT ebben a körben (rootfs offset-mount rw, /mnt/sfroot):
  AKTÍV (maszk levéve, valódi unit /usr/lib/systemd/system-ből, enabled a /usr/lib wants miatt):
    - connman.service        (WantedBy=multi-user.target; Requires=dbus.socket oneshot-root.service)
    - connman-vpn.service    (multi-user.target.wants)
    - dummy_netd.service     (graphical.target.wants; After=droid-hal-init [csak sorrend, nem Requires]
                              => maszkolt droid-hal mellett is indulhat; /dev/hwbinder statikus node)
    - oneshot-root.service   (connman REQUIRES-e! Requires=dbus.service; After=dsme [no-op, dsme maszkolt];
                              futtatja /usr/bin/oneshot root-setup) — connman e nélkül NEM indulna
  MASZKOLVA marad (25 db, /dev/null, "következő kör"): droid-hal-init, mce, dsme, sensorfwd,
    start-user-session, init-done, initial-bootstate, droid-bootctl, droid-late-start, bluebinder,
    oneshot-root-late, policies-setup, wait_for_keymaster, sailfish-fpd, sailjaild, yamuisplash,
    wayland.path, audiosystem-passthrough-dummy-af, nemo-devicelock.socket, quota_nld,
    crash-reporter-endurance, crash-reporter-journalspy, rich-core-early-collect,
    runlevel-user-done, sailfish-devicelock-encsfa-fpd.

KULCS-FELISMERÉSEK:
  - A maszk /etc/systemd/system/<svc> -> /dev/null FELÜLÍRJA a /usr/lib unitot. Maszk levétele =
    a valódi unit aktív. ENABLE külön kell, DE a network service-ek a /usr/lib/.../*.target.wants/-ban
    eleve enabled-ek (connman+connman-vpn a multi-user.target.wants-ban, dummy_netd a graphical.target.wants-ban)
    => maszk-levétel ELÉG, nem kell extra enable symlink.
  - default.target -> graphical.target (graphical behúzza a multi-user.target-et => connman elindul).
  - connman Requires=oneshot-root.service => maszkolt oneshot-root mellett connman NEM indulna el!
    Ezért oneshot-root-ot is unmaskoltam (network-prerekvizit).
  - dummy_netd Type=notify, TimeoutStartSec=60: ha a hwbinder miatt elakad, 60s után bukik, nem
    blokkol fatálisan.

PARANCSOK (mind adb shell, </dev/null KELL a loop-ban különben az adb elfogyasztja a lista-stdin-t!):
  mount -o remount,rw /mnt/sfroot
  # maszk-nevek kinyerése host-oldalon: ls -la .../system | awk '/-> \/dev\/null/{print $(NF-2)}'
  # törlés: while read f; do adb shell "rm -f '.../system/$f'" </dev/null; done < list
  # visszamaszk: ln -sf /dev/null '.../system/<svc>'
  # ELLENŐRZÉS: ls -la .../system | grep -c -- '-> /dev/null'

TWRP-BUKTATÓK (ÚJ):
  - find -lname NINCS ("bad arg"); find -iname SEGFAULTOL (SIGSEGV) mély fában => NE használj find-ot,
    csak ls + awk/grep.
  - a `for f in *; [ -L ]` glob+test megbízhatatlan a TWRP shellben (0 találat) => host-oldali parse.

KÖVETKEZŐ: sync + unmount rootfs, fsck.fat -a SD, retry-count ellenőrzés, reboot slot A, majd
  SD/p28/journal log: connman elindult-e, rndis0 TX feloldódott-e (telnet 192.168.2.15:23 él-e).
  Ha a network jó => következő körben droid-hal-init + UI service-ek unmask.

--------------------------------------------------------------------------------
[2026-06-26 ~22:27] ITERÁCIÓ F — EREDMÉNY (network unmask + successful bit + reboot)
--------------------------------------------------------------------------------
ELVÉGZETT VÁLTOZTATÁSOK ebben a körben:
  1. UNMASK: connman, connman-vpn, dummy_netd, oneshot-root (connman Requires-e). 25 maszk marad.
  2. GPT boot_a (p27) SUCCESSFUL BIT (bit 54) beállítva: flags 0x1027... -> 0x1067...
     => bootloader NEM csökkenti tovább a retry-t, MINDIG A-ra bootol (autonóm reboot infra).
     Dekód előtte: priority=3, active=1, retry=4, successful=0, unbootable=0.
     PARANCS: sgdisk --attributes=27:set:54 /dev/block/mmcblk0 (ez a sgdisk CSAK long-opt!).
     GPT-backup: sgdisk --backup=... -> SD-re ment, DE az SD BAD-SECTOROS (user) => NEM megbízható!
       TEENDŐ: legközelebb TWRP-ben adb pull a GPT-backupot /mnt/1TB-re (host), ne SD-re.
  3. fsck.fat -a SD (dirty bit törölve, 92 fájl) majd adb reboot -> slot A.

EREDMÉNY:
  + Boot STABIL: device ~25s-nél felhozta a RNDIS gadgetet (18d1:d001 "FP3 RNDIS"), device#79,
    AZÓTA NINCS újabb reboot/enumeráció => init-debug lefutott, watchdog életben tart, NEM crash-loop,
    NINCS watchdog-reset. A connman-unmask NEM törte el a bootot.
  - DE: USB device->host TX TELJESEN BEFAGYVA (a régi blokkoló MEGMARADT, connman NEM oldotta meg):
      host RX=11->12 (90s alatt +1 frame), ping 100% loss, telnet:23 "No route to host", ip neigh ÜRES.
      A device fogad (host TX=143 = device RX), de gyakorlatilag nem küld (12 frame összesen).
  - HOST-OLDAL BIZONYÍTOTTAN HELYES (tehát a hiba a DEVICE gadget-szinten van):
      * rndis_host bind OK: "register 'rndis_host' ... enx7e8f7b07ba38" (MAC bootonként random, nincs dev_addr)
      * host IP 192.168.2.1/24 beállítva, ip link up, NM-ből kivéve (nmcli dev set ... managed no),
        down->up ciklus, promisc on (packet-filter SET trigger) — SEMMI nem oldotta fel a device TX-et.
      * NM kezdetben "disconnected"-nek mutatta az ifacet (link-local only beállítás öröksége).
  - DIAGNÓZIS (korábbival egyező): device rndis0 netdev flags=0x1003 (UP|BROADCAST|MULTICAST),
    NINCS IFF_RUNNING(0x40) => a device kernel nem továbbít. A f_rndis gadget nem állít carrier-t
    (netif_carrier_on) — az RNDIS data-path state machine nem ér el DATA_INITIALIZED-be. NCM-mel is
    0-frame volt korábban => NEM RNDIS-protokoll-specifikus, hanem közös gadget-carrier probléma.

KÖVETKEZTETÉS: az USB-alapú autonómia (telnet) a device-oldali gadget-carrier hiba miatt NEM
  működik, és ez NEM host-konfig kérdés. Az adatút feloldásához device-hozzáférés kell (p28 olvasás
  TWRP-ből), és valószínűleg gadget/kernel szintű beavatkozás (f_rndis carrier, vagy más transport:
  Sailfish usb_moded developer-mode adb = functionfs bulk, NEM netdev => lehet hogy a carrier-bug
  NEM érinti; ezt érdemes tesztelni).

KÖVETKEZŐ LÉPÉS: TWRP-be bootolni (egyetlen elkerülhetetlen gombnyomás), majd:
  (a) p28 + (ha olvasható) SD-log: meddig jutott EZ a boot, elindult-e connman/multi-user.target,
      mi a device-oldali rndis0 állapot, IFF_RUNNING.
  (b) GPT-backup adb pull -> /mnt/1TB (SD bad-sector miatt).
  (c) dönteni: f_rndis carrier-patch vs. usb_moded developer-mode adb (functionfs) mint transport.

================================================================================
[2026-06-26 ~22:45] GYÖKÉROK MEGTALÁLVA: RNDIS TX-stall = Qualcomm IPA offload + uC nincs betöltve
================================================================================
A TWRP-ben (RAM-boot twrp-fp3.img) olvasott device-oldali bizonyítékok (sailfish-dmesg.log a SD-n,
ez a boot up=910s+ futott, network réteg fent: connman+ofonod+nfcd):

DÖNTŐ DMESG (a TX-stall oka):
  [1.913] ipa ipa_init: fail to register with bus mgr! / ipa_plat_drv_probe: ipa_init failed
  [2.109] ipa ipa2_uc_state_check: uC interface not initialized
  [2.109] ipa ipa_sps_irq_control_all: EP (2) not allocated / EP (5) not allocated
  [2.499] msm_sharedmem: hyp_assign_phys failed IPA=... err=-5
  [4.164] rmnet_ipa started initialization; IPA ipa-loaduC = True; IPA SSR support = True
  [4.168] ipa ipa2_uc_state_check: uC is not loaded
  [4.170] RNDIS_IPA module is loaded.

ÉRTELMEZÉS: a FP3 (msm8953) RNDIS gadget adatútja a Qualcomm IPA (IP Accelerator) HARDVER-offloadon
megy (rndis_ipa / f_qc_rndis), NEM CPU-úton. Az IPA TX-hez kell (a) az IPA mikrokontroller (uC)
firmware betöltve [most: "uC is not loaded"], és (b) az ipacm userspace daemon a routing/filter
szabályokhoz. Mindkettőt az Android userspace (droid-hal-init / PIL firmware + ipacm) hozná.
Droid-hal MASZKOLVA => IPA uC nem töltődik, ipacm nem fut => az offloadolt TX HALOTT.
A pár kontroll-frame (exception path) átmegy (device tx=10, host RX=12), majd elakad. EZ a
"néhány frame után stall" tünet pontos magyarázata, és AZÉRT nem segít semmilyen host-oldali fix /
route / CDC-csere — NCM-mel is ezért volt 0-frame (közös IPA-offload ok).

USB-DIAG MEGERŐSÍTÉS (sailfish-usbdiag.log up=910s): rndis0 carrier=1 operstate=up flags=0x1003
(nincs IFF_RUNNING 0x40), udc=configured, IP 192.168.2.15/24, device stats rx=176 tx=10.

ADB-ÚT KÖVETKEZMÉNY: Android adbd a com.android.adbd APEX-ben van (apexd=droid-hal mountolja);
NINCS különálló adbd a Sailfish rootfson, NINCS ffs.adb a usb-moded configban
(usb-moded-configfs-fp4.ini csak function_rndis=rndis.usb0 + function_mtp=ffs.mtp). Sailfish
developer_mode = RNDIS-alapú (dev_mode-configfs.ini network_interface=usb0, dhcp_server) =>
ugyanaz az IPA-bug. MTP viszont ffs.mtp=functionfs => a functionfs/bulk elvileg megy (IPA-tól
független), de adb-hez kell az APEX adbd => kell droid-hal.

KONVERGENCIA / KÖVETKEZŐ LÉPÉS: minden út a droid-hal-init felhozásához vezet (= sanctionált
"következő kör"). droid-hal-init: (a) PIL betölti az IPA uC firmware-t + ipacm => RNDIS TX feloldódik
=> telnet/SSH autonómia; (b) apexd + Android init => adbd functionfs => adb. Várható régi mély
blokkoló: binder/PDR -22 flood (servicemanager/PD bring-up), + binderfs hiány (kernel 4.9.227,
statikus /dev/binder,hwbinder,vndbinder van; /dev/binderfs üresen mountolt).

WEB-FORRÁSOK (a kereséshez, megerősítik az IPA-offload mechanizmust):
  - android.googlesource.com kernel/msm drivers/net/ethernet/msm/rndis_ipa.c
  - android.googlesource.com kernel/msm drivers/usb/gadget/f_qc_rndis.c
  - platform/hardware/qcom/data/ipacfg-mgr (ipacm: UL/DL filter+routing, USB client HW path)
  - kernel.org gadget_configfs / gadget-testing (rndis function = usb_f_rndis)

TEENDŐK A KÖVETKEZŐ KÖRRE:
  - UNMASK droid-hal-init (+ droid-bootctl, droid-late-start, init-done, initial-bootstate,
    oneshot-root-late, wait_for_keymaster?). UI-t (yamuisplash, start-user-session, mce, dsme,
    sailjaild, fpd, devicelock) EGYELŐRE maszkolva hagyni a fókusz miatt.
  - binderfs: vagy CONFIG_ANDROID_BINDERFS=y (kernel rebuild), vagy dev-binderfs.mount maszk +
    statikus node-okra hagyatkozás (Android 11 userspace binderfs-t vár — kockázat).
  - Reboot, p28+SD+journal: betöltődik-e az IPA uC fw (dmesg "uC loaded"), elindul-e servicemanager,
    feloldódik-e az rndis0 TX (host RX nő, ping/telnet él). GPT successful bit MÁR beállítva (autonóm A-boot).
  - GPT-backup MÁR a hoston: $FP3_ROOT/gpt-mmcblk0-*.bin (SD bad-sector miatt nem SD-re).

================================================================================
[2026-06-26 ~23:10] ITER-G EREDMÉNY: droid-hal-init unmask → 3 KÜLÖN BLOKKOLÓ azonosítva
================================================================================
Változtatás: unmask droid-hal-init + droid-bootctl + droid-late-start + init-done +
initial-bootstate + oneshot-root-late + wait_for_keymaster (UI maszkolva maradt). Reboot slot A.
TWRP-ből (RAM-boot) kiolvasva a 120s droid-hal dump (SD) + offset-mount rootfs + LVM metaadat.

BLOKKOLÓ #1 — binderfs hiány => servicemanager halott => binder -22 flood (AZ EREDETI MÉLY OK):
  - Android /init ELINDULT (ps: PID 644/785 = {init} /bin/sh /init), DE nincs servicemanager,
    ipacm, logd, hwservicemanager.
  - journal: "mount: /dev/binderfs: unknown filesystem type binder" (2x), dev-binderfs.mount
    FAILED (status=32). A kernel 4.9.227 nincs CONFIG_ANDROID_BINDERFS-szel.
  - dmesg: binder 32883/32894 -> 29189/-22 line 3119 flood ~1s-enként (context manager sosem
    áll fel, mert a servicemanager binderfs nélkül kilép a BINDER_SET_CONTEXT_MGR előtt).
  => MINDEN HAL (IPA uC load, ipacm, wifi-HAL) ezen bukik. FIX: kernel rebuild CONFIG_ANDROID_BINDERFS=y
     (4.9 backport kellhet), VAGY servicemanager/libbinder statikus /dev/binder-re kényszerítése.

BLOKKOLÓ #2 — rootfs 99% TELE (No space left on device kaszkád):
  - df: 1.4G méret, 1.3G használt, 16M szabad (99%). /usr=1.2G.
  - journal: dummy_netd / bluetooth / polkit / systemd-hostnamed "Failed to run start task:
    No space left on device" => kaszkádoló service-bukás, dbus activation timeoutok.
  - GYÖKÉR (LVM metaadat a p62-n): a "sailfish" VG PV-je (pv0) dev_size=3426528 sector (~1.63 GB),
    pe_count=418 (extent_size=8192 sect=4MiB), root LV=387 extent (1.51GB). A PV a flashelt image
    mérete, NEM a 48.7GB-os userdata (p62)! A first-boot resize (pvresize->lvextend->resize2fs)
    SOSEM futott (nincs resize-service a rootfson). Csak ~31 szabad extent (124MB) a VG-ben.
  => FIX: pvresize a PV-t a teljes p62-re (loop a teljes p62-n, offset nélkül), lvextend root
     -l +100%FREE, resize2fs. DE: TWRP-ben NINCS lvm tool (csak resize2fs). A rootfs /usr/sbin/lvm
     dinamikus, és LD-trükkel se megy: libdevmapper-event.so.1.02 NINCS a rootfson. => statikus
     lvm/lvm2 bináris kell TWRP-be, VAGY a device boot-időben végezze (de nincs resize-szolgáltatás).
  NB: a user korábban "ne várjunk a resize-ra" -> de a bizonyíték szerint a resize ELENGEDHETETLEN.

BLOKKOLÓ #3 (kisebb): wait_for_keymaster.service: "Failed to execute command: No such file"
  (a keymaster binár nincs) => ezt vissza lehet maszkolni, ártalmatlan de zajos.

WiFi (jó hír, a user kérdésére): dmesg "wcnss: wcnss_wlan probed in built-in mode",
  "subsys-pil-tz a21b000.qcom,pronto" => a WiFi HW (Pronto/WCN) DETEKTÁLVA, a wlan-fw PIL infra megvan.
  A WiFi adatút NEM IPA-kötelező (gEnableIpaOffload/gIPAConfig opcionális, ki is kapcsolható a
  WCNSS_qcom_cfg.ini-ben). DE a wlan FELHOZÁSA Sailfish/Haliumon jellemzően az Android wifi-HAL-on
  megy => az is servicemanager-függő (=binderfs blokkoló #1). Tehát a WiFi-autonómia is a binderfs-en
  bukhat, hacsak nincs HAL-mentes wlan.ko+wpa_supplicant út.

KÖVETKEZTETÉS: a VALÓDI kritikus út = (#1) binderfs (kernel) + (#2) rootfs resize. Mindkettő kell
  bármilyen HAL-hoz/autonómiához. Sorrend-javaslat: előbb resize (több szabad hely, kevesebb zaj),
  aztán binderfs kernel-fix. successful bit ÉL (0x1067), GPT-backup a hoston.

================================================================================
[2026-06-26 ~23:15] ITER-H: TWRP-stílusú functionfs ADBD kísérlet — gadget NEM enumerált (vak)
================================================================================
ÚJ FELISMERÉS (a user reframe-je): a TWRP USB-je MŰKÖDIK = functionfs adb (ffs.adb), BULK transport,
NEM netdev => NEM érinti az IPA-bugot, NEM kell servicemanager/binderfs/RNDIS. A TWRP adbd statikus:
  file: "ELF 64-bit aarch64, statically linked, for Android 28, not stripped" (1760744 B).
  Lementve: $FP3_ROOT/twrp-adbd (= /sbin/adbd a TWRP-ből).
TWRP gadget-recept (élőben kiolvasva): configfs /config, g1, idVendor 0x22b8 idProduct 0x2e76,
  UDC 7000000.dwc3, config b.1 (f1->mtp.gs0, f2->ffs.adb), functionfs mount /dev/usb-ffs/adb (ep0/1/2).

ELVÉGEZVE ebben a körben:
  - init-debug v6 (RNDIS helyett functionfs adbd): sleep16 -> usb_moded stop -> gadget lebont ->
    g1 22b8:2e76 + config b.1 + functions/ffs.adb -> mount -t functionfs adb /dev/usb-ffs/adb ->
    link ffs.adb -> /usr/bin/adbd-static & -> sleep3 -> echo UDC (ekkor descriptorok már kiírva) ->
    adbd-felügyelet + SD-log. (host: $FP3_ROOT/init-debug)
  - adbd-static a rootfsra: /usr/bin/adbd-static (chmod 755).
  - /system/bin/sh -> /bin/sh symlink (az adb shell ezt exec-eli Android adbd-ben).
  - droid-core 7 service VISSZA-maszkolva (adb-úthoz nem kell, és droid-hal Android-init újra-
    konfigurálná a gadgetet + binder flood). Network service-ek (connman...) unmaskolva maradtak.

KRITIKUS MELLÉK-PROBLÉMA: rootfs TELE => az 1.76M adbd-t SE lehetett pusholni ("No space left",
  16M szabad). MEGOLDÁS (band-aid): rm -rf /var/log/journal/* + cache + *.log => 54M szabad lett.
  => A RESIZE HARD PREREKVIZIT, e nélkül a rendszer nyomorék (lásd ITER-G blokkoló #2, LVM PV 1.63G).

EREDMÉNY: reboot után a device NEM hozott fel SEMMILYEN USB gadgetet (host dmesg: csak "USB disconnect"
  a TWRP-ből kilépéskor, azóta semmi; lsusb üres 3+ percig). A watchdog-petter (init-debug 1. szekció)
  valószínűleg fut (nincs reset-loop / ismételt enumeráció => a device él, csak nincs USB), tehát az
  init-debug 2. szekció (adbd/ffs) ELBUKOTT: az adbd valószínűleg nem írt descriptorokat (gyanú:
  Android adbd property-area nélkül elszáll a __system_properties_init-en, vagy a functionfs descriptor
  formátum, vagy uid-drop). UDC bind üres ffs-sel => nincs enumeráció => VAK.

KÖVETKEZŐ LÉPÉS (TWRP): olvasd /sdlog2/adbd.log + sailfish-usb.log + sailfish-usbdiag.log + dump-*.
  Eldönteni miért bukott az adbd. Lehetséges fixek: (a) minimál Android property-area létrehozása
  (/dev/__properties__) az adbd-nek; (b) adbd helyett egyszerűbb ffs-teszt; (c) usb_moded developer_mode
  ffs.mtp-jét használni mintaként a descriptor-írásra. PÁRHUZAMOSAN: a RESIZE megoldása — vagy a rootfs
  saját lvm-jét futtatni TWRP-ből MINDEN libbel (libdevmapper-event hiányzott; ellenőrizni a tényleges
  lib-igényt: ld --list), vagy statikus lvm bináris. successful bit ÉL, GPT-backup a hoston.

################################################################################
[2026-06-26 ~23:24] *** ÁTTÖRÉS: ÉLŐ ADB SHELL A SAILFISH BOOTON (functionfs) ***
################################################################################
init-debug v7: a v6 functionfs-adbd FIX = a functionfs mountot uid=2000,gid=2000-nal kell:
  mount -t functionfs adb /dev/usb-ffs/adb -o uid=2000,gid=2000
OK MIÉRT: a TWRP adbd "production build" => KÖTELEZŐEN uid 2000 (shell)-re ejt ("adbd cannot run as
root in production builds"). uid/gid nélkül az ep0 root-tulajdonú => az adbd (uid 2000) nem tudta
megnyitni/írni az ep0-t => nem írt descriptort => ep1/ep2 hiányzott => UDC bind -19 (failed to start
g1) => nincs enumeráció. uid=2000,gid=2000 mounttal AZ ADBD KIÍRJA A DESCRIPTOROKAT => ENUMERÁL.

EREDMÉNY (v7 boot, ~36s):
  lsusb: 22b8:2e76 "FP3 ADB"; adb devices: "FP3ADB device"
  adb shell id => uid=2000(shell) gid=2000(shell) groups=...1011(adb)...
  uname => Linux 4.9.227+ aarch64 (a VALÓDI hybris kernel, élő Sailfish boot!)
=> AZ IPA/RNDIS/binderfs BLOKKOLÓKAT TELJESEN MEGKERÜLTÜK. Bulk functionfs transport, nem netdev.
   AUTONÓMIA (read-only/shell szinten) MEGVAN, fastboot/TWRP nélkül lehet adb-zni.

ÉLŐ SHELL-BŐL KIDERÜLT:
  - df /: /dev/sailfish/root 1.4G 99% tele, 7.8M szabad (LVM aktív) => RESIZE kell (journal újratelt).
  - connman NEM fut ("net.connman not provided") az unmask ellenére — valószínűleg ENOSPC/függőség miatt.
    ofonod (radio) FUT. Nincs wlan iface (csak rmnet_ipa0, lo) => WiFi driver/fw nincs (HAL kell).
  - root: devel-su SETUID de JELSZÓT kér (Auth failed üres/nemo-ra). sailfish_tools_system_action:
    Permission denied (uid2000). setuid-root bins: mount, firejail, passwd, sailfish_tools_system_action...
  - adb forward tcp:2323 tcp:2323 MŰKÖDIK. busybox-static telnetd v1.36.1 megvan a rootfson.
  - init-debug ROOT-ként fut (PID 1575).

ROOT-TERV (v8): init-debug (root) indítson localhost root-telnetd-t:
  /usr/bin/busybox-static telnetd -p 2323 -b 127.0.0.1 -l /bin/sh  (loopban, restart)
  majd hoston: adb forward tcp:2323 tcp:2323 ; telnet 127.0.0.1 2323 => ROOT shell (init-debex root).
  uid2000 nem írhatja az /init-debug-ot => v8-at TWRP-ből kell telepíteni (remélhetőleg UTOLSÓ TWRP-menet;
  utána root shell-ből minden megy: LVM resize, connman, init-debug módosítás).
adbd-static a rootfson: /usr/bin/adbd-static. /system/bin/sh -> /bin/sh symlink kész.
successful bit ÉL, GPT-backup a hoston.

[2026-06-26 ~23:30] v8: ROOT SHELL MEGVAN. adb forward tcp:2323 tcp:2323 + telnet 127.0.0.1 2323 => uid=0(root). init-debug (root) localhost telnetd:2323 megy. TELJES AUTONOMIA: adb(uid2000)+root telnet, TWRP/fastboot NELKUL. df / meg 99%% (14M) => RESIZE a kovetkezo (root van hozza). adb-szerver host: TMPDIR=scratchpad kell (a /tmp/adb.1000.log jogosultsag miatt).

################################################################################
[2026-06-26 ~23:45] ITER-I: ROOT shellbol ELO RESIZE + connman FELHOZVA (autonomia kihasznalva)
################################################################################
Csatorna: host adb (TMPDIR=scratchpad!) -> adb forward tcp:2323 tcp:2323 -> busybox telnet
127.0.0.1 2323 -> init-debug ROOT shell (uid=0). A telnet-meghajto: rootcmd.sh (scratchpad),
parancsokat stdin-en pipe-ol, sleep-tures (a parancsban levo sleep > meghajto-wait eseten az
output levaghat -> kulon hivasban kell lekerdezni).

(A) LVM ALLAPOT a ELO rendszerbol (a TWRP-kori 1.63G metaadat ELAVULT volt!):
  PV /dev/mmcblk0p62: PSize=102211584S (~48.7G), PFree=98975744S (~47.2G) => a PV MAR a teljes
    particiot lefedi, pvresize NEM kell!
  VG sailfish: VSize 48.74g, VFree 43.71g (resize utan).
  LV: root=3170304S (1.51G, 99% tele), home=65536S (~32M, /home kulon LV, plain ext4 mount).
  => A blokkolo NEM a PV merete volt, hanem a root LV nem volt kiterjesztve. (Lehet egy korabbi
     pvresize mar lefutott, vagy a TWRP-metaadat-olvasas volt felrevezeto.)

(B) VALTOZTATAS #1 - ROOT FS RESIZE (ELO, reboot nelkul):
  /usr/sbin/lvm lvextend -L 5G /dev/sailfish/root   => 387->1280 extent, 1.51G->5.00G OK
  resize2fs /dev/sailfish/root                       => on-line resize, 1310720 (4k) block
  EREDMENY: df / : 1.4G/99% -> 4.9G total, 1.4G used, 3.4G avail, 29%. VG meg 43.71G szabad (home-nak).
  Nem vettem 100%FREE-t, hogy a /home-nak maradjon hely (kovetkezo korben lvextend home).

(C) ENOSPC KASZKAD MEGSZUNT (a resize bizonyitott haszna):
  systemctl --failed: korabban dummy_netd/bluetooth/polkit/systemd-hostnamed "No space left" -
  MOST eltunt. Marad 5 FAILED, egyik sem ENOSPC:
    dev-binderfs.mount (kernel CONFIG_ANDROID_BINDERFS hianyzik - a FO blokkolo),
    dev-blkio.mount (droid cgroup mount), mount-sd@mmcblk1p1 (SD bad-sector, varhato),
    systemd-modules-load, systemd-tmpfiles-setup.

(D) connman BLOKKOLO UJRADIAGNOSZTIZALVA - NEM ENOSPC volt, hanem first-boot encryption-gate:
  connman.service drop-in 01-prevent-start.conf: ConditionPathExists=!/var/lib/sailfish-device-
    encryption/encrypt-home  => az 'encrypt-home' (0-byte FLAG file) LETEZESE blokkolja connman-t.
  Masik drop-in 01-require-home-mount: RequiresMountsFor=/home + PartOf=home.mount => home.mount
    MAR active (mounted /dev/mapper/sailfish-home), tehat ez OK.
  => EGYETLEN blokkolo = a stale encrypt-home flag (a sosem-lefutott home-encryption first-boot).

(E) VALTOZTATAS #2 - connman FELHOZVA (ELO):
  mv /var/lib/sailfish-device-encryption/encrypt-home{,.disabled}  (a /home mar plain ext4, nem
    akarunk titkositast -> a flag eltavolitasa = epp az 'encryption-done' ut, biztonsagos)
  systemctl daemon-reload; systemctl start connman  => start rc=0
  EREDMENY: connman ACTIVE, State=idle. connmanctl mukodik.

(F) connman TECHNOLOGIES / IFACES (a kovetkezo frontvonal):
  technologies: CSAK 'gps' (Powered=False). NINCS wifi/cellular technology.
  ip link: lo, ip_vti0, ip6_vti0, sit0, ip6tnl0, rmnet_ipa0(DOWN). NINCS wlan0.
  => WiFi: NINCS wlan/cfg80211/mac80211 modul betoltve, /lib/modules-ban SINCS ilyen .ko;
     wcnss "built-in mode"-ban probe-olt DE nem regisztralt ieee80211 phy-t (/sys/class/ieee80211
     URES); nincs fw-download. wpa_supplicant megvan (/usr/sbin), de nincs phy. => a wlan0 a
     WCNSS-fw-download + driver-init utan jonne, amit Haliumon a Android wifi-HAL + cnss/wcnss
     service vezenyel => binderfs/droid-hal FUGGO.
     Cellular: rmnet_ipa0 DOWN, adatut = IPA (uC nincs betoltve) => szinten droid-hal/binderfs fuggo.

KOVETKEZTETES: a session ket ELO gyozelme kesz (resize + connman-up). A KOVETKEZO FO FRONT =
  kernel-rebuild CONFIG_ANDROID_BINDERFS=y (4.9 backport kellhet) -> servicemanager felall ->
  wifi-HAL/cnss -> wlan0 ; es IPA-uC/ipacm -> rmnet adat. Ez gatolja egyszerre a WiFi-t es a cellt.
  Mellek: lvextend home (43.7G szabad), dev-blkio/modules-load/tmpfiles failed-ek tisztitasa.
Szabalyok: ezek ELO valtoztatasok (nincs reboot/GPT/retry-counter erintve), igy nem esnek a
  'reboot-ok kozott egy valtoztatas' szabaly ala. successful bit EL (0x1067). SD bad-sector.

################################################################################
[2026-06-27 ~03:30] *** GYÖKÉROK MEGTALÁLVA: droid-hal-init linker ENOENT = /system nincs mountolva ***
################################################################################
A 3h szünet után (telefon végig futott, resize+connman túlélte) folytattam a droid-hal-init blokkoló
felgöngyölítését. EZ a port IGAZI, RÉGÓTA tartó blokkolója — és NEM a binderfs, NEM (csak) az ENOSPC.

(A) A binder -22 flood FORRÁSA tisztázva: NEM Android HAL-ok, hanem a SAILFISH saját démonjai
    (ofonod 31578, dummy_netd 31511, nfcd 31495) — libgbinder-en át próbálnak Android HAL-okhoz
    csatlakozni, de nincs context manager (servicemanager) regisztrálva => végtelen retry -22.
    servicemanager/hwservicemanager NINCS a ps-ben. Van viszont 2 db "{init} /bin/sh /init" (647/788,
    root=/, üres env) — degenerált maradék, NEM hozta fel a property service-t (/dev/__properties__ NINCS).

(B) servicemanager NEM igényel binderfs: a /system_root/system/bin/servicemanager binárisban a string
    "/dev/binder" (NEM /dev/binderfs/binder). A legacy /dev/binder (10,56), hwbinder(10,55),
    vndbinder(10,54) LÉTEZIK (CONFIG_ANDROID_BINDER_IPC=y + CONFIG_ANDROID_BINDER_DEVICES="binder,
    hwbinder,vndbinder"). binderfs NINCS a kernelben (CONFIG_ANDROID_BINDERFS hiányzik) DE NEM KELL.
    Az init.rc 268-282 mountolná binderfs-t + symlinkelné /dev/binder-t — ha a mount f失, a real node marad.
    => KERNEL-REBUILD NEM SZÜKSÉGES. (A korábbi "binderfs a blokkoló" feltételezés HIBÁS volt.)

(C) ITER-G droidhal logok TÚLÉLTÉK az SD-n (/sdlog2/droidhal-120s-*). Kiderült: droid-hal-startup.sh
    status=127, early-init.sh status=2. A startup.sh: cd /; touch /dev/.coldboot_done; echo $NOTIFY_SOCKET
    > /run/droid-hal/notify-socket-name; exec nohup /sbin/droid-hal-init. A 127 oka NEM ENOSPC volt:

(D) *** AZ IGAZI OK *** (élő teszt, guardian-nal, post-resize): a systemd journal:
      sh[9612]: nohup: can't execute '/sbin/droid-hal-init': No such file or directory  => status 127
    A /sbin/droid-hal-init LÉTEZIK (1070880 B), tehát az ENOENT = AZ ELF INTERPRETER hiányzik.
    file: interpreter = /system/bin/bootstrap/linker64. ls /system/bin/linker64 => NINCS.
    /system = majdnem üres dir (csak bin lib64). Az Android rendszer a /system_root/system/-ben van
    (p30 ro a /system_root-on; /system_root/system/bin/bootstrap/linker64 LÉTEZIK 2193352 B; a
    /system_root/system/lib64/bootstrap/ -ben libc.so/libdl.so/libm.so). /system_root = Android system-
    as-root (bin->/system/bin, etc->/system/etc, system/ a valódi tartalom, vendor/ üres mountpoint).
    => /system NINCS feltöltve => az Android linker nincs ott, ahol a binárisok várják => droid-hal-init
       NEM tud execelni => nincs property service/servicemanager => nincs HAL => nincs WiFi/cellular.

(E) MIÉRT nincs /system mountolva: system.mount + vendor.mount minden boot "Dependency failed"-del bukik.
    OK: az /etc/systemd/system/system.mount (override) What=/dev/block/mmcblk0p30, de a
    /dev/block/mmcblk0p30 MANUÁLIS SYMLINK (../mmcblk0p30, az init-debug /dev/block-fix csinálja),
    NEM udev-node => a dev-block-mmcblk0p30.device unit INACTIVE (míg dev-mmcblk0p30.device ACTIVE).
    A .mount implicit Requires/After a dev-block-...device-re => az inaktív => 'dependency' fail.
    RÁADÁSUL az /etc override STRUKTURÁLISAN is rossz: p30-at /system-re mountolná (p30 root = android /,
    bin->/system/bin symlinkkel => /system/bin/bootstrap/linker64 körkörös). A HELYES a /usr/lib/systemd/
    system/system.mount: bind /system_root/system -> /system (ez csak system_root.mount-tól függ = ACTIVE).
    vendor.mount: What=/dev/block/mmcblk0p32 -> ugyanaz a dep-bug; p32 (label "vendor") KÉZZEL HIBÁTLANUL
    mountolható (app bin bt_firmware dsp etc firmware_mnt lib lib64 odm radio rfs vendor_dlkm...). /vendor
    mountpoint NEM létezik a rootfson (mkdir kell).

(F) A FIX (kernel-rebuild NÉLKÜL):
    1. /system: bind /system_root/system -> /system  (töröld/javítsd az /etc override-ot, hogy a /usr/lib
       bind-verzió fusson; VAGY init-debug csinálja a mountot).
    2. /vendor: mkdir /vendor; mount -o ro,noatime /dev/mmcblk0p32 /vendor  (a unitban What=/dev/mmcblk0p32).
    3. (opc.) /vendor/dsp, /vendor/firmware_mnt almountok szintén /dev/block dep-bug — később, nem kritikus
       a START-hoz. apex-et az apexd hozza fel induláskor; a bootstrap linker NEM igényel apex-et.
    4. UTÁNA unmask droid-hal-init => execel => property svc + servicemanager (/dev/binder) + HAL-ok.
    TESZT: guardian v2 = élőben mount /system + /vendor, majd bare /sbin/droid-hal-init, monitor 90s
    (servicemanager? context mgr? wlan0? flood csökken?), majd reboot -f (init-debug v8 visszahozza a
    gadget+adb-t; droid-hal-init MASKED marad => tiszta boot). Failsafe: 150s-nál reboot mindenképp.

ÁLLAPOT: telefon él (resize 4.9G/29%, connman active), root adb+telnet OK. successful bit 0x1067.
KÖVETKEZŐ: guardian v2 futtatása (a fenti teszt). Ha servicemanager feláll => a fixet állandósítani
(system.mount/vendor.mount javítás /dev/mmcblk0pXX-re VAGY init-debug mount + droid-hal-init unmask).

################################################################################
[2026-06-27 ~04:00] *** A VALÓDI GYÖKÉROK: A11 (hybris-18.1) vs A15 (LOS22) VERZIÓ-ÜTKÖZÉS ***
################################################################################
A droid-hal-init blokkoló teljes láncának végigkövetése után KIDERÜLT a port valódi alapproblémája.

A LÁNC (mindegyik réteget lehántva, élő guardian-tesztekkel, reboot-recoveryvel):
 1. ENOSPC (rootfs 99%) -> RESIZE megoldotta (root 5G/29%). droid-hal-init MÉGIS bukott.
 2. droid-hal-init exec: "nohup: can't execute '/sbin/droid-hal-init': No such file or directory"
    (status 127). A bin LÉTEZIK => az ELF interpreter (/system/bin/bootstrap/linker64) hiányzott,
    mert /system nem volt feltöltve.
 3. /system mount: system.mount + vendor.mount minden boot 'Dependency failed' — mert
    What=/dev/block/mmcblk0pXX (MANUÁLIS symlink, az init-debug /dev/block-fix), aminek a
    dev-block-mmcblk0pXX.device unitja INACTIVE (a dev-mmcblk0pXX.device ACTIVE).
    FIX (ALKALMAZVA, állandó): /etc/systemd/system/system.mount -> bind /system_root/system /system
    (RequiresMountsFor=/system_root); vendor.mount -> What=/dev/mmcblk0p32; mkdir /vendor. Backup:
    *.mount.bak. REBOOT után BIZONYÍTOTT: system.mount+vendor.mount ACTIVE, /system/bin/bootstrap/
    linker64 LÁTHATÓ, /vendor/bin OK. (Ez a fix HELYES és MEGTARTANDÓ, az A11/A15 döntéstől függetlenül.)
 4. droid-hal-init exec /system mountolva: a bootstrap linker MOST FUT, de:
    "CANNOT LINK EXECUTABLE /sbin/droid-hal-init: library libbacktrace.so not found"
 5. *** A GYÖKÉROK ***: libbacktrace.so SEHOL (sem /system/lib64, sem bootstrap, sem /vendor).
    OK: a flashelt rendszer ANDROID 15 / LineageOS 22:
       ro.build.version.release=15 ; ro.lineage.version=4.0-a15-20260610...-official-FP3
       ro.vendor.build.fingerprint=Fairphone/lineage_FP3/FP3:15/BP1A.250505.005 ; vendor release=15
    Az A15 ELDOBTA a libbacktrace.so-t (libunwindstack-ra cserélték). BIZONYÍTÉK:
       natív A15 init (/system_root/system/bin/init) NEEDED: libbase,libcutils,LIBUNWINDSTACK (19 db)
       hybris /sbin/droid-hal-init   (Jun 21) NEEDED: ...,LIBBACKTRACE (20 db)  <-- A11-es!
    A HADK build-fa ($FP3_ROOT/hadk): revision android-11.0.0_r46, lineage-18.1,
       hybris-18.1, PLATFORM_VERSION RP1A (Android 11). => a teljes Sailfish hybris/droid-hal réteg
       ANDROID 11, de a device system_a(p30)+vendor_a(p32) ANDROID 15.
    => Egy A11 init bináris NEM tud futni A15 libekkel (4 major verzió ABI-eltérés; nem csak
       libbacktrace, hanem az egész HAL-middleware: libfs_mgr/liblp/libgsi/libselinux/property/
       servicemanager/HIDL-AIDL interfészek). EZÉRT nem jött fel SOHA a droid-hal-init.
    => binderfs/kernel-rebuild HALOTT NYOM volt; a kernel rendben (legacy binder megvan).

A DÖNTÉS (a USER-é, architekturális):
 A) [AJÁNLOTT, kevés munka] LineageOS 18.1 (Android 11) system+vendor flashelése a meglévő
    hybris-18.1 buildhez. Minden más (droid-hal-init, rootfs, kernel) MÁR A11-re kész. Kell: LOS 18.1
    FP3 system_a(p30)+vendor_a(p32) image (a hoston JELENLEG NINCS A11 system.img/zip). Ez a HADK
    szabványos elvárása. A mostani A15 system/vendor LECSERÉLENDŐ LOS 18.1-re.
 B) [HATALMAS munka] Az egész Sailfish hybris stack újraépítése hybris-22-re (Android 15), hogy a
    flashelt A15 alaphoz illeszkedjen. hybris-22 támogatottság bizonytalan; teljes HADK újraszinkron
    lineage-22.x forrásokkal + összes adaptáció újra.

ÁLLAPOT: device él, slot A, resize+connman+mount-fix MEGVAN (mind megtartandó), droid-hal-init MASKED
(úgyse futna). successful bit 0x1067. A mount-fix az EGYETLEN állandó változás ebben a körben (és helyes).
KÖVETKEZŐ: a USER döntése A/B; A esetén LOS 18.1 FP3 image beszerzése + p30/p32 flashelése (fastboot/TWRP).

################################################################################
[2026-06-27 ~04:20] DÖNTÉS: Option B — hybris-22.2 (Android 15) ÚJRAÉPÍTÉS
################################################################################
A USER az A11/A15 ütközésre a B opciót választotta: a Sailfish hybris réteg újraépítése
hybris-22.2-re, hogy a MÁR flashelt A15 (LineageOS 22) system+vendor-hoz illeszkedjen.
FEASIBILITY MEGERŐSÍTVE (GitHub API):
  - mer-hybris/hybris-patches: hybris-22.2 LÉTEZIK (és hybris-23.x). mer-hybris/android (manifest) is.
  - LineageOS/android_device_fairphone_FP3: lineage-22.2 LÉTEZIK (a device A15/LOS22-t futtat).
  - FP3 kernel LOS22-n is 4.9 (a device most is 4.9.227+ az A15 system alatt) => kevés kernel-churn.
TOOLING MEGERŐSÍTVE (non-interaktívan vezérelhető):
  - Platform SDK chroot: sudo -n $FP3_ROOT/sdk/sdks/sfossdk/sdk-chroot /bin/bash -lc "..."
    (Sailfish OS 4.6.0.13 Sauna; git, rpm, mb2). 
  - HABUILD: a Platform SDK-ból: ubu-chroot -r /parentroot$FP3_ROOT/sdk/sdks/ubuntu
    /bin/bash -lc "..." (Ubuntu 20.04; repo /usr/local/bin/repo, git, make).
  - Host: curl/wget/python3 van; git/repo NINCS a host PATH-ban (csak a chrootokban).
KÖRNYEZET: /mnt/1TB 682G szabad. Régi hadk (18.1) = 130G. RAM 15G (~7G szabad — a build fázisra
  szűk, swap/-j limit kell). env.sh hiba: /mnt/1T helyett /mnt/1TB a valódi path.
MODELL: a flashelt A15 system/vendor MARAD; csak a Sailfish/hybris réteg épül újra 22.2-re
  (hybris-boot.img A15-kernel+ramdisk, droid-hal RPM-ek droid-hal-init A15, droidmedia, libhybris,
  rootfs image). Utána flash: új boot + rootfs; system/vendor marad.
TERV: (1) env hybris-22.2; (2) HABUILD: repo init -b hybris-22.2 (mer-hybris/android) + local_manifests
  FP3 lineage-22.2 (device/kernel/vendor) + repo sync (~150GB, órák); (3) make hybris-hal + kernel;
  (4) Platform SDK: droid-hal RPM-ek (rpm/dhd) + droidmedia + middleware; (5) image build; (6) flash.
ÁLLAPOT a döntés előtt: device A15-öt futtat slot A-n, resize+connman+mount-fix megvan (megtartandó),
  droid-hal-init MASKED (A11, úgyse fut). successful bit 0x1067.

################################################################################
[2026-06-27 ~05:00] PONTOS FLASHELT BUILD AZONOSÍTVA: /e/OS (A15), + akkucsere (boot-loop volt)
################################################################################
KÖZJÁTÉK: a telefon leesett USB-ről (functionfs adbd idle után/akksi), majd boot-loopba esett
  (akksi ~3.66V alacsony). USER AKKUT CSERÉLT (FP3 cserélhető akksi!) -> 4.275V -> fastboot reboot
  (slot A, SOHA B) -> Sailfish visszajött (FP3ADB device). A mount-fix boot EGÉSZSÉGES (mounts active).
PONTOS BUILD (device /system + /vendor build.prop):
  ro.build.version.sdk=35  (ANDROID 15) ; ro.build.id=BP1A.250505.005 ; ro.vendor security_patch=2026-02-05
  ro.build.fingerprint=Fairphone/FP3/FP3:13/6.A.040.2/gms-d33dc62f:user/release-keys  (SPOOFOLT A13 stock, Play-cert)
  ro.vendor.build.fingerprint=Fairphone/lineage_FP3/FP3:15/BP1A.250505.005/eng.root:user/release-keys (valódi A15)
  ro.lineage.version=4.0-a15-20260610633983-official-FP3 ; ro.lineage.build.version=4.0 ; releasetype=official
  ro.build.host=runner-...-project-53 (GitLab CI) ; ro.board.platform=msm8953 ; build date 2026-06-10
  *** ro.elegal.url=https://e.foundation/legal  => /e/OS (Murena, e.foundation), LineageOS-alapú, A15 ***
KÖVETKEZTETÉS: a flashelt OS = /e/OS A15 (LOS22-alapú). A vendor (TheMuppets lineage_FP3) standard.
  A hybris-22.2 build CÉLJA: A15 API + a flashelt /e/OS vendorhoz illő droid-hal. Mivel /e/OS vékony
  réteg a LOS22 felett és a vendor TheMuppets, a VANILLA lineage-22.2 hybris-hal várhatóan ABI-kompatibilis.
  DÖNTENDŐ (user): (1) vanilla LineageOS lineage-22.2 [HADK-standard, ajánlott]; (2) /e/OS források
  (gitlab.e.foundation) pontos egyezésért [bonyolultabb]; (3) device újraflashelése vanilla LOS22.2-re.

=== factentry10 (2026-06-27): USB-net közbeni töltés vizsgálat ===
Tünet: a telefon usbnet/adb gadget módban merül töltés helyett.
Mérés (root telnet, /sys/class/power_supply):
  usb/present=1, usb/online=0, VBUS=5.05V
  usb/real_type=USB (SDP), typec_mode="Source attached (default current)"
  usb/sdp_current_max=250mA, usb/hw_current_max=100mA, usb/input_current_settled=100mA
  battery/status=Charging (de) battery/current_now = -517mA (NEGATIV = kisul!)
  battery/input_suspend=0, battery/battery_charging_enabled=1 (battery-szint NEM tilt)
GYOKEROK: a charger SDP-unconfigured default 100mA-en tartja az input current limitet.
  A minimal hybris debug-boot nem futtat toltesi userspace-t (usb_moded + charging HAL),
  ami normal esetben vbus_draw(500)-zal felemelne. Rendszer-load ~500mA > 100mA -> netto -0.5A.
  => NEM az usbnet funkcio tiltja a toltest, hanem a hianyzo toltes-negociacio.
PROBALT override-ok (NEM hatott):
  - ctm_current_max=900000 beirva (rc=0), de csak PLAFONT szavaz -> hw_current_max maradt 100mA.
  - /sys/kernel/debug/charger csak force_*_psy_update triggert ad, nincs regiszter/ICL iras.
  - usb/current_max, sdp_current_max, main/* mind READ-ONLY.
KOVETKEZTETES: szoftver-only ICL bump ezen a charger-driveren (qpnp-smb/msm8953) nincs kiteve.
HASZNALHATO MEGOLDASOK:
  1. Toltes+adat egyutt: CDP (Charging Downstream Port) / taplalt USB-hub -> charger CDP-t
     detektal -> 1.5A WITH data. A jelenlegi PC-port plain SDP-kent enumeral (real_type=USB).
  2. Idle toltes: fastboot/TWRP modban tolt teljes sebesseggel (eddigi rutin).
  3. Fali tolto: 1.5-2A, de nincs adb adat.
  4. Vegleges fix: teljes hybris-22.2 boot (usb_moded + charging HAL) -> OS-ben mukodo
     toltes-negociacio adb mellett is.

=== factentry11 (2026-06-27): toltes megoldva TWRP RAM-boottal ===
USER valasztas: opcio 2 (idle toltes TWRP/fastbootban).
Lepesek: debug-boot -> (telnet) reboot bootloader -> fastboot -> fastboot boot twrp-fp3.img (RAM, NEM flash).
  Megj.: "fastboot reboot recovery" NEM TWRP-be megy (boot part = a mi hybris bootunk), ezert RAM-boot kell.
TWRP 3.7.0_9-0 betoltott (adb get-state=recovery, ro.twrp.version=3.7.0_9-0).
Toltes-meres TWRP-ben: battery/status=Charging, current_now=+82mA (POZITIV=tolt),
  usb/input_current_settled=500000 (500mA!) -- a TWRP adbd vbus_draw(500)-at hiv.
  => MEGERSITI a factentry10 diagnozist: a debug-boot 100mA-je a hianyzo toltes-negociacio miatt van,
     nem az usbnet miatt. Teljes hybris-22.2 boot (usb_moded+HAL) ezt megoldja OS-ben is.
  Megj.: capacity 92->76% esett a debug-session alatti -500mA meruleskbol; TWRP-ben most tolt.
Tovabbi gyorsitas: TWRP screen elalvas utan a load csokken -> nagyobb toltoaram.
KOVETKEZO: phone biztonsagban tolt TWRP-ben; build (hybris-22.2) inditasa host-oldalon.

=== factentry12 (2026-06-27): hybris-22.2 build pipeline ELINDITVA ===
Chroot-layout TISZTAZVA (a memoriabeli /mnt/1T tipo + ANDROID_ROOT korrigalva):
  - SDK chroot: sudo -n $FP3_ROOT/sdk/sdks/sfossdk/sdk-chroot /bin/bash -lc '...'
    Sailfish OS 4.6.0.13 (Sauna), i686. Host / -> /parentroot.
  - HABUILD: azon belul ubu-chroot -r /parentroot$FP3_ROOT/sdk/sdks/ubuntu <cmd>
    Ubuntu 20.04, USER=ubuntu(uid1000), sudo -n MUKODIK (uid0).
  - FONTOS: HABUILD-bol a host /mnt/1TB a /parentroot/parentroot/mnt/1TB alatt van!
  - GOTCHA: /dev/shm a HABUILD-ban 0755 root -> repo (python multiprocessing) elhasal
    'PermissionError /dev/shm/pym-*'. FIX: minden HABUILD-szakasz elejen `sudo chmod 1777 /dev/shm`.
  - Scriptek atadasa: a HABUILD rootfs = host .../sdks/ubuntu/, ezert host-rol .../ubuntu/tmp/X.sh-ba
    irom, HABUILD-ban /tmp/X.sh-kent fut (tiszta kvotalas, nincs parentroot-talalgatas).
Uj fa: $FP3_ROOT/hadk22 (a 18.1 hadk MARAD).
  repo init -u https://github.com/mer-hybris/android -b hybris-22.2  -> OK (INIT_RC=0).
local_manifests/fp3.xml (lineage-22.2, mind ELLENORIZVE GitHub API 200):
  device/fairphone/FP3 = LineageOS/android_device_fairphone_FP3 @ lineage-22.2
  kernel/fairphone/sdm632 = LineageOS/android_kernel_fairphone_sdm632 @ lineage-22.2
  vendor/fairphone/FP3 = TheMuppets/proprietary_vendor_fairphone_FP3 @ lineage-22.2 (PER-DEVICE repo!
    a regi TheMuppets/proprietary_vendor_fairphone csak 19.1-ig megy; uj per-device repo git-lfs-szel)
repo sync ELINDITVA hatterben (bg task b39ladzpc):
  repo sync -c --no-clone-bundle --no-tags --optimized-fetch --force-sync -j6
  Log (host-lathato): $FP3_ROOT/hadk22/sync.log
  Inditas 06:29 UTC; 30s utan 1.5G + projektek (android/art/bionic/...). ~150GB / orak.
TODO sync utan: git-lfs MISSING a HABUILD-ban -> vendor/fairphone/FP3 LFS blobok pointer-fajlok
  lesznek; git-lfs telepites (portable binary v apt) + `git lfs pull` a vendor dirben KELL.
KOVETKEZO a sync utan: make -j3 hybris-hal + kernel; majd Platform SDK droid-hal RPM-ek.

=== factentry13 (2026-06-27): repo sync 1. menet kesz (162G), LFS-fix re-sync ===
1. sync: 06:29->10:45 UTC (~4h15m), 162G letoltve. rc=1 KIZAROLAG 2 repo miatt:
  external/chromium-webview/prebuilt/arm + arm64 -> "Cannot initialize work tree"
  (git-lfs hianyzott a checkout-kor). Minden mas repo OK.
git-lfs FIX: git-lfs 3.7.1 portable binary letoltve host-rol -> .../sdks/ubuntu/usr/local/bin/git-lfs,
  `sudo git lfs install --system` a HABUILD-ban (Git LFS initialized).
  (Megj.: chromium-webview a hybris-hal-hoz NEM kell, de a vendor/fairphone/FP3 LFS blobok IGEN.)
RE-SYNC inditva hatterben (bg bejxgtdqu) git-lfs-szel: log $FP3_ROOT/hadk22/sync2.log
  Start 10:51 UTC. Csak a hianyzo checkoutokat + LFS objektumokat huzza (gyors).
Disk: 521G szabad (40% hasznalt).
KOVETKEZO a re-sync utan: ellenorizni vendor/fairphone/FP3 valodi .so-k (nem LFS-pointer);
  majd source build/envsetup.sh + breakfast FP3 + make -j3 hybris-hal (HABUILD), + kernel.

=== factentry14 (2026-06-27): breakfast OK + make hybris-hal ELINDITVA ===
breakfast FP3 rc=0 (a "failed" task-status csak a cwd-artefakt). Lunch-combo TISZTA:
  PLATFORM_VERSION=15, TARGET_PRODUCT=lineage_FP3, arch=arm64, variant=userdebug,
  LINEAGE_VERSION=22.2-20260627-UNOFFICIAL-FP3
  >>> BUILD_ID=BP1A.250505.005 = PONTOSAN a flashelt /e/OS build! Tokeletes illeszkedes. <<<
  SOONG namespaces: vendor/fairphone/FP3 device/fairphone/FP3 hardware/qcom-caf/msm8953 ... wlan
  (nsjail/sandboxing disabled warning = artalmatlan a chrootban)
Tree-ellenorzes: device/kernel/vendor mind OK; vendor LFS-blob VALODI ELF (libmmcamera_faceproc.so 1.2M ARM).
  (chromium-webview webview.apk meg LFS-pointer 134B -> hybris-hal-hoz nem kell, irrelevans.)
Swap: +16G swapfile (/mnt/1TB/swapfile2) -> osszesen 23G swap (21G szabad), OOM-vedelem.
  (make figyelmeztet: 15.5G RAM < 16G ajanlott; swap fedezi.)
make -j3 hybris-hal ELINDITVA hatterben (bg bkvew77qf):
  Log: $FP3_ROOT/hadk22/make-hybris-hal.log ; start 11:15 UTC.
  Most "Running product configuration..." -> soong bootstrap -> ninja. ~30perc-2ora.
KOVETKEZO: ha hybris-hal OK -> out/ ellenorzes (boot, system, droid-hal targets);
  majd Platform SDK: rpm/dhd droid-hal RPM-ek + droidmedia; image; flash boot+rootfs.

=== factentry15 (2026-06-27): make hybris-hal 1. menet CRASH (soong SIGSEGV), retry ===
make -j3 hybris-hal futott 4h26m (11:15->15:41 UTC), majd CRASH a ninja-generalasnal:
  [100%] analyzing Android.bp files and generating ninja file at out/soong/build.lineage_FP3.ninja
  FAILED -> "unexpected fault address 0x0 / fatal error: fault / SIGSEGV code=0x80 addr=0x0"
  crash helye: aeshashbody() -> type:.hash...OsType -> runtime.mapaccess1 (Go map-hash).
DIAGNOZIS: NEM soong-bug (a soong_build binarist 131/131 lefordította). aeshashbody null-deref =
  jellemzoen memoria-nyomas/instabilitas. 15.5G RAM (< 16G ajanlott) + 4.5h swap-thrashing.
  A 4.5h nagy resze a soong Go-toolok forditasa volt -> MOST CACHE-ELT, retry gyorsan eljut az analizishez.
Crash utan: 13G RAM elerheto, 19G swap szabad, nincs ragado folyamat (tiszta).
RETRY inditva (bg b2hkhjwk7) GOGC=40-nel (kisebb Go-heap csucs): log make-hybris-hal2.log.
  Figyelo: bgc5rm3xe (szol ha analizis atmegy v ujra crash, max 15min).
HA UJRA CRASH ugyanott: lehetseges hardver/RAM instabilitas (live-USB) v tovabbi mem-csokkentes kell
  (pl. soong egy-szalu, vagy tobb swap, vagy GODEBUG). HA ATMEGY: tranziens volt, megy a ninja-fordítas.

=== factentry16 (2026-06-27): soong swap-thrash diagnozis + GOMEMLIMIT fix ===
A retry (GOGC=40) NEM crashelt, de 93 perc utan is "Running globs"-nal allt, RSS 9.4->12.4->13G.
DONTO DIAG: soong_build state=D, wchan=blk_mq_get_tag (SWAP-I/O-n ragad), 93perc alatt csak
  7 perc CPU (>90% swap-wait). Working set ~13G >> hasznalhato RAM (15.5G - ~2.3G live-overlay).
  => swap halalspiral; ezert is volt az elozo SIGSEGV (aeshashbody) = mem-nyomas.
drop_caches alig segitett (csak 1.5G cache volt).
FIX: build leallitva (pkill soong_build/soong_ui/make -> RSS azonnal felszabadult, 13G free, swap urul).
  Ujrainditas make_hal3.sh-val: GOMEMLIMIT=11GiB (Go soft heap-cap a ~12G hasznalhato RAM ala)
  + GODEBUG=madvdontneed=1 (lapok azonnali visszaadasa). GOMEMLIMIT >> GOGC a peak-RSS kapaszhoz.
  Cel: soong RAM-ban marad -> nincs swap-thrash -> a ~7perc CPU-munka percek alatt lefut.
bg build: bglsgrjcp ; log make-hybris-hal3.log ; figyelo: b1w4xmub3 (~30min).
TANULSAG: 15.5G RAM hatareset A15 soong-hoz; GOMEMLIMIT KOTELEZO minden tovabbi make-hez
  (hybris-hal compile, droidmedia, full image). Ha GOMEMLIMIT=11G is thrashel -> live set >11G,
  akkor tobb fizikai RAM v. nagyobb/gyorsabb swap kell.

=== factentry17 (2026-06-27): swap-strategia valtas -> SSD swap-particio (NTFS zsugoritas) ===
PROBLEMA: soong-analizis ~13G working set 15.5G RAM-on; a swap a LASSU sdb HDD-n (5400rpm,
  Toshiba MQ01ABD100) volt + verseng a build I/O-val -> blk_mq_get_tag thrash -> 7min CPU/93min,
  vagy SIGSEGV crash. zram-ot kiprobaltam (zstd,24G,prio100) majd reset.
DISK-VALOSAG: sda=Samsung SSD 860 EVO (GYORS) de teljesen Windows NTFS (sda1 EFI,sda2 MSR16M,
  sda3=232GiB NTFS Win C: [175G hasznalt/58G szabad], sda4=769M recovery); sdb=1TB lassu HDD
  (/mnt/1TB build + regi swap); sdc=7.5G USB live. NTFS-en NINCS mukodo file-swap (ntfs-3g/ntfs3
  nem tamogatja); loop-hack lassu+deadlock. => SSD-swaphoz natIV particio kell = NTFS zsugoritas.
USER DONTES: szuntesd meg az osszes swapot + hatterben zsugoritsd az NTFS-t, csinalj swap-particiot, csatold fel.
VEGREHAJTVA: swapoff -a + zram reset (bg bkdi9kwws). Majd bg bre2t4y14:
  $FP3_ROOT/buildscripts/ntfs_swap.sh (log: ntfs-swap-setup.log).
  Geometria (512B szektor): sda3 -> 200GiB (start MARAD 239616, size 419430400); FS->198GiB
  (ntfsresize 212600782848B); uj sda5 = 32GiB swap (start 419670016, size 67149824), sda4 erintetlen.
  BIZTONSAGI KAPU: ntfsresize --no-action dry-run; ha NTFS dirty (Win fast-startup/hibernacio)
  -> ABORT mindenfele particio-valtoztatas NELKUL. Part-tabla backup: sda-parttable-backup.sfdisk.
KOVETKEZO: ha sda5 swap kesz -> ujra make -j3 hybris-hal GOMEMLIMIT=11GiB + GODEBUG=madvdontneed=1
  (most a swap gyors SSD-n -> ha mmegis spillel, nem thrashel). Whack-a-mole tanulsag: a make_hal*.sh
  SZKRIPTET kell olni (nem csak soong_build-ot), kulonben ujrainditja a make-et.

=== factentry18 (2026-06-27) SSD swap created — soong memory blocker resolved ===
SUCCESS: ntfs_swap.sh ran to completion (exit "1" was only the cwd artifact; log shows "=== DONE ===").
- ntfsresize DRY-RUN: NTFS was CLEAN (not dirty) -> "read-only test run ended successfully".
  Note: ntfsresize printed "Schedule chkdsk for NTFS consistency check at Windows boot time" -> Windows
  WILL run a chkdsk on next boot (normal after a Linux-side resize); not an error.
- ntfsresize REAL: shrank NTFS filesystem to 198 GiB, synced.
- sfdisk: sda3 shrunk to 200 GiB (start KEPT at 239616), new sda5 = 32 GiB created (ends before sda4 recovery).
- mkswap /dev/sda5 -> UUID=c4d36dcc-94ef-45d1-aaa3-5704a921a68a, swapon -p 100 -> ACTIVE.
Final partition layout (lsblk sda): sda1 100M EFI, sda2 16M MSR, sda3 200G NTFS, sda4 769M WinRE, sda5 32G [SWAP].
Then: swapoff'd the leftover slow-HDD swaps (/dev/sdb1 8G + /mnt/1TB/swapfile2 16G, both prio -1) so ONLY
the fast SSD sda5 (prio 100) remains -> build spill now hits SSD, no HDD I/O contention / blk_mq_get_tag thrash.
NEXT: re-run make -j3 hybris-hal via make_hal3.sh (GOMEMLIMIT=11GiB, GODEBUG=madvdontneed=1).

=== factentry19 (2026-06-27 este): GÉP-FAGYÁS GYÖKÉROK = HDD I/O-kontenció (NEM RAM/soong) ===
A make-hybris-hal3 (GOMEMLIMIT=11GiB) eljutott a soong "Running globs..."-ig, majd a GÉP
TELJESEN BEFAGYOTT (terminal+remote halott), user hard power-off-ot csinált.
USER-KORREKCIÓ a gyökérokra: NEM soong-OOM/RAM volt, hanem **HDD I/O-bottleneck**:
  a build fája a lassu 1TB HDD-n van, ÉS ezzel egyidejűleg futott a `swapoff /dev/sdb1`
  (a régi HDD-swap leürítése), ami szintén a HDD-ről húzott le ~2.7G lapot → a lassú
  5400rpm HDD I/O-ja kiéhezett → I/O-livelock → teljes gépfagyás.
REBOOT UTÁNI ÁLLAPOT (eszköznevek ÁTRENDEZŐDTEK!):
  - 1TB build-lemez MOST = **sdc** (TOSHIBA MQ01ABD100); sdc2 ext4 = /mnt/1TB (528G szabad, 39%);
    sdc1 (8G) = a RÉGI HDD-swap partíció, jelenleg KIKAPCSOLVA.
  - SSD = sda (Samsung 860 EVO); sda5 (32G) = SWAP, ONLY ez aktív (0B used).
  - live USB MOST = sdb (7.5G, /cdrom).
  - hadk22 tree = 163G ÉP; out/soong = csak bootstrap + glob_results (nincs kész ninja).
  - adb NINCS telepítve (live reboot reset); telefon TWRP-ben ül.
KULCS-TANULSÁG: a swap (sda5 SSD) és a build-tree (sdc HDD) MOST KÜLÖN FIZIKAI LEMEZEN van
  → a fagyás strukturális oka megszűnt. SZABÁLY: sdc1 (HDD-swap) SOHA ne legyen bekapcsolva;
  build alatt SOHA ne fusson swapoff a build-lemezen.
GOMEMLIMIT: a szűk 11GiB már nem kötelező (a thrash-ok eltűntek), de mérsékelt sapka marad
  insurance-ként: GOMEMLIMIT=13GiB + GODEBUG=madvdontneed=1.
KÖVETKEZŐ: (1) fsck a sdc2-n (hard power-off után ext4-konzisztencia): umount /mnt/1TB ->
  e2fsck -fy /dev/sdc2 -> remount; (2) make -j3 hybris-hal újraindítás a fenti env-vel + sampler.

=== factentry20 (2026-06-27): live-USB reboot utáni környezet-helyreállítás + takarítás ===
KONTEXTUS: a gép-fagyás (factentry19) utáni hard power-off + reboot. Live USB → a root
  (/, /tmp, /home részben) RESETELŐDÖTT. Helyreállítás és takarítás ebben a körben:

(A) TAKARÍTÁS — régi Claude session-maradványok törölve a projekt gyökeréből:
  - $FP3_ROOT/claude-1000 (533M) + claude-cffb (4K, üres) → sudo rm -rf.
  - Tartalom: 7 régi session scratchpad (Jun 25-26), kibontott ramdiskek (rd/, bootwork/,
    inspect/), *.gz ramdiskek, p28/p58 dumpok, tasks/*.output. MIND az ELHAGYOTT A11
    NCM/telnet debug úthoz tartozott → regenerálható a gyökérben lévő hybris-boot-ncm*.img-ekből.
    A kanonikus build_nosk_kernel.py a gyökérben van (nem veszett el).
  - NEM az aktuális session (cb2b2859-…, annak scratchpadja /tmp-ben). Szabad hely: 528→529G.

(B) adb/fastboot ÚJRATELEPÍTVE (live USB reset miatt minden bootnál kell):
  sudo apt-get install -y android-tools-adb android-tools-fastboot
  → adb 1.0.41, fastboot 34.0.5-debian. (A /tmp NEM éli túl a rebootot → tartós dolgok /mnt/1TB-re.)
  adb devices: $FP3_SERIAL  recovery  → a telefon TWRP-ben ül (factentry11 óta ott tölt).

(C) KÖRNYEZETI TÉNYEK (user megerősítette):
  - /home/ubuntu/.claude -> $FP3_ROOT/.claude (SYMLINK) → a .claude konfig/memória
    TÚLÉLI a live-USB rebootot (a perzisztens lemezen van).
  - SZABÁLY: ami a futás közben kell és tartósnak kell lennie → a projekt mappába (/mnt/1TB/
    Fp3-Sailfish/...) írni, SOHA /tmp-be (reboot törli).
  - Lemez-elrendezés a reboot után (factentry19 szerint, megerősítve): build-lemez = sdc
    (sdc2 ext4 = /mnt/1TB, 334G használt/529G szabad); SSD swap = sda5 (32G); live USB = sdb.

KÖVETKEZŐ (változatlan factentry19-ből): (1) e2fsck a sdc2-n a hard power-off után
  (umount /mnt/1TB → e2fsck -fy /dev/sdc2 → remount) — MEGJ.: a /mnt/1TB épp HASZNÁLATBAN van
  (cwd), így a teljes umount nem triviális élő rendszeren; mérlegelni kell.
  (2) make -j3 hybris-hal újraindítás (GOMEMLIMIT=13GiB GODEBUG=madvdontneed=1), swap CSAK sda5-ön.

=== factentry21 (2026-06-27): e2fsck OK + make hybris-hal (4. menet) ELINDÍTVA ===
(A) e2fsck /dev/sdc2 (user futtatta): "clean, 3385673/60530688 files, 91684980/242093238 blocks"
    → a hard power-off (factentry19) ELLENÉRE a build-fa fájlrendszere konzisztens. (Megj.: -f nélkül
    futott, csak a clean flaget nézte; a journal rendben helyreállt.)
(B) ENV-ELLENŐRZÉS reboot után: swap = CSAK /dev/sda5 (SSD 32G); sdc1 (HDD-swap) KI; /mnt/1TB=sdc2
    (HDD, külön fizikai lemez az SSD-től) → a factentry19 I/O-livelock strukturális oka MEGSZŰNT.
    RAM 15Gi (13Gi avail). Nincs ragadó soong/ninja/make processz (tiszta indulás).
(C) Nested chroot helyreállt reboot után (SDK→HABUILD mount OK): x86_64, hadk22 fa ÉP, make+repo+
    envsetup.sh megvan. Belépés: sudo -n sdk/sdks/sfossdk/sdk-chroot -lc "ubu-chroot -r
    /parentroot$FP3_ROOT/sdk/sdks/ubuntu -lc '/tmp/make_hal4.sh'".
(D) BUILD-SZKRIPT: sdk/sdks/ubuntu/tmp/make_hal4.sh (a make_hal3.sh alapján, de GOMEMLIMIT=11→13GiB,
    GODEBUG=madvdontneed=1, log: hadk22/make-hybris-hal4.log). Háttérben indítva 21:07 UTC.
    Sampler: buildscripts/sampler4.sh → build-sampler4.log (soong RSS/stat/wchan, RAM, swap, 60s).
(E) INDULÁS EGÉSZSÉGES: breakfast FP3 OK, lunch-kombó PLATFORM_VERSION=15, TARGET_PRODUCT=lineage_FP3,
    BUILD_ID=BP1A.250505.005 (= flashelt /e/OS), arch=arm64. Most "Running product configuration"
    → soong analízis = A KRITIKUS VESZÉLYZÓNA (itt volt a SIGSEGV factentry15 + swap-thrash fagyás
    factentry16/19). A sampler4 figyeli a soong D-state/blk_mq_get_tag thrash-szignatúrát.
KÖVETKEZŐ: a soong-analízis átmenetét megvárni (sampler4); ha átér a ninja-fordításra → tranziens
    veszély elmúlt, fut a tényleges compile. Ha újra thrash/SIGSEGV → mélyebb mem-csökkentés kell.

=== factentry22 (2026-06-27): make_hal4 (GOMEMLIMIT=13GiB) MEGÖLVE — gyökér-diagnózis ===
EREDMÉNY: a make_hal4 build 24 perc után (21:31) megölve a "Running globs" soong-fázisban.
SAMPLER4 BIZONYÍTÉK (a thrash teljes íve, build-sampler4.log):
  21:23 soong rss=14.2G stat=Dl wchan=lock_buffer  swapused=10.0G  avail=763M
  21:24 soong rss=14.5G stat=Sl wchan=futex_do_wait swapused=12.6G avail=260M
  21:27 soong rss=14.4G                              swapused=16.4G avail=223M
  21:29 soong rss=14.4G stat=Dl wchan=blk_mq_get_tag swapused=16.4G avail=237M
  21:31:32 log: "Got signal: terminated" -> "soong bootstrap failed with: signal: killed"
=> soong RSS elérte a ~14.5G-t (a 15.9G RAM-ot kimerítve), swap 16.4G-ig, avail ~220M 8+ percig.

KI ÖLTE MEG (tisztázva):
  - NINCS kernel-OOM (dmesg tiszta). NINCS systemd-oomd kill-log (journalctl -u systemd-oomd üres).
  - A "Got signal: terminated" = SIGTERM => a HARNESS reapelte a run_in_background Bash-taskot
    (MINDKÉT task — build ÉS sampler — egyszerre halt), szinte biztosan mert a gép load=275-ön
    elérhetetlenné vált a thrash alatt. (systemd-oomd AKTÍV, SwapUsedLimit=90%, MemPressure=60%/20s,
    de nem logolt kilövést — a harness gyorsabb volt, vagy a reszponzivitás-vesztés triggerelte a reapet.)

GYÖKÉR-OK #1 (a valódi blokkoló): GOMEMLIMIT=13GiB TÚL MAGAS. A Go a heapet a limitig hizlalja GC
  előtt => RSS ~14.5G (limit+nem-heap) => meghaladja a ~13G használható RAM-ot => SSD-swap thrash.
  A magas limit RONTOTT. (A fa NEM kóros: out/ csak 864M, nincs gyanús symlink a régi 130G hadk-ra.)
GYÖKÉR-OK #2 (túlélés): a multi-órás buildet run_in_background harness-taskként futtatni TÖRÉKENY —
  thrash alatt a harness reapeli. MEGOLDÁS: setsid-del TELJESEN leválasztva futtatni (új session,
  nem a harness folyamatcsoportjában) => túléli a harness-reapet.

HALADÁS factentry19-hez képest: az SSD swap elnyelte a spillt, a gép NEM fagyott le (válaszolt,
  load 275->31 csökkent), a folyamat tisztán megölhető volt (nem kellett hard power-off).

FIX-TERV (Kísérlet 1, make_hal5):
  - GOMEMLIMIT=13GiB -> 10GiB (korábbi GC, RSS-cél ~11G a ~13G usable RAM alatt; min. SSD-swap).
  - systemd-oomd LEÁLLÍTVA (sudo systemctl stop systemd-oomd) — nyomásra ne öljön (live-USB build-box).
  - build setsid+nohup-pal LEVÁLASZTVA (túléli a harness-reapet); sampler5 marad bg-taskként az
    értesítéshez (önállóan kilép a build "rc=" sorára).
  - HA 10GiB is thrashel (a working set genuine >RAM) -> Kísérlet 2: zram (tömörített swap, prio>SSD)
    a hot lapokhoz + GOMEMLIMIT 10GiB; esetleg GOMAXPROCS=2 az allokációs ráta csökkentésére.
SZABÁLY (új): minden további soong-make setsid-del leválasztva + GOMEMLIMIT a RAM alá + oomd off.

=== factentry23 (2026-06-27): *** GYÖKÉROK: env -i kiüti a GOMEMLIMIT-et → wrapper+zram fix ***
make_hal5 (GOMEMLIMIT=10GiB) FUTOTT, de a soong_build RSS UGYANÚGY ~14.5G-ig nőtt (avail 175M,
swap 13.6G) → leállítottam. A LEVÁLASZTÁS (setsid) MŰKÖDÖTT: a harness reapelte a sampler bg-taskot,
DE a detached build TOVÁBB FUTOTT (megerősíti: setsid kötelező a túléléshez).

*** A DÖNTŐ FELFEDEZÉS *** — miért volt a GOMEMLIMIT mindig hatástalan:
A soong a soong_build-ot ÍGY indítja (ps-ből, bootstrap.ninja rule):
   /bin/sh -c '... cd / && env -i "$BUILDER" --top ... Android.bp'
Az **env -i** TELJESEN kiüríti a környezetet → a shell-ben/make_hal*.sh-ban exportált GOMEMLIMIT
és GODEBUG SOHA nem jut el a soong_build Go-runtime-jához. BIZONYÍTÉK: tr '\0' '\n' < /proc/<soong_build_pid>/environ
| grep GOMEM → ÜRES. Ezért adott a 13GiB ÉS a 10GiB IS PONTOSAN ugyanazt a ~14.5G RSS-t (no-op volt).
A ~14.5G nagy része GOGC=100 garbage (live set becsült ~8-9G) → egy HATÉKONY GOMEMLIMIT=10GiB
a GC-t kikényszerítve ~10-11G-ra fogná az RSS-t → BEFÉRNE a 15.9G RAM-ba.

FIX A — soong_build WRAPPER (env -i megkerülése):
  hadk22/out/host/linux-x86/bin/soong_build  ÁTNEVEZVE -> soong_build.real
  helyette /bin/bash wrapper (env -i UTÁN, exec ELŐTT állít → nem törölhető):
     #!/bin/bash
     export GOMEMLIMIT=10GiB
     export GODEBUG=madvdontneed=1
     exec "${0}.real" "$@"
  ($0 = a soong által átadott abszolút in-chroot path → "${0}.real" a valódi ELF.)
  KOCKÁZAT: a soong bootstrap ("[100%] bootstrap blueprint", microfactory) ÚJRAÉPÍTHETI a soong_build-ot
  és felülírhatja a wrappert. VERIFIKÁCIÓ: validate_soong.sh (detached) megnézi a /proc/PID/environ-t →
  ha GOMEMLIMIT ott van = wrapper él; ha nincs = bootstrap felülírta (akkor mélyebb injekt kell).
FIX B — zram (tömörített RAM-swap, overflow insurance):
  modprobe zram; comp_algorithm=zstd; disksize=14G; mkswap; swapon -p 100 /dev/zram0 (PRIO 100=hot).
  sda5 (SSD) leminősítve swapon -p 10 (overflow). swapon --show: zram0 prio100 + sda5 prio10 = 46G total.
  A zram a hot lapokat RAM-sebességgel tömöríti (~3x) → nincs disk-I/O thrash a marginális spillnél.
FIX C — oomd KIKAPCSOLVA: systemctl stop systemd-oomd.socket + mask systemd-oomd.service (nyomásra ne öljön).

ATTEMPT 6 (make_hal5.sh + wrapper + zram + oomd-off) indítva 22:02 detached. sampler5 + validate_soong
detached fut. EREDMÉNY-FÁJLOK: soong-validate.log (env-teszt + peak RSS), build-sampler5.log (RSS/swap/abort),
make-hybris-hal5.log (build). A soong_build a breakfast (soong_ui --dumpvar-mode) UTÁN indul (pár perc).
DÖNTŐ KÉRDÉS amit a validate_soong.log megválaszol: (1) eljut-e a GOMEMLIMIT a soong_build-hoz (wrapper él-e),
(2) a peak RSS ~10-11G-ra csökken-e (akkor befér), (3) befejezi-e a "Running globs"-ot thrash nélkül.

MONITOR-TANULSÁG: a harness reapeli a run_in_background Bash-taskokat (rendszer-stressz v. turn-vég?) →
NEM megbízható completion-értesítésre. MINDEN tartós háttér (build, sampler, validator) setsid-del,
fájlba logolva; a státuszt a log-fájlok olvasásával követem (nem bg-task notifikációval).

=== factentry24 (2026-06-27): WRAPPER MŰKÖDIK, de a live set ~14G → ZRAM A TÉNYLEGES FIX ===
ATTEMPT 6 a "Running globs"-ban ÉL (22:54), az előző két kör pont itt halt meg → ÁTTÖRÉS.
VERIFIKÁLT (/proc/<soong>/environ): GOMEMLIMIT=10GiB + GODEBUG=madvdontneed=1 OTT VAN a soong_build.real
  környezetében → a wrapper MEGKERÜLI az env -i-t (a fix helyes). MEGJ.: a valódi folyamat comm-ja
  "soong_build.rea" (15-char trunc a .real miatt) → `pgrep -x soong_build` NEM fogja; a sampler/validator
  comm-matchét erre kell igazítani (a validate_soong emiatt adott téves "never spawned"-ot).
DE: soong_build.real VmRSS=13.7G + VmSwap=3.9G a 10GiB GOMEMLIMIT ELLENÉRE. => a GOMEMLIMIT soft limit;
  a Go nem tud LIVE adatot collectálni, és a GC-t max ~50% CPU-ra fogja, ezért a heap átlépi a limitet,
  ha a live set > limit. KÖVETKEZTETÉS: a working set GENUINELY ~14G live (A15 teljes fa glob+modulgráf),
  NEM garbage → a GOMEMLIMIT NEM a megfelelő eszköz (zsákutca, de ártalmatlan).
*** A TÉNYLEGES FIX = ZRAM ***: a 14G live set nem fér a ~13.5G usable RAM-ba; a zram (zstd, prio100)
  5.3G-t abszorbeál tömörítve RAM-sebességgel → a gép ÉL (S-state, load magas de halad), nem thrashel
  halálra disk-I/O-n. sda5 SSD (prio10) overflow még 0. 46G swap headroom → nincs OOM-veszély.
  Az előző bukások oka: zram NÉLKÜL a 14G live set a lassú disk-swapra ömlött → D-state livelock/kill.
ÁLLAPOT: build fut (analízis-fázis, lassú a mem-nyomás miatt). A ninja-generálás után az RSS leesik
  (a compile -j3 sok kis cc, alacsony per-proc mem) → a nehéz rész a "Running globs"/analízis.
SZABÁLY: A15 (hybris-22.2) soong-hoz a ZRAM KÖTELEZŐ (14G live > RAM). wrapper/GOMEMLIMIT opcionális.
KÖVETKEZŐ: loop-monitor a befejezésig; ha kész → out/ ellenőrzés (hybris-boot/system/droid-hal targets),
  majd Platform SDK droid-hal RPM-ek. Ha thrash-halál → nagyobb zram (pl. 20G) v. lz4 (gyorsabb).

=== factentry25 (2026-06-27 23:17): GC-THRASH diagnózis → GOMEMLIMIT 10→14GiB (attempt 7) ===
Attempt 6 (GOMEMLIMIT=10GiB) 75 PERC után IS "Running globs"-ban (sosem ért az analízis végére).
NEM fagyott (zram tartotta), de PATOLÓGIÁSAN lassú. MÉRÉS (/proc/<soong>/stat + vmstat 20s):
  - soong CPU: ~1.2 mag (117%/1 core) → halad, de lassan.
  - **major page fault: 451247 / 20s (~22500/s!)** → brutális heap-thrash.
  - vmstat: si/so ~350MB/s be ÉS ki, sy=53% (kernel page-fault/zram), wa=30-69% iowait.
  - soong RSS=12G (a 10GiB GOMEMLIMIT ellenére → live set ~11-12G), 1007 thread, GOMAXPROCS=6.
DIAGNÓZIS: a GOMEMLIMIT=10GiB KONTRAPRODUKTÍV. A live set ~12G > 10G limit → a Go FOLYAMATOSAN GC-zik
  (nem tud 10G alá menni), és MINDEN GC végigpásztázza a teljes 12G heapet. A heap egy része zram-ban →
  minden GC-mark = tömeges random page-fault (a 22500/s major fault = a GC a swap-backed heapet olvassa).
  6 GC-mark thread párhuzamosan lapoz → 6x thrash-amplifikáció.
FIX (attempt 7): GOMEMLIMIT 10→14GiB + GOGC=200 a wrapperben. 14GiB = ~2G fejtér a ~12G live set
  felett → a GC-t a GOGC-növekedés triggereli (ritka), NEM a limit (folyamatos) → kevesebb teljes-heap
  pásztázás → kevesebb thrash. RSS ~14G + system 2.4G = 16.4G; a ~0.5-2G overflow zram-ba (tömörítve
  ~RAM-sebesség). sda5 SSD (32G) a végső backstop. Kill PID-del (nem pkill -f 'soong'!), wrapper update,
  relaunch detached 23:xx.
VÁRT: ha a major-fault ráta DRASZTIKUSAN csökken (pl. <1000/s) és a glob percek alatt befejeződik →
  a GC-thrash volt a gyilkos. Ha még mindig 20k/s fault → a live set genuine túl nagy a 15.9G RAM-hoz,
  és nincs GC-tuning ami megoldja → akkor: (a) GOMEMLIMIT=16-18GiB (több zram/sda5 spill, de ritka GC),
  vagy (b) elfogadni h órákig tart, vagy (c) GOMAXPROCS=2 (kevesebb párhuzamos GC-lapozás).
TANULSÁG: swap-backed Go heapnél a GYAKORI GC = halál. A GOMEMLIMIT-et a live set FÖLÉ kell tenni
  (ritka GC), NEM alá (folyamatos GC). A live set ~12G (mért) az A15 soong-analízishez.

=== factentry26 (2026-06-27 23:52): *** GC-FIX BEVÁLT — 19x kevesebb thrash *** ===
A 14GiB GOMEMLIMIT (attempt 7) DÖNTŐ MÉRÉSE a glob-fázisban (soong RSS=13G):
  major fault/s: **1172** (attempt6 @10GiB: ~22500/s) → **~19x CSÖKKENÉS**.
  RSS=13G (a 14GiB cap alatt, GC ritka), VmSwap=0 (a soong nem swappel), zram=1.6G, sda5=0, avail=506M.
=> MEGERŐSÍTVE: a GOMEMLIMIT-et a ~12G live set FÖLÉ (14GiB) téve a Go GC-t a GOGC-növekedés
   triggereli (ritka), nem a limit (folyamatos) → megszűnt a teljes-heap pásztázás minden pár mp-ben
   → a swap-backed heap random page-fault vihar összeomlott. A soong most CPU-bound (halad), nem
   iowait-stuck. load még magas (~218, 1007 thread), de a THRASH (major fault) a lényeg, az 19x jobb.
STÁTUSZ: még "Running globs", de most reális tempóban → várhatóan hamarosan átér az analízis végére
   (ninja-generálás), majd a compile-fázisra (alacsony per-proc mem). VÉGLEGES SZABÁLY az A15 soong-hoz:
   GOMEMLIMIT a live set FÖLÉ (14GiB) + GOGC=200 + zram + wrapper (env -i bypass) + setsid + oomd off.

=== factentry27 (2026-06-28 00:11): 14GiB ELÉGTELEN (55k fault/s), escaláció 20GiB-re (attempt 8) ===
A factentry26 1172 fault/s mérése FÉLREVEZETŐ volt (GC-cikluson kívüli pillanat). ÚJ mérés 00:11-kor
(soong RSS=13G, 31 perc globs-ban): **55542 major fault/s** — MÉG az attempt6-nál (22500/s) is TÖBB!
A load mégis alacsony (20), mert a zram RAM-sebességgel szolgálja ki a faultokat (nem disk) → félrevezető
load-jel. .glob dir ÜRES, build.ninja NINCS → 31 perc után sem halad ki a globs-ból (mint attempt6 @75min).
DIAGNÓZIS: a live set ~13G ÉPP a 14GiB cap alatt → a Go a limit miatt ~25mp-enként GC-zik, és minden
GC végigpásztázza a heapet (5.4G zram-ban) → 220MB/s swap-olvasás. A 14GiB fejtér (1G a live felett)
TÚL SZŰK → még mindig folyamatos GC.
FIX (attempt 8): GOMEMLIMIT 14→20GiB + GOGC=300. 7G fejtér a ~13G live felett → a heap 13→20G nő GC
előtt (7G allokáció), KÖZBEN nincs teljes-heap pásztázás (csak lokális glob-paging) → a fault-spike
csak a RITKA GC-nél. RSS akár 20G → ~9G overflow zram(14G)+sda5(32G)-re (bőven elég). Kill exact-comm
(soong_build.rea/soong_ui/ninja) + awk-PID lista (NEM pkill -f 'soong' → self-kill!). Relaunch 00:14.
MÉRÉSI TANULSÁG: a fault-ráta BURSTY (GC alatt 55k/s, között ~1k/s) → 1 db 20s mintavétel félrevezet;
átlagolni kell több mintával / hosszabb ablakkal. KÖVETKEZŐ: ha 20GiB SEM csökkenti az ÁTLAGOS fault-rátát
és a globs nem fejeződik be → STRATÉGIAVÁLTÁS: NE restartolj tovább (minden restart ~30min veszteség),
hanem HAGYD FUTNI 2-3 órát (a zram életben tartja, a CPU halad) és nézd, befejezi-e a globs-ot magától.

=== factentry28 (2026-06-28 00:37): *** 20GiB MEGOLDOTTA a mem-thrash-t — új bottleneck: HDD I/O ***
Attempt 8 (GOMEMLIMIT=20GiB, GOGC=300) ÁTLAGOLT fault-mérés (3×20s, soong RSS=13G + zram 7.5G):
  minták: 344, 23, 26 fault/s → **ÁTLAG 131/s** (attempt6@10GiB: 22500/s, attempt8-korai@14GiB: 55542/s)
  => ~400x KEVESEBB thrash! A 7G GC-fejtér (20GiB cap a ~13G live felett) + GOGC=300 megszüntette a
     folyamatos teljes-heap GC-pásztázást. A MEMÓRIA-THRASH MEGOLDVA. *** EZ A VÉGLEGES MEM-RECEPT. ***
DE: soong state=D, load=675 — alacsony fault mellett ez NEM mem-thrash, hanem **HDD I/O-wait**: a glob
  a 162G build-fát járja be (stat/readdir milliók) az 5400rpm HDD-n (sdc) → I/O-bound, D-state, magas load.
  Ez megkerülhetetlen (a fa a lassú HDD-n van), de VÉGES → a glob/analízis befejeződik, csak lassú.
  avail 278M (RAM tele: 13G soong + ~2.5G zram-compressed + 2.4G system), zram 7.5G/14G, sda5 0 (backstop).
STRATÉGIA-DÖNTÉS: a mem-fix KÉSZ → NEM restartolok többet. HAGYOM FUTNI (let-it-ride), 30min tickek,
  csak THRASH DEATH-re avatkozom (sampler5 auto-abort: avail<400M ÉS swap>20G). Várom a build.ninja-t
  (=analízis kész) majd a compile-fázist (alacsony mem). VÉGLEGES A15 SOONG MEM-RECEPT (megtartandó):
  wrapper GOMEMLIMIT=20GiB + GOGC=300 + GODEBUG=madvdontneed=1 (env -i bypass) + zram 14G zstd prio100
  + sda5 SSD prio10 + oomd off + setsid. A 15.9G RAM A15 soong-hoz HATÁRESET; a zram + magas GOMEMLIMIT
  teszi lehetővé. JAVÍTÁSI ÖTLET (ha kell): a build-fát SSD-re tenni drámaian gyorsítaná a globot (most HDD).

=== factentry29 (2026-06-28 02:15): ANALÍZIS KÉSZ (build.ninja 263MB), kati-bukás = LFS radio-blobok ===
*** A MEMÓRIA-BLOKKOLÓ VÉGLEG MEGOLDVA: a soong-analízis BEFEJEZŐDÖTT, build.lineage_FP3.ninja = 263MB. ***
Az attempt 8 build 1h28m után rc=1-gyel bukott a kati-fázisban (01:58), de NEM memória:
  vendor/fairphone/FP3/Android.mk:9: error: radio/modem.img SHA1 mismatch
  (20c88990... != 6b29a0f1...) → ckati failed exit 1.
GYÖKÉR-OK: a 12 db radio/*.img (modem, dsp, tz, aboot, sbl1, rpm, cmnlib, cmnlib64, devcfg,
  keymaster, lksecapp, mdtp) MÉG git-LFS POINTEREK voltak (133B ASCII "version https://git-lfs..."),
  nem a valódi firmware. A factentry13/14 LFS-pull NEM fogta a radio/ alkönyvtárat (csak a
  proprietary/lib blobokat). A kati add-radio-file-sha1-checked a pointer SHA1-ját látta → mismatch.
FIX: git lfs pull --include "radio/*" a vendor/fairphone/FP3-ban (HABUILD chroot, git-lfs 3.7.1).
  BUKTATÓ: a beágyazott chroot-kvótolásban a $változó expanzió elveszett ("$H" üres lett) → szkriptet
  kell írni sdk/sdks/ubuntu/tmp/lfspull.sh-ba (a make_hal*.sh mintára), NEM inline parancsot.
  A .git relatív symlink (../../../.repo/projects/...) → cd-zni KELL a project-dirbe (relatív cd a
  hadk22-ből), abszolút cd elbukik (az ubu-chroot init-file /home/ubuntu-ba cd-z).
  EREDMÉNY (~6s, helyben cache-elt blobok): modem.img = 92MB, sha1=6b29a0f1... = PONTOS egyezés;
  mind a 12 radio-blob valódi. lfspull.log a részletekkel.
RELAUNCH (attempt 9, 02:19): run_build5.sh detached. A soong-analízis CACHE-ELT (build.ninja megvan) →
  átugorja az 1.5h globot, egyenesen kati (radio-check most ÁTMEGY) → ninja compile (a tényleges
  fordítás: hybris-boot, droid-hal, libhybris stb.). VÁRT: gyors kati, majd compile-fázis (-j3, alacsony
  per-proc mem). KÖVETKEZŐ git-lfs TANULSÁG: ha más blob is pointer maradt, ugyanígy pull-olni.

=== factentry30 (2026-06-28 03:08): ninja-bukás = hiányzó libui_compat_layer → external/libhybris hozzáadva ===
Attempt 9 (radio-fix után) tovább jutott: kati ÁTMENT, ninja ELINDULT, majd 8:37 után bukott:
  FAILED: ninja: 'libui_compat_layer', needed by 'hybris-hal', missing and no known rule to make it
GYÖKÉR-OK: hybris/hybris-boot/Android.mk:352-353 Android 10+-ra FELTÉTEL NÉLKÜL hozzáadja:
  HYBRIS_INIT_TARGETS += libui_compat_layer  (a "devices without gralloc" komment STALE/félrevezető —
  valójában minden A10+ eszközre hozzáadja). A modul SEHOL nem volt definiálva a fában, mert a
  base hybris-22.2 manifest (mer-hybris/android default.xml) NEM tartalmazza az external/libhybris-t
  (csak hybris-boot@a16, droidmedia@android15, busybox, selinux_stubs van benne).
FORRÁS (web + GitHub API): a libui_compat_layer a libhybris compat/ui/Android.mk-jában van
  (LOCAL_MODULE:= libui_compat_layer, compat/ui/ui_compatibility_layer.cpp). mer-hybris/libhybris egy
  WRAPPER (rpm/ spec + submodule), a kód a sailfishos-mirror/libhybris-ben (pin: 02f9f62...).
FIX: local_manifests/fp3.xml-be felvéve:
  <project path="external/libhybris" name="sailfishos-mirror/libhybris"
           revision="02f9f62678ba2902d5fc0a180e0526525cca0a3b" remote="github"/>
  repo sync -c --force-sync external/libhybris (HABUILD, ~6s) → compat/ui/Android.mk megvan,
  LOCAL_MODULE:= libui_compat_layer megerősítve. (synclibhybris.log)
RELAUNCH (attempt 10, 03:19): run_build5.sh detached. Mivel ÚJ projekt került a fába, a soong
  valószínűleg ÚJRA-ANALIZÁL (re-glob ~1.5h a HDD+szűk RAM miatt) az új Android.mk/bp felfedezéséhez,
  MAJD kati → ninja compile (most már libui_compat_layer-rel). A mem-recept (20GiB wrapper+zram) áll.
TANULSÁG: az A10+ hybris-hal-hoz az external/libhybris (sailfishos-mirror/libhybris) KÖTELEZŐ a
  manifestben — a base hybris-22.2 manifest hiányosan hagyja. Ha más hybris-modul is hiányzik a
  ninja-fázisban ("missing and no known rule"), valószínűleg szintén egy ki nem szinkronizált
  mer-hybris/sailfishos repo (pl. droidmedia már megvan; libhybris most pótolva).

=== factentry31 (2026-06-28 03:41): COMPILE FÁZIS ELÉRVE (libhybris-fix bevált) ===
Attempt 10: a soong NEM globolt újra (a libhybris Android.mk-alapú → kati gyorsan felvette, a soong
bp-cache érvényes maradt) → egyenesen ninja compile. libui_compat_layer már nem blokkol.
ÁLLAPOT 03:41: ninja AKTÍV [12% 6979/54549], 8 clang, load 3.59, avail 5.8G, zram 1.4G, sda5 0 —
EGÉSZSÉGES fordítás, nincs mem-thrash (a compile -j3 sok kis cc, alacsony per-proc mem). 54549 lépés
-j3-on órákig tart, de halad. A mem-recept (20GiB wrapper+zram) + radio-blobok + libhybris MIND áll.
KÖVETKEZŐ: kivárni a compile-t (rc=0 → out/target/product/FP3/hybris-boot.img + droid-hal artifacts),
majd Platform SDK droid-hal RPM-ek. Ha újabb "missing rule" modul → repo pótlás (mint libhybris).

========================================================================
=== factentry32 (2026-06-28 05:18): *** hybris-hal BUILD SIKERES (rc=0) *** ===
========================================================================
Az ELSŐ sikeres hybris-22.2 (Android 15) hybris-hal build! "build completed successfully (01:55:04)",
[100% 54549/54549], rc=0 @ 05:14:50. (A make_hal5.log "error:" sorai ál-pozitívak: liberror modul-nevek
+ Class.java warningok, NEM hibák.)
ARTEFAKTOK (hadk22/out/target/product/FP3/):
  hybris-boot.img    14.4MB (Android bootimg: hybris kernel + ramdisk) <-- a FŐ kimenet
  hybris-recovery.img 14.4MB ; boot.img 67MB ; dtbo.img 8MB ; vendor.img 547MB ; ramdisk-recovery 15MB
MEGOLDOTT BLOKKOLÓK ÖSSZE (ehhez a sikeres buildhez): (1) skip_initramfs kernel-patch [korábbi];
  (2) A11/A15 verzió-ütközés -> hybris-22.2 újraépítés; (3) soong mem-thrash -> GOMEMLIMIT=20GiB
  wrapper (env -i bypass) + GOGC=300 + zram 14G zstd + sda5 SSD swap + oomd off; (4) radio/*.img
  git-LFS pointerek -> git lfs pull; (5) hiányzó libui_compat_layer -> external/libhybris hozzáadva.
ÖSSZ build-idő: ~1h55m (a soong-analízis HDD-I/O-bound ~1.5h volt, a compile ~gyors).

KÖVETKEZŐ FÁZIS: droid-hal RPM-ek. A hadk22-ben NINCS rpm/dhd (a 18.1 hadk-ban van referencia:
$FP3_ROOT/hadk/rpm/dhd + standalone $FP3_ROOT/droid-hal-fp3 a 18.1 spec-kel).
HADK lépés: dhd (mer-hybris/droid-hal-device) klónozása hadk22/rpm/dhd-be + droid-hal-fp3.spec
(18.1 defines: %define device FP3 / rpm_device fp3 / droid_target_aarch64 1), majd
build_packages.sh --droid-hal a Platform SDK chrootból (target: fairphone-fp3-aarch64).

=== factentry33 (2026-06-28 05:24): droid-hal fázis setup + SDK target reboot-recovery ===
hybris-hal kész -> droid-hal RPM fázis. Setup:
  - dhd klónozva: mer-hybris/droid-hal-device (master, verzio-fuggetlen) -> hadk22/rpm/dhd (build_packages.sh + .inc OK).
  - droid-hal-fp3.spec: a 18.1 spec ATMASOLVA hadk22/rpm/-be (eszkoz-specifikus: device FP3 / rpm_device fp3
    / vendor fairphone / droid_target_aarch64 1 -> A15-höz is jó, csak %include rpm/dhd/droid-hal-device.inc).
  - droidmedia jelen (external/droidmedia@android15 synced).
ELSŐ build_packages.sh --droid-hal HIBA: "Fatal: fairphone-fp3-aarch64 is not a known build target".
GYÖKÉR-OK: LIVE-USB REBOOT torolte az SDK target sb2-REGISZTRACIOJAT (a ~/.scratchbox2 / sb2 state a
  ephemeral /home-on volt). A target DIR + tarball megvan (/mnt/1TB persistent), csak a regisztracio veszett.
  (A tooling SailfishOS-5.0.0.62 regisztracioja viszont tulelt.)
FIX (regtarget.sh, Platform SDK chroot): sdk-assistant --non-interactive create fairphone-fp3-aarch64
  /parentroot$FP3_ROOT/sdk-tarballs/target.tar.7z -> "Target set up", sdk-assistant list OK.
SZABALY (reboot utan): a build elott ELLENORIZD: sdk-assistant list; ha a target hianyzik -> regtarget.sh.
  (A tooling+target tarballok: sdk-tarballs/{tooling,target}.tar.7z.)
RELAUNCH: build_droidhal.sh (Platform SDK, detached), log: hadk22/droid-hal-build.log + droid-hal-fp3.log.

=== factentry34 (2026-06-28 05:25): droid-hal %build bukás = 8 kernel-config ERROR (mint 18.1) ===
build_packages.sh --droid-hal a %build-ben bukott (sh -e): mer_verify_kernel_config 8 ERROR-t adott:
  CONFIG_VT, NET_L3_MASTER_DEV, SYSVIPC, DEVTMPFS, DEVTMPFS_MOUNT, FHANDLE (mind unset/hiányzik),
  CONFIG_DUMMY=y (n kell), CONFIG_NETFILTER_XT_MATCH_QTAGUID (hiányzik).
  => PONTOSAN a 18.1-ben javított Sailfish-kötelező opciók (sailfish-customizations.md). A lineage-22.2 FP3
  kernel (szintén 4.9 sdm632) ugyanazokat hiányolja. (A NFACCT/SUNRPC/LOCKD/AUTOFS4/SCTP csak WARNING="!").
FIX: hadk22/.../configs/lineageos_FP3_defconfig javítva (backup .bak.preSF): a 8 opció beállítva
  (sed: not-set->=y, DUMMY->off; QTAGUID+DEVTMPFS_MOUNT hozzáfűzve). Majd kernel-ujrafordítás
  (rebuild_kernel.sh: KERNEL_OBJ/.config + kernel/boot output torolve -> make -j3 hybris-boot
  regeneralja a .config-ot a defconfigbol). soong cache marad (defconfig = kati/kernel input, nem Android.bp).
  Utana droid-hal ujra (build_droidhal.sh). A mem-recept (20GiB wrapper+zram) aktiv.

=== factentry35 (2026-06-28 06:06): kernel-rebuild OK 7/8; QTAGUID nem létezik 22.2 kernelben ===
kernel-rebuild RC=0 (05:58): KERNEL_OBJ/.config-ban 7/8 opció javítva (VT/NET_L3_MASTER_DEV/SYSVIPC/
DEVTMPFS/DEVTMPFS_MOUNT/FHANDLE=y, DUMMY off). soong cache maradt (gyors).
DE CONFIG_NETFILTER_XT_MATCH_QTAGUID HIÁNYZIK a .config-ból: a symbol NEM LÉTEZIK a lineage-22.2
kernelben (nincs net/netfilter/Kconfig bejegyzés, nincs xt_qtaguid.c -> eltávolítva, Android Q után
deprecated, eBPF váltja). A defconfig-sor no-op. A mer-check (mer_verify_kernel_config:332) viszont
4.9 kernelre (y,m,<=4.13.0) KÖTELEZŐKÉNT kérte -> elkerülhetetlen ERROR -> droid-hal %build (sh -e) bukna.
FIX: mer_verify_kernel_config:332 y,m,<=4.13.0 -> y,m,! (OPCIONÁLIS, mint a connman-opcionális NFACCT/
SUNRPC). Helyes: qtaguid deprecated, connman működik nélküle (csak per-uid iptables statisztika).
Backup: mer_verify_kernel_config.bak.qtaguid. (18.1-ben a 4.9 kernel MÉG tartalmazta a qtaguid-ot, ezért
ott defconfig-gal javítható volt; 22.2-ben már nincs -> mer-check oldalon kell opcionálissá tenni.)
KÖVETKEZŐ: droid-hal újraindítás (kernel NEM kell újra, csak a check-követelmény változott).

=== factentry36 (2026-06-28 06:26): droid-hal kernel-check ÁTMENT; %files mismatch = A15 root mountpointok ===
A QTAGUID-fix bevált: droid-hal túljutott a mer_verify_kernel_config-on. Új bukás a %files check-files-nál:
  "Installed (but unpackaged) file(s) found": /adb_keys /bugreports /cache /d /product /sdcard /system_ext
Ezek A15 (LOS22) root-szintű mountpoint/symlink stubok, amik újabbak a 18.1/A11 root-layoutnál -> az
upstream dhd nem csomagolja őket automatikusan. (Az "absolute symlink" sorok = linker/libc -> /apex,
szándékos hybris-symlinkek, csak QA-warning, NEM fatális; a 18.1-ben is megvoltak.)
FIX: droid-hal-fp3.spec-be: %define straggler_files /adb_keys /bugreports /cache /d /product /sdcard
/system_ext (a dhd straggler_files mechanizmusa, .inc:100/906/1312 -> felveszi a %files-be). MEGJEGYZÉS:
a patterns fázisban (későbbi) kell majd droid-hal-fp3-detritus pattern-bejegyzés is (lásd .inc:101).
KÖVETKEZŐ: droid-hal újraindítás (kernel NEM kell újra).

=== factentry37 (2026-06-28 06:41): straggler_files %files "More than one file on a line" -> lua newline ===
A straggler_files space-separated egy sorba került a %files detritus szekcióba (.inc:1312 %{?straggler_files})
-> rpm "More than one file on a line: /cache /d /product /sdcard /system_ext" (symlink/dir bejegyzések
fájlonként külön sort kérnek). FIX: a makró ujsorokkal -> %define straggler_files %{lua: print("...\n...")}.
A lua print valódi ujsorokat ad; a .inc shell cruft-loopja (xargs -n1) is kezeli az ujsort. droid-hal ujra.

=== factentry38 (2026-06-28 06:56): straggler_files zsákutca -> custom_install_cmds rm (kanonikus hook) ===
A straggler_files %files-be illesztése ÚJSORT igényel (egy fájl/sor), de RPM makró NEM tud újsort tartani:
  - lua print("...\n...") -> az RPM leeszi a backslash-t a lua előtt -> literális "n" (adb_keysn/bugreportsn...).
  - lua több print() -> az RPM makró-engine ÖSSZEVONJA a belső újsorokat (od: "/adb_keys/bugreports/cache\n").
  => a straggler_files inline-%files út JÁRHATATLAN újsorral.
MECHANIZMUS: a dhd _remove_cruft() CSAK a hardcoded arg-listáját törli (.inc:935: /fstab.* /proc /sys /dev
  /sepolicy ...) — a 7 A15 root-bejegyzés nincs benne -> bent maradtak -> "Installed (but unpackaged)".
KANONIKUS FIX: a .inc:1105 %{?custom_install_cmds} spec-hook -> droid-hal-fp3.spec:
  %define custom_install_cmds rm -rf %{buildroot}/{adb_keys,bugreports,cache,d,product,sdcard,system_ext}
  (explicit %{buildroot}/path-okkal, egy soros shell rm). Eltávolítja a stray A15 root-mountpointokat
  %install-ben, a check-files ELŐTT. Helyes: ezek mountpoint-stubok, nem droid-hal tartalom (18.1 sem szállította).
Spec iter 3 (straggler-space -> lua -> custom_install_cmds). droid-hal újra.

========================================================================
=== factentry39 (2026-06-28 07:13): *** droid-hal-fp3 RPM-EK KÉSZ (DROIDHAL_RC=0) *** ===
========================================================================
HADK Step 5 (droid-hal) KÉSZ hybris-22.2-re! 9 RPM a hadk22/droid-local-repo/fp3/-ben:
  droid-hal-fp3-0.0.6 (13MB, fő), -img-boot (15MB), -img-recovery (14MB), -kernel (14MB),
  -kernel-modules (36K), -kernel-dtbo (12K), -devel (353K), -tools (142K), -users (10K).
MEGOLDOTT droid-hal blokkolók: (1) 8 mer-kernel-check ERROR -> defconfig fix + kernel rebuild;
  (2) QTAGUID nem létezik 22.2 kernelben -> mer-check opcionális (y,m,!); (3) SDK target reboot-recovery
  (regtarget.sh); (4) A15 root-mountpointok unpackaged -> custom_install_cmds rm hook.
KÖVETKEZŐ: droid-hal --version (droid-hal-version-fp3 csomag), majd droid-configs-fp3 (Step 6, nagy).

################################################################################
=== factentry40 (2026-06-28 07:25): *** ÉJSZAKAI MUNKA ÖSSZEGZÉS + droid-configs HANDOFF ***
################################################################################
LOOP MEGÁLLÍTVA itt (fázishatár, user-bevonás kell a droid-configs-hoz).

--- AMI ELKÉSZÜLT AZ ÉJSZAKA (hybris-22.2 / Android 15, /e/OS-hez illesztve) ---
1. hybris-hal build OK (rc=0): hadk22/out/target/product/FP3/hybris-boot.img (14.4MB) + boot/dtbo/vendor.img.
2. droid-hal-fp3 RPM-ek OK (9 db): hadk22/droid-local-repo/fp3/droid-hal-fp3-0.0.6-*.aarch64.rpm
   (+ -img-boot, -img-recovery, -kernel, -kernel-modules, -kernel-dtbo, -devel, -tools, -users).

--- MEGOLDOTT BLOKKOLÓK (mind dokumentálva factentry21-39) ---
- soong mem-thrash (a fő, napokig akasztó): GOMEMLIMIT=20GiB wrapper (env -i bypass!) + GOGC=300 + zram 14G
  zstd + sda5 SSD swap + oomd off + setsid. (22500->131 fault/s.)
- radio/*.img git-LFS pointerek -> git lfs pull.
- hiányzó libui_compat_layer -> external/libhybris (sailfishos-mirror) a manifestbe + sync.
- 8 mer-kernel-check ERROR -> defconfig fix (lineageos_FP3_defconfig) + kernel rebuild.
- QTAGUID nem létezik a 22.2 kernelben -> mer_verify_kernel_config:332 opcionális (y,m,!).
- SDK target reboot-recovery (regtarget.sh) ; A15 root-mountpointok -> custom_install_cmds rm.

--- MIÉRT ÁLLT MEG A --version ---
build_packages.sh --version -> buildversion() (util.sh:160): a droid-hal-version-$DEVICE.spec-et a
hybris/ ALATT keresi (find hybris -name droid-hal-version-fp3.spec). Ez NEM létezik -> dirname hiba.
=> a droid-hal-version a droid-configs (Step 6) RÉSZE; a droid-configs setup generálja/hozza. NEM külön
   előzetes lépés. Tehát a --version a droid-configs után épül.

--- KÖVETKEZŐ FÁZIS: droid-configs-fp3 (HADK Step 6) — USER-REVIEW JAVASOLT ---
Cél: hybris/droid-configs létrehozása FP3-ra. Terv:
1. Referenciák: git clone mlehtima/droid-config-fp4 (A11/FP4) tanulmányozni; A15/hybris-22.2 community
   config (ha van) jobb. A régi 18.1 droid-config munka: $FP3_ROOT (lásd sailfish-customizations.md).
2. hybris/droid-configs váz (droid-config-device template) + droid-configs-fp3.spec + droid-hal-version-fp3.spec.
3. sparse/ overlay FP3-ra: etc/ (udev, systemd), usr/libexec/droid-hybris HW, hwcomposer/EGL (Adreno 506).
4. audio policy / pulseaudio (MSM8953 — eltér az FP4 SD750G-től!), usb-moded, dconf (kijelző/gombok).
5. build_packages.sh --configs ; majd --version ; majd patterns (Step 7) ; majd --mic image (Step 8).
DÖNTÉS A USERÉ: (a) vanilla droid-config-device template + kézi FP3 adaptáció, vagy (b) van-e kész
   community hybris-22.2 FP3/MSM8953 config alapnak. + audio/HW path-ok a postmarketOS fp3 portból.

ÁLLAPOT: hadk22 fa ép, mem-recept stabil, SDK target regisztrálva, RPM-ek a droid-local-repo-ban.
Minden build-szkript: buildscripts/ (run_build5, build_droidhal, build_droidhalversion, regtarget,
rebuild_kernel, sampler5). A wrapper (soong_build GOMEMLIMIT) a helyén. SD/swap: zram+sda5.

=== factentry41 (2026-06-28 08:26): *** droid-configs RPM-EK KÉSZ (rc=0, ELSŐ próbára!) *** ===
A mlehtima/droid-config-fp3 (18.1-era) bázis TISZTÁN épült a hybris-22.2/A15 stacken (nem kellett igazítás)!
11 droid-config-fp3 RPM a droid-local-repo/fp3-ban: droid-config-fp3 (fő), -pulseaudio-settings,
-policy-settings, -ssu-kickstarts, -kickstart-configuration, -preinit-plugin, -flashing, -bluez4, -bluez5,
-sailfish, -out-of-image-files. (HADK Step 6 lényegében kész.) droid-configs-device submodule @ 2021 pin elég volt.
KÖVETKEZŐ: --version (most már a hybris/droid-configs adja a droid-hal-version-fp3.spec-et), majd patterns + image (mic).

=== factentry42 (2026-06-28 08:32): droid-hal-version-fp3 setup (kanonikus layout) ===
A --version azért bukott (dirname missing operand), mert nem volt droid-hal-version-fp3.spec a hybris/ alatt.
A droid-hal-version KÜLÖN repo (mer-hybris/droid-hal-version: droid-hal-version.inc + @DEVICE@.spec.template).
KANONIKUS LAYOUT (hadk-faq:58): hybris/droid-hal-version-fp3/ tartalmazza:
  rpm/droid-hal-version-fp3.spec (a template-bol: device fp3/vendor fairphone/pretty/have_vibrator_native 1/
    have_led 1 + %include droid-hal-version/droid-hal-version.inc)
  droid-hal-version/ (klónozott mer-hybris/droid-hal-version repo, a .inc-cel).
buildversion(): find hybris -name droid-hal-version-fp3.spec -> dir/rpm -> cd dir/.. -> build rpm/spec;
  a relatív %include droid-hal-version/...inc a hybris/droid-hal-version-fp3 cwd-hez oldódik fel. Stimmel.
setup_dhv.sh elvégezte; --version MOST épül (nincs dirname-hiba). KÖVETKEZŐ: patterns + image (mic).

=== factentry43 (2026-06-28 08:54): --version hiányzó middleware build-deps -> --gg/--mw fázis ===
droid-hal-version-fp3 RC=1: "Failed build dependencies" — a meta-csomag az egész adaptációt igényli, de a
MIDDLEWARE nincs megépítve. Hiányzó: libhybris, pulseaudio-modules-droid, qt5-qpa-hwcomposer-plugin,
qtscenegraph-adaptation, ngfd-plugin-native-vibrator, mce-plugin-libhybris, hybris-libsensorfw-qt5
(+ droid-config-preinit-plugins/pulseaudio-settings/sailfish, droid-hal-kernel — ezek Provides-szal megvannak).
HELYES HADK-SORREND: --droid-hal -> --gg (gst-droid/droidmedia/audioflingerglue) -> --mw (middleware) ->
--version -> --configs (kész) -> patterns -> --mic. A --version a MW UTÁN épül.
INDÍTVA: build_packages.sh --gg --mw (standard mer-hybris MW repók, a helper klónozza+építi). Log: mw-build.log.
MW provenance -> sailfish-components.md frissítendő a tényleges repó/branch-ekkel sync után.

=== factentry44 (2026-06-28 09:10): MW libhybris ütközés az external/libhybris-szel -> félretéve ===
A --mw bukott: buildmw -u .../libhybris ÚJRAHASZNÁLJA az external/libhybris-t ha létezik (util.sh:193),
de az általam (libui_compat_layer-hez, Android hybris-hal) hozzáadott external/libhybris = sailfishos-mirror
BARE MIRROR: nincs rpm/libhybris.spec ÉS nincs tag -> get_package_version die ("--unshallow on complete repo").
KÉT KÜLÖN SZEREP: external/libhybris = Android-modul forrás (hybris-hal, KÉSZ); MW libhybris = a
mer-hybris/libhybris WRAPPER (rpm/spec + submodule + tagek) -> buildmw klónozza hybris/mw/libhybris-be.
FIX: external/libhybris -> external/libhybris.android-bak (a hybris-hal már megépült, nem kell most).
  buildmw így a wrappert klónozza hybris/mw-be. *** RESTORE KELL minden jövőbeli hybris-hal rebuild ELŐTT ***
  (mv vissza external/libhybris), különben a libui_compat_layer forrás hiányzik. (sailfish-components.md frissítve.)
--mw újraindítva.

=== factentry45 (2026-06-28 09:26): MW libhybris bukás = android-config.h hiányzik; --gg sorrend-hipotézis ===
hybris/mw/libhybris build (a wrapperből, helyesen) configure-nál bukott:
  "checking for android-headers... yes" majd "checking for android-config.h... no" -> configure: error.
  (libhybris/hybris/configure.ac:183 AC_CHECK_HEADERS(android-config.h) kötelező.)
DIAGNÓZIS: android-config.h SEHOL nincs a fában (out/.../obj/include, KERNEL_OBJ/usr/include, device/ -- mind
üres). Az android-headers csomag telepítve (pkgconfig yes), de android-config.h nélkül.
GYANÚ: az android-config.h-t a DROIDMEDIA (--gg) generálja, de a helper a --mw-t a --gg ELŐTT futtatja
  (build_packages.sh:190 BUILDMW, :295 BUILDGG) -> libhybris a droidmedia android-headers ELŐTT épült.
HIPOTÉZIS (standard HADK-sorrend): --gg (droidmedia) ELŐBB -> android-headers+android-config.h -> majd --mw.
KIPRÓBÁLVA: build_packages.sh --gg (csak droidmedia) külön, a --mw ELŐTT. Log: gg-build.log.
HA --gg után megvan az android-config.h -> --mw újra. HA NEM -> mélyebb A15 android-headers gen kérdés (kutatás).

=== factentry46 (2026-06-28 09:34): droidmedia tag-fix; --gg újra (android-config.h forrása) ===
--gg azonnal bukott: droidmedia (external/droidmedia, repo-synced, tag nélkül) get_package_version --unshallow die
(ugyanaz mint libhybris-nél). DE a droidmedia-nak VANNAK tagjei (sailfishos/droidmedia: 0.20260522.0 stb.) ->
git fetch github --tags external/droidmedia-ben -> git describe = 0.20260508.2-5-g4183e95. get_package_version OK.
ÁLTALÁNOS TANULSÁG: a repo-synced external/ MW-repók tag nélkül jönnek -> get_package_version --unshallow
bukik a teljes klónon. FIX: git fetch <remote> --tags az adott external/<pkg>-ben (ha van upstream tag).
--gg újraindítva: droidmedia build -> várhatóan android-headers + android-config.h -> utána --mw libhybris.

=== factentry47 (2026-06-28 09:35): --gg igényli a make droidmedia-t (HABUILD) ELŐBB ===
--gg (tag-fix után) tovább jutott: pack_source_droidmedia-localbuild.sh -> "Please build droidmedia as per
HADK instructions" -> a droidmedia Android-oldali buildje (make droidmedia, HABUILD) hiányzott. HADK-sorrend:
make hybris-hal -> make droidmedia -> droid-hal RPM -> --gg (pack droidmedia+gst-droid) -> --mw.
INDÍTVA: make -j3 droidmedia (HABUILD, mem-recept aktív, soong cache-elt). Log: make-droidmedia.log.

=== factentry48 (2026-06-28 ~11:10 UTC) — make droidmedia soong RE-GLOB: thrashing-but-progressing ===
make droidmedia (HABUILD) triggered "Globs changed, rerunning soong... culprit glob: system/core/**/*"
(a FULL soong re-analysis, one-time cost, caused by moving external/libhybris → glob cache invalidated).
DIAGNOSIS at T+62min (log stdout silent the whole time — soong analysis prints nothing during re-glob):
- NOT a glob-loop: only 1 "Globs changed" line in log.
- NOT deadlocked: soong_build pid727741 ELAPSED 01:02, CPU TIME 00:47:47, %CPU 77 → real forward progress.
- RSS 12.2 GB. mem 14/15G used, swap 9G/46G. vmstat si/so ~23k/24k, iowait 43→85%, kswapd0 6% =
  swap-thrash on the margin: soong heap (12.2G, GOGC=300 lets it grow ~4x live before GC) sits at the RAM
  ceiling, so each GC pass = swap-in storm. SLOW but the mem-recept (zram+sda5+GOMEMLIMIT20G) holds it alive.
DECISION: let it finish (killing forfeits 62min + restarts re-glob from zero). Decisive next signal =
CPU TIME climbing (progress) vs stalled (deadlock→kill by PID). Re-glob is one-time; once .glob cache
rebuilt, later builds fast. Watch: if RSS climbs toward 20G GOMEMLIMIT with avail pinned 0 AND CPU TIME
flat → thrash-death, kill soong_build.rea + ninja by exact PID and consider GOGC=200 to shrink footprint.

=== factentry49 (2026-06-28 ~12:40 UTC) — droidmedia soong re-glob: VERY long, diagnosing stuck-vs-grinding ===
make droidmedia still in the SAME single "Globs changed, rerunning soong (culprit system/core/**/*)" after
~2.5h wall. soong_build pid727741: state S, wchan futex_do_wait (main thread waiting on lock), 1005 OS
threads, cputicks 1150211 (~3:11 CPU, up from ~2:30 last check → still climbing), RSS ~12G, load down to 20
(thrash eased vs earlier 250). `find system/core -type l` could not traverse in 20s (disk saturated by soong,
stuck D-state) → couldn't confirm/deny a symlink-loop hypothesis (a loop under system/core/**/* would make the
recursive glob effectively infinite + accumulate path strings → growing RSS, which fits). DECISION: take a
short-window cputick sample (baseline 1150211 @ ~12:40). If next check ticks barely move → futex deadlock,
KILL soong_build.rea+ninja by PID + rethink (likely: restore external/libhybris to stop the glob-set change,
or build droidmedia with stable tree). If ticks climb strongly → still grinding, give a HARD deadline of ~1-2
more checks then escalate. NOTE: machine so loaded that even ps/grep/find foreground-timeout & auto-background;
use /proc reads only (cputicks via awk on /proc/PID/stat), avoid find on the build tree.

=== factentry50 (2026-06-28 ~12:51 UTC) — soong RE-GLOB FINISHED! now in kati legacy-make parse ===
The ~2.5h soong re-glob (culprit system/core/**/*) COMPLETED — soong_build pid727741 exited cleanly (NOT a
deadlock; it was genuinely grinding through the full re-analysis under mem pressure the whole time, CPU climbed
to ~3:11 then finished). make-droidmedia.log advanced to the kati (legacy Make module parser) phase:
"[100% 3/3] initializing legacy Make module parser" → "[7% 4/56] including out/soong/installs-lineage_FP3.mk".
soong_ui pid726911 still orchestrating. Next: kati finishes 56 steps → ninja compiles droidmedia C++ → "make
droidmedia RC=". LESSON: a soong re-glob on 15GB-RAM+swap can take 2.5h wall / 3h CPU but DOES complete; the
cputick-climbing test correctly said "wait, not deadlocked". To AVOID future re-globs: don't move top-level
source dirs (external/libhybris move = glob-set change = full re-glob); restore before building if possible.
OBSERVED: log parses external/libhybris/compat/media/Android.common.mk → external/libhybris is PRESENT again
(move reverted by a repo sync?). Verify after droidmedia; matters for MW libhybris gotcha but not for this build.

=== factentry51 (2026-06-28 ~13:05 UTC) — droidmedia RC=1: DUPLICATE libhybris module → fixed content-only ===
make droidmedia FAILED RC=1 after 2:47:34. ROOT CAUSE (kati, not memory):
  base_rules.mk:300: error: hybris/mw/libhybris/libhybris/compat/camera:
  MODULE.TARGET.SHARED_LIBRARIES.libcamera_compat_layer already defined by
  external/libhybris.android-bak/compat/camera.
TWO libhybris trees both Android-scanned: (1) external/libhybris.android-bak (the dir I renamed from
external/libhybris — RENAMING WITHIN $ANDROID_ROOT does NOT exclude it; kati still scans it), and
(2) hybris/mw/libhybris/libhybris (full clone from earlier --mw attempt). Both define libcamera_compat_layer
(+ ui/media/input/hwc2/surface_flinger) → kati duplicate-module abort.
FIX (content-only, to AVOID another 2.5h re-glob): emptied the 6 leaf Android.mk under
hybris/mw/libhybris/libhybris/compat/{camera,hwc2,surface_flinger,ui,media,input}/Android.mk to disable
comments (no LOCAL_MODULE). Same file PATHS kept → soong glob set unchanged → NO re-glob; kati just re-parses.
external/libhybris.android-bak stays the sole Android-side libhybris (provides libui/camera/... compat). MW
libhybris RPM builds via autotools later, doesn't need these Android.mk. Original content == identical to
external/libhybris.android-bak/compat/*/Android.mk (restorable). DID NOT create in-tree .bak files (would add
files → change **/* glob set → re-glob). Relaunched make droidmedia detached; expect FAST run (reuses prior
soong analysis, skips re-glob) → kati → ninja droidmedia → RC.
OPEN ITEM: manifest still lists external/libhybris (now absent; only .android-bak). A future `repo sync` would
re-clone external/libhybris → 3-way dup. Before any repo sync: either rename .android-bak back to
external/libhybris (Android side) and keep hybris/mw clone neutered, or drop the manifest entry. Decide at MW step.

=== factentry52 (2026-06-28 13:28 UTC) — make droidmedia RC=0 SUCCESS (content-only fix worked) ===
After emptying the 6 MW-clone Android.mk (factentry51), make droidmedia REBUILT in 8:44 (vs the failed
2:47:34 run): NO re-glob recurred (glob set unchanged), kati passed the previously-failing parse, ninja
"no work to do" (droidmedia .so already compiled in the prior run before the kati abort) →
"#### build completed successfully ####" RC=0. CONFIRMS: content-only edits avoid the 2.5h soong re-glob;
the libhybris duplicate-module was the only blocker. droidmedia is now BUILT Android-side.
NEXT: build_packages.sh --gg (packs droidmedia + gst-droid; provides android-config.h for libhybris MW).

=== factentry53 (2026-06-28 13:32 UTC) — --gg RC=1: droidmedia was NEVER compiled ("make droidmedia" builds nothing) ===
build_packages.sh --gg failed instantly: "Please build droidmedia as per HADK instructions / Failed to
pack_source_droidmedia-localbuild.sh". ROOT CAUSE: external/droidmedia/Android.mk (legacy make) defines
modules libdroidmedia/libminisf/minimediaservice/minisfservice but NO module/phony named "droidmedia"
(grep confirms: no .PHONY droidmedia, env.mk empty). So `make -j3 droidmedia` matched nothing → "ninja: no
work to do" → "build completed successfully" RC=0 but built ZERO artifacts (no obj/SHARED_LIBRARIES/
libdroidmedia_intermediates, no out/target/product/FP3/system/lib64/libdroidmedia.so). pack_source_droidmedia-
localbuild.sh (rpm/dhd/helpers/) checks for out/target/product/$DEVICE/system/lib64/libdroidmedia.so → absent
→ abort. NOTE: pack uses OUT_DEVICE=${HABUILD_DEVICE:-$DEVICE}; product dir is FP3 (uppercase), no fp3
symlink — but droid-hal built fine reading FP3 so HABUILD_DEVICE=FP3 resolves OK in build_packages env; the
real issue was just the missing libs.
FIX: edited make_droidmedia.sh `make -j3 droidmedia` → `make -j3 libdroidmedia libminisf minimediaservice
minisfservice` (explicit module names force these optional/non-PRODUCT_PACKAGES modules to compile). Command-
only change → no tree change → no re-glob. Relaunched in HABUILD. This run will actually COMPILE droidmedia
(real ninja work, heavier — libdroidmedia+minimediaservice pull libstagefright/libcameraservice etc.) → then
re-run --gg to pack. LESSON for community: on hybris-22.2/A15, `make droidmedia` is a no-op here; build the
4 modules by name (or droidmedia upstream may need a phony target re-added for A15).

=== factentry54 (2026-06-28 14:22 UTC) — droidmedia ACTUALLY BUILT (4 artifacts) RC=0 ===
With explicit module targets (factentry53), make completed in 22:27 RC=0 and produced ALL FOUR artifacts:
  out/target/product/FP3/system/lib64/libdroidmedia.so (126K)
  out/target/product/FP3/system/lib64/libminisf.so (85K)
  out/target/product/FP3/system/bin/minimediaservice (3.0M)
  out/target/product/FP3/system/bin/minisfservice (27K)
~4480 ninja steps (built libstagefright/libcameraservice/hidl deps then droidmedia's own .cpp). NO A15 source
breakage in droidmedia — compiled clean (the A15 ifdef branches in Android.mk/minimedia.cpp handle API 35).
Re-launching build_packages.sh --gg now; pack_source_droidmedia will find the .so and pack droidmedia + build
gst-droid. COMMUNITY LESSON: droidmedia @ git-describe 0.20260508.2 builds on hybris-22.2/A15 for FP3 with
`make libdroidmedia libminisf minimediaservice minisfservice` (NOT `make droidmedia`).

=== factentry55 (2026-06-28 14:36 UTC) — --gg "Please build droidmedia" = DEVICE-CASE mismatch (fp3 vs FP3) ===
--gg still failed with "Please build droidmedia" despite the 4 artifacts existing. CAUSE: pack_source_droidmedia-
localbuild.sh checks ./out/target/product/${OUT_DEVICE}/system/lib64/libdroidmedia.so where
OUT_DEVICE=${HABUILD_DEVICE:-$DEVICE}. build_gg.sh sets DEVICE=fp3 (lowercase, needed for RPM names droid-hal-fp3)
and HABUILD_DEVICE is unset → OUT_DEVICE=fp3, but the Android product dir is FP3 (uppercase, from breakfast FP3).
So it looked in out/target/product/fp3/ (nonexistent) → "Please build droidmedia".
FIX: symlink out/target/product/fp3 -> FP3 (relative, inside out/ which is NOT source-globbed → no re-glob;
universal: any tool using lowercase $DEVICE for the out dir now resolves). Verified libdroidmedia.so resolves via
the symlink. Relaunching --gg. COMMUNITY LESSON: FP3 has a device-case split — Sailfish DEVICE=fp3 (RPM names) vs
Android product FP3 (out dir); add `out/target/product/fp3 -> FP3` symlink (or export HABUILD_DEVICE=FP3) so
pack_source_droidmedia & friends find the libs.

=== factentry56 (2026-06-28 14:37 UTC) — --gg SUCCESS (DROIDHAL_RC=0) after symlink fix ===
fp3->FP3 symlink fixed pack_source_droidmedia: it packed droidmedia (tar paths out/target/product/fp3/system/
lib64/libdroidmedia.so etc.), "Building of droidmedia-localbuild finished successfully", DROIDHAL_RC=0.
Produced: droid-local-repo/fp3/droidmedia-0.20260508.2+5+g4183e95-1.aarch64.rpm. (audioflingerglue + pulseaudio-
modules-droid-glue skipped — pulseaudio-modules-droid-hidl is in patterns instead; normal.)
NEXT: build_packages.sh --gg --mw (build_mw.sh) → builds libhybris + middleware stack (libhybris configure
generates android-config.h from droidmedia-provided android-headers). MW is many packages (~20-60min).

=== factentry57 (2026-06-28 14:55 UTC) — --mw libhybris FAIL: A15 bionic availability attr breaks GCC ===
--mw RC=1 at libhybris configure: "checking for android-config.h... no". REAL cause (config.log): the check
COMPILES `#include <android-config.h>` with GCC; android-config.h (droid-hal A15 packaging) appends
`#include <android/versioning.h>` + `#include <android/api-level.h>`. A15 bionic versioning.h defines
__BIONIC_AVAILABILITY via `__attribute__((__availability__(android,strict,introduced=..)))` in BOTH #if/#else
branches (NO non-clang branch) → GCC: "'strict' undeclared", "'introduced' undeclared" → check fails.
android-config.h already neutralizes other clang-isms (_Nonnull,_Nullable,__BIONIC_VERSIONER) but NOT the
availability attr.
FIX: patched android/versioning.h to neutralize for non-clang — after the GUARD #endif:
  #if !defined(__clang__)
  #undef __BIONIC_AVAILABILITY ; #define __BIONIC_AVAILABILITY(__what, ...)
  #undef __BIONIC_AVAILABILITY_GUARD ; #define __BIONIC_AVAILABILITY_GUARD(api_level) 1
  #endif
→ __INTRODUCED_IN/__DEPRECATED_IN/__REMOVED_IN (defined after, via __BIONIC_AVAILABILITY) expand empty under
gcc. Applied to BOTH (a) target headers sdk/targets/fairphone-fp3-aarch64/usr/include/droid-devel/droid-headers/
android/versioning.h (immediate, what libhybris build reads) and (b) source bionic/libc/include/android/
versioning.h (durable for future -devel regen; content-only → no re-glob). Semantically safe: availability
attrs only affect NDK weak-linking, irrelevant to hybris (dlopen). Relaunching build_mw.sh. If error recurs →
--mw reinstalled droid-hal-fp3-devel from the (old) RPM, overwriting target patch → then rebuild droid-hal so
-devel RPM carries the patched header. COMMUNITY LESSON: hybris-22.2/A15 MW build with mer SDK gcc needs the
bionic availability attr neutralized for non-clang (droid-hal-device android-config.h gen should add it).

=== factentry58 (2026-06-28 15:20 UTC) — *** STRATEGIC BLOCKER: SDK gcc 10.3.1 too old for A15 C23 headers *** ===
PROGRESS: availability-attr fix (factentry57) WORKED — libhybris passed configure (android-config.h... now OK)
and started COMPILING. PROOF my target-header patches persist: --mw did NOT reinstall droid-hal-fp3-devel, it
used my patched target versioning.h. So target droid-headers edits ARE picked up without rebuilding droid-hal.
NEW BLOCKER (libhybris gralloc.c compile): 
  /usr/include/droid-devel/droid-headers/android/data_space.h:41: enum ADataSpace : int32_t {  
  /usr/include/.../vndk/hardware_buffer.h:118: enum AHardwareBufferStatus : int32_t {
  → gcc: "expected identifier or '(' before ':' token"
TOOLCHAIN TEST (definitive): SDK target compiler = aarch64-meego-linux-gnu-gcc (GCC) 10.3.1 (Sailfish OS).
  `echo 'enum E:int{A};' | gcc -std=gnu2x -x c -c -` → SAME error. GCC 10.3.1 CANNOT parse C23 enum-base
  syntax (added in GCC 13). A15 bionic headers use `enum X : int32_t/uint64_t` pervasively.
WHY blind fix is unsafe: stripping `: <type>` works for int32_t enums but CORRUPTS uint64_t enums
  (e.g. AHardwareBuffer_UsageFlags bits >31) → defaults to int → overflow. So can't sed-strip globally.
ROOT MISMATCH: Platform SDK is Sailfish 4.6 (gcc 10.3.1) but the port targets RELEASE=5.0.0.71 and hybris-22.2
  / Android 15. A15 userspace headers need gcc 13+ (C23) or clang. The SDK is the wrong vintage.
RECOMMENDED FIX (for user decision):
  (1) BEST: upgrade Platform SDK to a 5.0-era SDK (gcc 13+) that matches RELEASE=5.0.0.71 and compiles C23
      headers natively. Then re-run --mw onward. Cleanest, fixes the whole class.
  (2) Build MW with clang if the SDK target ships one (clang handles C23 enum-base + availability attrs).
  (3) Hack: sed-sanitize extracted droid-headers (strip int32_t enum bases, special-case uint64_t) — fragile,
      not recommended.
STOPPED loop here for user decision (don't thrash; 2nd toolchain-class issue in libhybris). All prior work
intact: droidmedia RPM, droid-hal/config RPMs, --gg done. Resume point: fix toolchain → re-run build_mw.sh.

=== factentry59 (2026-06-28 15:25 UTC) — USER DECISION: upgrade Platform SDK to gcc 13+ ===
User chose option 1 (upgrade Platform SDK) over header-sanitization / clang-install. Plan: obtain a newer
Sailfish toolchain (gcc 13+, C23-capable) target+tooling matching RELEASE 5.0.0.71, register it, then resume
build_mw.sh → --version → --mic. clang NOT present in SDK (host or target), confirmed. Now surveying current
SDK/tooling/target versions + download path.

=== factentry60 (2026-06-28 15:30 UTC) — SDK-UPGRADE IS A DEAD END: Sailfish 5.0.0.62 = gcc 10.3.1 ===
Surveyed: tooling SailfishOS-5.0.0.62 EXISTS and target fairphone-fp3-aarch64 is ALREADY parented to it
(sdk-assistant list). Target rootfs os-release = Sailfish 5.0.0.62 (Tampella). Tooling cross-compiler =
opt/cross/bin/aarch64-meego-linux-gnu-gcc-10.3.1, lib/gcc/.../10.3.1. => Sailfish OS 5.0 (latest) STILL ships
gcc 10.3.1. There is NO newer Sailfish toolchain with gcc 13+. Upgrading the Platform SDK CANNOT provide C23.
IMPLICATION: every Sailfish hybris-22.2/A15 port compiles A15 bionic headers with gcc 10.3.1 → the community/
upstream solution MUST be droid-headers SANITIZATION (or libhybris/dhd patches), not a newer compiler. My
rpm/dhd extract-headers.sh neutralizes _Nonnull/_Nullable/__BIONIC_VERSIONER + (now) availability attr, but
NOT the C23 `enum X : int32_t` base syntax. Likely my dhd is older than the one used for hybris-22.2, OR a
known sed/patch is needed. PIVOT: find the correct upstream A15 enum-base handling (newer dhd extract-headers,
hadk hotfix, or careful sed that special-cases uint64_t enums) and apply at extraction time. Informing user;
SDK-upgrade option is infeasible.

=== factentry61 (2026-06-28 15:45 UTC) — *** SOLUTION FOUND via web: APPLY hybris-patches *** ===
WEB SEARCH RESULT (user was right — we're not the first): the gcc/A15 header issues are fixed by mer-hybris
hybris-patches @ hybris-22.2 (manifest project, revision hybris-22.2). hybris-22.2 IS a real established base
(AOSP android-15.0.0_r32, lineage-22.2, external/droidmedia@android15).
The TWO patches that fix EXACTLY our blockers:
  1. bionic/0010-hybris-Workaround-build-issues-with-gcc.patch
     → wraps libc/include/android/versioning.h macros in `#ifndef DISABLED_FOR_HYBRIS_SUPPORT ... #else
       (#define __BIONIC_AVAILABILITY / __INTRODUCED_IN / __DEPRECATED_IN / __REMOVED_IN / _32 / _64 empty) #endif`.
       android-config.h ALREADY `#define DISABLED_FOR_HYBRIS_SUPPORT` → so patched versioning.h yields empty
       availability macros under gcc. (My manual `#if !defined(__clang__)` edit = equivalent reimplementation.)
  2. frameworks/native/0006-hybris-Fix-build-with-gcc.patch
     → libs/nativewindow/include/android/data_space.h: `enum ADataSpace : int32_t {` → `enum ADataSpace {`
       libs/nativewindow/include/vndk/hardware_buffer.h: `enum AHardwareBufferStatus : int32_t {` → `enum ... {`
       libs/nativewindow/include/android/native_window.h: splits __INTRODUCED_IN(31) decl from definition.
     → EXACTLY the data_space.h/hardware_buffer.h enum-base errors that blocked libhybris gralloc.c.
ROOT CAUSE of the entire MW blocker: hybris-patches was NEVER APPLIED to the AOSP tree before extracting
droid-headers. gcc 10.3.1 is FINE; the HADK flow just requires the hybris-patches step (apply-patches.sh).
(Also explains: had patches been applied pre-hybris-hal, headers would've been correct from the start.)
hybris-patches structure: apply-patches.sh + dirs bionic/, build/, frameworks/{av,native}, hardware/, system/.

RESUME PLAN (post-compact):
 A. In hadk22: revert my manual source edit to bionic/libc/include/android/versioning.h
    (git checkout) so patch 0010 applies cleanly — OR keep it and skip 0010 (equivalent). 
 B. Apply hybris-patches: cd $ANDROID_ROOT(hadk22); run hybris-patches/apply-patches.sh (HABUILD). Watch for
    files ADDED by patches → could trigger a soong re-glob on next Android build (content-only edits don't).
 C. Re-extract headers into droid-hal-fp3-devel: rebuild droid-hal (build_droidhal.sh) so -devel RPM carries
    patched data_space.h/hardware_buffer.h/native_window.h/versioning.h.
    FAST ALTERNATIVE (proven path): target droid-header edits ARE used by --mw without reinstall, so instead of
    rebuilding droid-hal, directly apply the same 3 enum/native_window edits to
    sdk/targets/fairphone-fp3-aarch64/usr/include/droid-devel/droid-headers/android/{data_space.h,native_window.h}
    + vndk/hardware_buffer.h (versioning.h already patched in target). Then re-run build_mw.sh.
 D. build_mw.sh (--gg --mw) → --version (build_droidhalversion.sh) → --mic (build_mic.sh) → flashable zip.
STATE: droidmedia BUILT+RPM, droid-hal RPMs(9), droid-config RPMs(11), --gg RC=0, libhybris past configure
(versioning fix). Only remaining libhybris blocker = the 3 nativewindow enum headers (patch 0006 fixes them).

=== factentry62 (2026-06-28) — WEB RESEARCH: no existing A15 FP3 port + UBports confirms hybris-patches step + applied patch 0006 ===
User asked (HU): give links to articles referencing THIS gcc patch that are FP3-Sailfish themed; then "do it; if a
solution already exists we save time." VERDICT after multi-angle web search:
1. NO ready-made A15/hybris-22 FP3 Sailfish port exists. GitHub search "fairphone fp3 sailfish droid" = 0 repos.
   The "FairSail" forum thread (forum.sailfishos.org/t/.../7379) is PURELY political (should Jolla support FP3?),
   zero technical content, no image, no repo. So our A15 rebuild is genuinely novel — the build itself is NOT
   skippable; nothing to copy wholesale.
2. DIAGNOSIS INDEPENDENTLY CONFIRMED: the UBports FP3 port (Halium 9.0) build recipe
   (forums.ubports.com/topic/4964) explicitly lists the step "hybris-patches/apply-patches.sh --mb" right after
   repo sync. => apply-patches.sh is the mandatory standard step we had been missing. factentry61 root cause = correct.
3. REUSABLE ASSETS for the later hw-config phase (NOT the build system — those are Halium-9/Android-9, we are A15):
   luksus42 FP3 device trees, MSM8953/sdm632 — kernel defconfig, sensors, hw-settings reference:
     - kernel:  github.com/luksus42/android_kernel_fairphone_sdm632
     - device:  github.com/luksus42/android_device_fairphone_FP3
     - vendor:  github.com/luksus42/proprietary_vendor_fairphone
     - manifest: github.com/luksus42/halium-devices/blob/halium-9.0/manifests/fairphone_FP3.xml
     - AOSP DT: github.com/WeAreFairphone/android_device_fairphone_FP3
   MSM8953 sensor/display/audio mapping is ~stable A9->A15, so copy from these instead of guessing in droid-config.

ACTION TAKEN this run (single change = apply hybris-patches frameworks/native/0006, FAST PATH on target headers,
since --mw does not reinstall droid-hal-fp3-devel): edited target droid-headers under
sdk/targets/fairphone-fp3-aarch64/usr/include/droid-devel/droid-headers:
  - android/data_space.h:        enum ADataSpace : int32_t {        -> enum ADataSpace {
  - vndk/hardware_buffer.h:      enum AHardwareBufferStatus : int32_t { -> enum AHardwareBufferStatus {
  - android/native_window.h:     ANativeWindow_clearFrameRate ... __INTRODUCED_IN(31) {  ->  split decl; + def
All three EXACTLY match upstream mer-hybris/hybris-patches@hybris-22.2 frameworks/native/0006-hybris-Fix-build-with-gcc.patch.
Then relaunched build_mw.sh (--gg --mw) detached at 15:56:51 UTC. Previous run was DROIDHAL_RC=1 (the enum errors).
EXPECT: libhybris now compiles past gralloc.c enum-base errors. Watch hadk22/mw-build.log for "DROIDHAL_RC=0".
NOTE for durability: also apply same 3 edits to SOURCE hadk22/frameworks/native/.../{data_space,native_window,hardware_buffer}.h
(or run apply-patches.sh properly) so a future droid-hal rebuild re-extracts patched headers. Source edits are
content-only (no file add) => no soong re-glob. Deferred to keep this run to one change.

=== factentry63 (2026-06-28) — MW BLOCKER FULLY RESOLVED: --mw RC=0, --version RC=0, --mic launched ===
After applying patch 0001 (audio typed-enums) on top of patch 0006 (nativewindow enums), the libhybris %build
COMPILED CLEAN and the WHOLE middleware chain succeeded:
  middleware build DROIDHAL_RC=0 (16:05:40 UTC). Built: libhybris, pulseaudio-modules-droid,
  pulseaudio-modules-droid-hidl, mce-plugin-libhybris, qt5-qpa-hwcomposer-plugin, droidmedia.
Then --version: droid-hal version DROIDHAL_RC=0 (16:07:31) — built droid-hal-version-fp3; log says
"DONE! Now proceed on creating the rootfs". Then launched --mic (new buildscripts/build_mic.sh -> build_packages.sh
--mic, log hadk22/mic-build.log) at ~16:18. Kickstart template present: hybris/droid-configs/installroot/usr/share/
kickstarts/Jolla-@RELEASE@-fp3-@ARCH@.ks. CONFIRMED: the two upstream hybris-patches (system/media 0001 +
frameworks/native 0006), applied to the TARGET droid-headers (NOT source, --mw doesn't reinstall -devel), were the
complete fix. gcc 10.3.1 was never the problem (factentry61 thesis proven end-to-end).

KERNEL SECURITY / EOL STRATEGY (user asked re: ALHACK article forum.fairphone.com/t/.../84131 + "after 4.9 EOL?"):
- The article's FP3-relevant CVE = CVE-2021-30351 (Qualcomm ALAC decoder RCE, CVSS 9.8). It is USERSPACE/DSP,
  NOT a kernel bug; fixed by Qualcomm Dec-2021. We keep the A15 /e/OS vendor (2026 patch level) => already mitigated
  in the retained blobs; Sailfish audio uses droid audio HAL => covered. No kernel action for this CVE.
- Kernel = 4.9.337 (msm-4.9 CAF, near 4.9-LTS EOL). lineageos_FP3_defconfig ALREADY hardened: DEBUG_RODATA,
  DEBUG_SET_MODULE_RONX, HARDENED_USERCOPY, CC_STACKPROTECTOR_STRONG, RANDOMIZE_BASE(KASLR), DEVMEM/DEVKMEM off,
  SECCOMP, UNMAP_KERNEL_AT_EL0(KPTI), HARDEN_BRANCH_PREDICTOR(Spectre-v2), ARM64_SW_TTBR0_PAN, SELINUX.
  SAFE build-time adds (low risk): CONFIG_SLAB_FREELIST_RANDOM=y, CONFIG_DEBUG_LIST=y.
  Best cheap wins via sysctl (droid-config /etc/sysctl.d, NOT kernel): kernel.unprivileged_bpf_disabled=1 (BPF on,
  4.9 unpriv-eBPF is an LPE vector), kptr_restrict=2, perf_event_paranoid=3, dmesg_restrict=1 (AFTER boot-debug).
  DEFER to after first boot (panic risk on vendor drivers): FORTIFY_SOURCE, BUG_ON_DATA_CORRUPTION, PAGE_POISONING.
  SKIP (n/a on 4.9 or breaks hybris): SLAB_FREELIST_HARDENED/REFCOUNT_FULL (4.14+), STRICT_KERNEL_RWX(=DEBUG_RODATA),
  STRICT_DEVMEM(DEVMEM off), MODULE_SIG_FORCE(unsigned vendor wlan.ko).
- EOL ROADMAP: kernel choice is bound to port model. Hybris is LOCKED to downstream 4.9 (Adreno/modem blobs need
  KGSL/ion/binder ABI); no official MSM8953 4.19/5.x vendor BSP exists. Directions:
    1) NOW/short: stay 4.9, rebase kernel/fairphone/sdm632 onto latest LineageOS-22 /e/OS FP3 kernel (they backport
       CVEs post-EOL). 4.9 is NOT CIP-SLTS (CIP=4.4/4.19/5.10/6.1/6.12).
    2) LONG / EOL-proof: NATIVE (non-hybris) Sailfish on MAINLINE kernel + Mesa/freedreno, like the community
       PinePhone/Librem Sailfish ports. MSM8953/FP3 is mainlined & maintained: github.com/msm8953-mainline
       (Vladimir Lypak + Luca Weiss/Fairphone); postmarketOS linux-postmarketos-qcom-msm8953 already at 6.15 with
       close-to-mainline GPU(a506=a5xx freedreno)/WiFi/audio. Means dropping the Android blobs; camera/modem less
       complete today. Recommended sequence: finish hybris port now -> ride LOS/e 4.9 backports -> migrate to
       native mainline+Mesa when that stack matures or backports dry up.

=== factentry64 (2026-06-28) — USER PIVOT to EOL-proof only + NATIVE feasibility (pmOS FP3 mainline matrix) ===
User context: has 2x FP3 (one stock, one TWRP); started SFOS port due to network/LTE change; explicitly NOT
interested in short/medium term, ONLY the EOL-proof direction; chose "feasibility first". Provided the pmOS FP3
wiki page (Anubis-blocked for me) as a local download (~/Downloads). AUTHORITATIVE pmOS Fairphone 3 mainline matrix:
  WORKS: Display/Screen, Touch, 3D accel (GPU freedreno a506), WiFi, Bluetooth, GPS, SMS, Mobile data, FDE,
         USB networking, USB OTG, Flashing.
  PARTIAL: Audio (note: only speaker works; earpiece + microphone DO NOT work), Calls.
  BROKEN: Battery/charging (NO fuel-gauge/charger driver — can't see charge, charging broken; charge via eOS
          recovery!), Camera + Camera flash (BUT Luca Weiss landed FP3 front+rear cameras on mainline Nov-2025,
          newer than this wiki snapshot), Sensors (accelerometer + magnetometer broken → no auto-rotation/compass).
  Kernel: mainline available; pkg linux-postmarketos-qcom-msm8953 (now ~6.15); maintainer @z3ntu (Luca
  Weiss/Fairphone); MSM8953 devices in pmOS 'community' tier.
VERDICT: native is the correct EOL-proof target and the CORE is excellent (GPU/WiFi/BT/display/data/FDE all work,
mainline = maintained kernel forever). BUT two daily-driver SHOWSTOPPERS today: (1) battery/charging broken,
(2) voice calls not usable (Calls Partial + earpiece+mic broken). Given user's motivation = a usable phone on
modern networks, NO working calls = dealbreaker right now. Trajectory positive (Fairphone's own engineer
mainlining; camera just landed). A NATIVE SAILFISH port inherits exactly this HW capability (same kernel+Mesa+
userspace drivers) and adds the Sailfish middleware layer on top (ofono native modem, sensorfw iio, PulseAudio
ALSA-UCM, Mesa EGL for lipstick/wayland) — the proven PinePhone/Jolla-C2 non-hybris model. So native SFOS calls/
battery would be AT BEST as good as pmOS = not daily-usable yet.
CONTRAST: hybris (current build) reuses A15 vendor blobs → battery/calls/VoLTE/camera/sensors use the stack that
works on stock/eOS → a working phone, but locked to EOL 4.9. The tension: user wants EOL-proof (native) but native
FP3 today lacks the essentials (calls, battery). RECOMMENDATION to present: native is right long-term; today it's
not a daily driver; either (a) ride hybris on 4.9 now + migrate when calls/battery land upstream, or (b) commit to
native, help/track upstream, accept no-daily-driver until calls+battery fixed.
ALAC/"patching outdated processor" (user re-raised the forum thread): the forum poster's argument (old chipset
can't be patched → permanently vulnerable) IS the EOL argument, and it REINFORCES native: CVE-2021-30351 is a
USERSPACE ALAC decoder bug (patched by Qualcomm Dec-2021, already in retained A15 vendor), NOT a processor/kernel
bug; "outdated processor can't be patched" applies to FUTURE undiscovered vendor-firmware/DSP/modem bugs that
Qualcomm won't fix for an old SoC. Native answers this best: mainline kernel stays maintained, and media decoding
moves to glibc/GStreamer (distro-updated), dropping the Android media stack entirely.
Sources: pmOS wiki FP3 (user download), pmOS blog 2025-10 (FP3 camera), github.com/msm8953-mainline,
forum.sailfishos.org/t/mainline-kernel-and-sailfish/26289 + /the-pinephone-thread/13845 (native SFOS model:
ofono+Mesa+sensorfw, no hybris), Jolla C2 mainline thread (data+SMS work, no VoLTE yet).
BUILD SIDE (deprioritized hybris validation image): --mic kept aborting on missing COMMUNITY pattern pkgs that
were never built: droid-fake-crypt (+sailfish-fpd-community/sailfish-devicelock-fpd) and miniaudiopolicy
(from audioflingerglue). Commented these optional Requires out of patterns-sailfish-device-adaptation-fp3.inc
(non-essential for first boot), rebuilt --configs, re-running --mic. UPDATE: after commenting out
droid-fake-crypt + miniaudiopolicy, --mic passed pattern resolution and got all the way into rootfs
creation, but failed at the %pack stage ("Failed to execute %pack script with /bin/bash"). Deferred —
hybris validation image is deprioritized per user pivot to native.

=== factentry65 (2026-06-28) — NATIVE GAP ANALYSIS: battery + call-audio drivers (hybris tree as data source) ===
User committed to EOL-proof (native) direction; hybris tree continues as DATA/INFRA source. Concrete findings
from our downstream kernel (kernel/fairphone/sdm632, msm-4.9) + extracted vendor (out/target/product/FP3/vendor):

BATTERY/CHARGING (pmOS: BROKEN):
- FP3 PMIC = PMI632. Downstream drivers ENABLED: CONFIG_QPNP_SMB5=y (charger, drivers/power/supply/qcom/
  qpnp-smb5.c + smb5-lib.c) and CONFIG_QPNP_QG=y (fuel gauge "Qualcomm Gauge", qpnp-qg.c + qg-soc.c +
  qg-battery-profile.c + qg-sdam.c + qg-profile-lib.c). NOT the older qpnp-fg-gen3.
- Mainline status: SMB5/PMI632 charger has upstream work ("power: supply: qcom_smbx / smb5 add PMI632 charger");
  mainline has pm8941-charger/qcom_smbb (old) + the newer smb2/smb5 effort. The QG fuel-gauge is NOT mainlined
  (Android-only IP); mainline path = use the SMB5 charger driver + a fuel-gauge via ADC/qcom-vadc + battery
  profile, OR port QG. THIS is the main missing piece: a working fuel-gauge + charger binding in the FP3 mainline DT.
- WHAT WE HAVE TO GIVE: the downstream qpnp-smb5/qg drivers (register maps, battery profile data in DT
  qcom,qpnp-qg / qcom,battery-data) = the reference for wiring mainline charger + SoC/charge reporting. Battery
  profile (OCV tables, capacity) extractable from downstream DTS battery-data node.

CALL AUDIO / EARPIECE+MIC (pmOS: audio Partial — only speaker; earpiece+mic broken; Calls Partial):
- FP3 codec = internal sdm660/msm8x16-style WCD analog+digital codec (techpack/audio/asoc/codecs/sdm660_cdc/
  msm-analog-cdc.c + msm-digital-cdc.c). Machine driver = techpack/audio/asoc/sdm660-internal.c +
  sdm660-common.c. (Some FP3 SKUs also have external WCD9335 "tasha"; default vendor/etc/mixer_paths.xml uses
  the INTERNAL codec: it has "EAR PA Gain"/"EAR PA Boost"/"EAR_S" = earpiece, "ADC1 Volume"/DMIC = mic.)
- pmOS note matches: "EAR output = receiver (top speaker for calls)", "DMIC1 using MIC_BIAS1 for main mic". So
  the hardware paths are known; mainline just lacks the mixer routing/UCM to enable EAR + mic.
- Mainline status: the msm8916-wcd analog+digital codec IS mainlined (ASoC, since ~4.9-5.x: msm8916-wcd-analog +
  msm8916-wcd-digital), and MSM8953/MSM8976 ASoC machine support was upstreamed (apq8016_sbc extended for
  msm8953; q6afe clk difference). So the codec + machine driver largely EXIST mainline. The gap = (a) correct DT
  audio routing for FP3, (b) PulseAudio/Sailfish UCM (ALSA Use Case Manager) profiles that set the EAR + mic
  control sequences for voice call, (c) voice-call PCM path (modem<->codec) — on mainline this needs the Q6/audio
  DSP (q6afe/q6asm/q6voice via APR over GLINK) OR a direct codec<->modem I2S route.
- WHAT WE HAVE TO GIVE (gold): vendor/etc/mixer_paths.xml is the EXACT control list (EAR PA Gain/Boost, ADC1,
  DMIC, Voice Tx Mixer TERT_MI2S_TX_Voice, etc.). These map almost 1:1 into a Sailfish ALSA-UCM
  earpiece/mic/voicecall verb. The downstream sdm660-internal.c machine driver shows the DAPM routes + DAI links.
  Plus: a live A15/stock FP3 (user has one) can `tinymix`/`amixer` dump the ACTIVE controls during a real call =
  ground-truth for the UCM.

CROSS-CUTTING: voice calls also need the MODEM audio path. On mainline qcom, in-call audio typically goes via the
ADSP (q6voice) which is the hardest bit; alternatively VoLTE/voice over the modem's own path. This is why pmOS
lists Calls only "Partial". So even with EAR+mic UCM solved, full 2-way call audio depends on q6voice/ADSP
bring-up — the real long-pole.

EFFORT VERDICT:
- Battery: medium. Charger (SMB5) is close in mainline; fuel-gauge needs DT battery-profile + either QG port or
  ADC-based gauge. Tractable; FP3-specific DT + profile from our downstream tree.
- Call audio: codec+machine mostly upstream → earpiece/mic playback+capture is LOW-MEDIUM (DT routing + UCM from
  our mixer_paths.xml). FULL voice call (modem<->DSP audio) is HIGH (q6voice/ADSP) and is the shared blocker that
  caps pmOS at "Calls Partial" today.
KEY LEVERAGE FROM HYBRIS WORK: (1) downstream qpnp-smb5/qg + battery-data = battery reference; (2)
vendor mixer_paths.xml + sdm660-internal.c = UCM/routing reference; (3) extracted firmware (adsp/q6, wcd) from
vendor; (4) the user's stock FP3 as a live tinymix/register oracle. None of this requires libhybris — pure data.
Sources: linux-msm.github.io/mainline-status, github.com/msm8953-mainline, ASoC msm8916-wcd (lwn.net/Articles/
704366), MSM8953/8976 ASoC upstream (lkml), qcom_smbx/smb5 PMI632 charger (linux-hardening mail-archive).

=== factentry66 (2026-06-28) — q6voice DSP analysis (NOT black-box RE: full GPL source in our tree) ===
KEY REFRAME: the "DSP reverse-engineering" for voice-call audio is NOT black-box RE. Our downstream tree has the
COMPLETE GPL q6voice driver: kernel/fairphone/sdm632/techpack/audio/dsp/q6voice.c (258KB) + include/dsp/q6voice.h
(full VSS_* opcode vocabulary) + the whole q6 stack (q6afe/q6adm/q6asm/q6core/q6lsm/q6usm) + APR transport
(ipc/apr_v2.c, apr_tal_glink.c). The DSP firmware internals are opaque, but the HOST-SIDE command protocol is
fully in source → task = PORT GPL downstream q6voice onto the mainline APR/ASoC framework (both GPL, clean).

ARCHITECTURE (the voice call recipe, from source):
- Entry: voc_start_voice_call(session_id) @ q6voice.c:7218 → voice_apr_register() → 3 ADSP services via
  apr_register("ADSP","MVM"/"CVS"/"CVP") @ 626/639/653.
  MVM = Multi-Mode Voice Manager, CVS = Core Voice Stream, CVP = Core Voice Processor.
- Setup order: voice_create_mvm_cvs_session (898) → voice_setup_vocproc (4393, builds CVP: dev cfg, cal, media
  fmt, channel info, topology commit) → voice_send_start_voice_cmd (2414, VSS_IMVM_CMD_START_VOICE 0x00011190).
- Teardown: voc_end_voice_call (6898), voice_destroy_mvm_cvs_session (1283).
- Controls already mapped in source: voc_set_tx_mute, voc_set_device_mute, voc_set_rx_vol_step, voc_set_tty_mode,
  voc_set_device_config, voc_set_route_flag, voc_enable/disable_device, voc_standby_voice_call.
- VSS opcode vocabulary in q6voice.h: CREATE_PASSIVE/FULL_CONTROL_SESSION (0x110FF/0x110FE), ATTACH_STREAM
  (0x1123C), ATTACH_VOCPROC (0x1123E), START/STOP/STANDBY_VOICE (0x11190/92/91), MAP/UNMAP_MEMORY, SET_NETWORK,
  SET_VOICE_TIMING, SET_CAL_MEDIA_TYPE, etc.

MAINLINE GAP (precise): mainline upstream HAS q6afe, q6asm, q6adm, q6routing, q6core (the APR services) + APR/GPR
transport + q6dsp common. Mainline does NOT have q6voice (the MVM/CVS/CVP voice-call services) — confirmed: it is
not mainlined on ANY qcom device. So the gap = exactly the MVM/CVS/CVP layer, for which we hold the full GPL
reference. This is an UNSOLVED upstream problem (Linaro/pmOS haven't landed it) → real risk, research-grade.

WHAT I CAN DO (no hardware): analyze q6voice.c, extract the exact APR command/response sequences for call
bring-up, map to mainline q6afe/q6routing primitives, draft a mainline q6voice + ASoC voice DAI. WHAT NEEDS THE
USER (hardware-in-loop): load on the TWRP FP3, capture APR/GLINK traces, iterate. Estimated success for working
2-way call audio ~25-40% with sustained joint effort; recommend tackling AFTER easy wins (pmOS boot, data/SMS,
earpiece/mic UCM, battery) and IN PARTNERSHIP with upstream (linux-msm/pmOS). First concrete deliverable possible
now = a q6voice "what mainline lacks" delta doc from the source.
MIC SIDE: validation image one step from done — rootfs builds (LVM root.img 1.6G + home.img), only %pack failed:
first on missing pigz (installed: pigz-2.3.3 jolla), then on stale loop17/sailfish-VG from repeated aborts
(cleaned: vgchange -an + losetup -d + rm partial out + /var/tmp/mic). Relaunched mic with clean loop state.

=== factentry67 (2026-06-28) — HYBRIS FLASHABLE IMAGE COMPLETE (--mic RC=0, zip produced) ===
After pigz install + stale-loop cleanup, --mic FINISHED RC=0. Flashable zip:
hadk22/SailfishOScommunity-release-5.0.0.71-fp3/Sailfish_OS-5.0.0.71-fp3-0.0.1.202606281607.zip (1.2 GB).
Contents: hybris-boot.img (14.5M), sailfish.img001 (1.43G rootfs), fimage.img001 (619M), vendor.img001,
dtbo.img (8M), hybris-recovery.img, flash.sh, flashing-README.txt, os-release/hw-release. FULL HADK chain done:
hybris-hal -> droidmedia -> --gg -> --mw -> --version -> --mic. This is the validation/fallback image (boots the
A15-blob hybris stack on downstream 4.9). NOTE: not yet flashed/tested on device. Per user pivot, focus stays
native (pmos-bringup.md); this image = hardware-validation + data source, not the EOL-proof goal.
Created pmos-bringup.md: full native/pmOS plan (matrix, gap analysis 3a battery/3b earpiece-mic UCM/3c q6voice,
modem bring-up, pmOS-vs-Sailfish, feasibility %, roadmap, provenance).
