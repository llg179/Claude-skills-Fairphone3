# FP3 — permanent HW / environment facts

> Migrated from the project's `Opus-fp3-facts.txt` (permanent-facts half). Device data:
> partitions, boot-image params, USB gadget/VID:PID, log channels. Verify each session (names drift).

================================================================================
 Opus-fp3-facts.txt — Sailfish OS / Fairphone 3 boot-debug tényés kísérlet-napló
 Vezeti: Claude (Opus 4.8). Minden bejegyzés: MIT futtattam, MIÉRT, MILYEN KIMENET.
 Legújabb bejegyzések alul. Időbélyeg: session 2026-06-25.
================================================================================

## CÉL (felhasználó kérése, 2026-06-25)
Első körben: az FP3-on álljon fel egy MEGBÍZHATÓ usbnet, amihez PC-ről lehet
kapcsolódni (telnet), és lépésről lépésre futtatni a service-eket — remélve,
hogy usbnettel csatlakozva a konzolon rögtön látszik, mi miért akad el.
Tünet a felhasználótól: "az usbnet kapcsolat akad el", és bár az usbnet felépítés
átkerült a ramdiskbe, az SD kártyára nem kerül log.

================================================================================
## ÁLLANDÓ TÉNYEK (HW / környezet)
================================================================================

### Host (debug PC, Linux live USB)
- adb/fastboot KEZDETBEN NEM volt telepítve → `apt-get install android-tools-adb
  android-tools-fastboot` (adb 1.0.41). Live USB: reboot után újra kell telepíteni.
- Host usbnet modulok jelen: cdc_ncm.ko (USB CDC NCM host driver), cdc_ether.ko,
  rndis_host.ko, usbnet.ko — mind elérhető/betöltve.
  → Linux host CDC-NCM-et OSZTÁLY alapján AUTOMATIKUSAN köt (nem kell new_id).
- Munkakönyvtár: $FP3_ROOT/

### Fairphone 3 USB gadget (configfs) — kernel képességek
Forrás: out/target/product/FP3/obj/KERNEL_OBJ/.config (4.9.218 kernel)
- CONFIG_USB_DWC3=y, CONFIG_USB_DWC3_MSM=y  → DWC3 UDC (7000000.ssusb / .dwc3)
- CONFIG_USB_CONFIGFS=y                     → configfs gadget backend
- CONFIG_USB_CONFIGFS_RNDIS=y / CONFIG_USB_F_RNDIS=y   → RNDIS elérhető
- CONFIG_USB_CONFIGFS_NCM=y   / CONFIG_USB_F_NCM=y     → NCM elérhető (EZT HASZNÁLJUK)
- CONFIG_USB_CONFIGFS_F_MTP=y, F_FS=y (adb/ffs) → MTP/ADB function
- NINCS CONFIG_USB_CONFIGFS_ECM (CDC-ECM nem elérhető; NCM az ECM utódja, jó)
- androidboot.usbconfigfs=true a kernel cmdline-ban (BoardConfig)
  → android_usb sysfs (/sys/class/android_usb/android0) NEM létezik, csak configfs.

### FP3 partíciók / blokk eszközök (Android konvenció)
- A devtmpfs a blokk eszközöket /dev/block/ alá teszi, NEM /dev/ gyökérbe!
  Pl. /dev/block/mmcblk1p1 LÉTEZIK, /dev/mmcblk1p1 NEM. (Ez volt a régi SD-log bug.)
- system_a → /dev/block/mmcblk0p30
- vendor_a → /dev/block/mmcblk0p32
- userdata → /dev/block/bootdevice/by-name/userdata (~52 GB); Sailfish rootfs ide
  flashelve (sailfish.img001 simg2img-gal). LVM: VG "sailfish", LV root+home.
- SD kártya: /dev/block/mmcblk1p1 (vfat). JELENLEG a kártya ÜRES (felhasználó).
- ⚠️ **Node-út a bootolt OS-től FÜGG (folyt.134/182):** a UT-oracle-on a by-partlabel szimlinkek a
  **`/dev/disk/by-partlabel/`**-ben vannak (NEM `/dev/block/bootdevice/by-name/`, ami itt nem is létezik;
  `fdisk` sincs — van `losetup/partx/parted`). Cross-slot recovery-hez a NYERS node kell:
  `/dev/mmcblk0pNN` (NEM `/dev/block/…` — a `losetup -fP /dev/block/…` némán `rc=1`-gyel bukik). A pmOS
  rootfs a **`system_b` = `/dev/mmcblk0p31`**, amire egy TELJES DOS-particionált disk-image van nyersen írva
  (`blkid`: `PTTYPE="dos"`, nincs fs közvetlenül p31-en) → `losetup -fP` → `loopXp1`=pmOS_boot(ext2, /boot),
  **`loopXp2`=pmOS_root(ext4, a valódi rootfs)**; `e2fsck -fy` MINDKETTŐT. A UT writable-overlay (runtime `/etc`)
  = `userdata` = `/dev/mmcblk0p62` → `system-data/etc/…` (a system_a base read-only). Lásd `fp3-kernel-test/references/recovery.md`.

### Boot image paraméterek (device/fairphone/FP3/BoardConfig.mk)
- BOARD_KERNEL_BASE        := 0x80000000
- BOARD_KERNEL_PAGESIZE    := 2048
- BOARD_KERNEL_TAGS_OFFSET := 0x00000100
- BOARD_RAMDISK_OFFSET     := 0x01000000
- BOARD_BOOT_HEADER_VERSION := 1
- cmdline: androidboot.hardware=qcom msm_rtb.filter=0x237 ehci-hcd.park=3
  lpm_levels.sleep_disabled=1 androidboot.bootdevice=7824900.sdhci
  androidboot.usbconfigfs=true loop.max_part=7
- mkbootimg/unpack_bootimg: hadk/system/tools/mkbootimg/{mkbootimg.py,unpack_bootimg.py}

================================================================================
## USB ENUMERÁCIÓ — megfigyelt VID:PID szekvencia (PC dmesg)
================================================================================
Egy boot-ciklus alatt a PC ezt látja a 1-5 porton:
1. 18d1:d00d  "Google / Android"      — ramdisk + bootloader/init-debug fázis
2. 22b8:2e81  "Fairphone / FP3"        — usb-moded átmeneti mód
3. 22b8:2e76  "Fairphone / FP3"        — usb-moded fejlesztői/RNDIS mód
   majd disconnect → reboot → ismétlés (crash loop).

### FONTOS FELISMERÉS (2026-06-25):
A JELENLEG enumerált 22b8:2e76 NEM a Sailfish RNDIS, hanem a TWRP!
  lsusb -v: iConfiguration="mtp_adb", 2 interfész:
    if0: class ff/ff/00 iInterface="MTP"
    if1: class ff/42/01 iInterface="ADB Interface"
  → Ez TWRP MTP+ADB. adb devices: "$FP3_SERIAL  recovery" (TWRP fut).
A korábbi 22b8:2e76 "RNDIS"-nek hitt eszköz is gyanús: a Linux rndis_host soha
nem kötötte (interfész osztály nem e0/01/03 volt), ezért usbnet sosem épült fel.
→ EZÉRT VÁLTUNK NCM-RE: a host cdc_ncm class alapján magától köti.

================================================================================
