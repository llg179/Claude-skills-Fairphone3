# FP3 pmOS bring-up eszköztár

> Full, English index of every script here: **[INDEX.md](INDEX.md)**.
> Single-use reverse-engineering artifacts now live in `archive/`.

Tipikus parancs-szekvenciák scriptként (ne gépeld újra). Minden `/mnt/1TB`-n.
Forrás-tudás: `../references/archive/pmos-bringup-log.md` és `../references/archive/hw-facts.md`.

| script | mit csinál | mód |
|---|---|---|
| `fp3-env.sh` | közös env (utak, serial, partíciók, helperek) — a többi ezt sourcolja | — |
| `slot.sh get\|set [a\|b]` | A/B retry-count / slot lekérdezés-beállítás | fastboot |
| `boot-watch.sh [from_fastboot\|from_recovery] [s]` | reboot + kimenet (USB-net=bootolt / vissza-fastboot=bukott); logmarkerre vár | bg-ben |
| `flash-pmos.sh [full\|vbmeta\|lk2nd\|rootfs]` | pmOS flash; **full = vbmeta(disable)+lk2nd+rootfs+reboot** | fastboot |
| `twrp.sh flash-b\|flash-a` | TWRP a boot_b-re (ajánlott, őrzi lk2nd-t) vagy boot_a-ra | fastboot |
| `twrp-dd.sh <img> <part> [raw\|sparse]` | image partícióra TWRP-adb-vel (fastboot boot tiltott!) | TWRP |
| `diag.sh` | roncsolásmentes diag: boot_a/b tartalma, pstore, userdata fs, vbmeta | TWRP |
| `sd-fsck.sh phone [mmcblk1p1]\|host /dev/sdX1` | SD debug-log dirty-bit törlés (umount+fsck) | TWRP/host |
| `to-twrp.sh` | **IDLE→TÖLTÉS**: pmOS→bootloader→TWRP(boot_b)+set_active b+reboot; TWRP tölt | pmOS/fastboot |
| `to-pmos.sh` | vissza: set_active a→lk2nd(boot_a)→pmOS | TWRP/fastboot |
| `discharge.sh [cap=65] [burst=25] [battMax=45] [cpuMax=86]` | **GYORS MERÍTÉS** charger-teszthez: pmOS-ben sha256sum minden magon, akku-oldali thermal-guard, TWRP-mérés a célig | bg-ben |
| `charge-test.sh [cycles] [dwell] [abort]` | duty-cycle charger-teszt harness (pmOS-burst → TWRP hő/SoC-mérés) | bg-ben |
| `fg-verify.sh` | **FUEL-GAUGE ellenőrzés**: `pmi632-battery` capacity/voltage/status + UPower SSH-n | pmOS |

### Audio / SLIMbus diagnosztika (lásd `../references/archive/slimbus-audio-context.md`)
Ezek a `scratchpad`-ből kerültek ide — a SLIMbus-framer-fal bemérésének teljes eszközkészlete.

| script | mit csinál | mód |
|---|---|---|
| `dump_lpass_regions.py` | **framer(0xc140000/0x2c000) + LPASS clock-controller(0xc000000/0x14000) teljes `/dev/mem` dump** — auto NGD force-resume (LPASS_AP alias clocked), mindkét régió fájlba + kulcs-regek. UGYANAZ a script UT-n és pmOS-en → kétoldali diff flash/SSR nélkül (folyt.142) | UT **vagy** pmOS root |
| `diff_lpass_regions.py` | a fenti két dump (UT vs pmOS) szó-szintű diffje — azonos config = az a réteg NEM a differenciátor; magányos eltérő STATUS-szó = marker (bizonyítsd causality-vel) | host |
| `frm_causality.py` | **marker-vs-lever teszt:** framer state-biteket (+0x804 bit23, +0x430 bit4) AP /dev/mem-ből ír + FRM_STAT-ot néz — latch-el-e (kar) vagy sem (HW-owned marker). Reverzibilis | pmOS/UT root |
| `framer_mmio_dump.c` | **standalone külső KERNEL-MODUL** (nem full-Image): framer+clock MMIO snapshot debugfs-be, ADSP SUBSYS_BEFORE_SHUTDOWN-nál (SSR-t túléli). `make -C <tree> M=<dir> modules` → hot-load az oracle-re. Instrument-hozzáadás recept, ha az Image-build zsákutca | UT (build+insmod) |
| `regdump_pmos.py` | **NGD(0xc141000) + SLIMbus-BAM v1.7.0(0xc104000) regiszter-dump** `/dev/mem`-en át (P_CTRL/P_EVNT/P_DESC stb.) — eldönti, csatlakozik-e az RX pipe és mozgatja-e a framer a pointert | pmOS root |
| `poll_pipes.py` | **gyors regiszter-tranzíció-sampler** (2ms) egy újra-triggerelt power_up alatt: minden NGD/pipe3/pipe4 változás logolva | pmOS root |
| `poll2.py` | slim-ngd rebind + 8s pipe3-RX/NGD mintavétel 150ms heartbeattel (P_EVNT mozog-e = framer ír-e) | pmOS root |
| `regdump.py` / `rdmem.py` | általános `/dev/mem` szó-olvasó helperek (busybox-nak nincs devmem) | pmOS root |
| `rdtlmm.py` | TLMM GPIO ctl-regiszter dump (SLIMbus pin-mux ellenőrzés: gpio70/71/72 → lpass_slimbus) | pmOS root |
| `fdt_slim.py` | **downstream FDT-parser**: kiszedi a `slim@c140000` node reg/IRQ/props mezőit a stock `boot_a.img`-ből | host |
| `pdr_trace.sh` | dynamic_debug `pdr_interface`+`qcom_pd_mapper`+`slim_qcom_ngd_ctrl` → adsp remoteproc stop/start → dmesg-grep (PDR/servreg a framer-trigger?) | pmOS root |
| `diag-adsp.sh` | ADSP-állapot összegzés: remoteproc state, APR-svc, slimbus-devices, clk_summary (bb_clk1/bi_tcxo) | pmOS |
| `downstream-capture.sh` | working-trace gyűjtő (dmesg slim + clk_summary) a downstream/UT referenciához | UT/downstream |
| `dapm-probe.sh` / `dapm-probe2.sh` | DAPM-widget-állapot + útvonal-probe (mi kapcsol be hívás/earpiece-routingnál) | pmOS |
| `ear-tone{,2,3}.sh` / `hph-test.sh` / `spk-tone.sh` / `voice-test.sh` | hang-útvonal teszt-tónusok (earpiece/HPH/speaker/voice) UCM-cset-tel | pmOS |
| `ucm-look.sh` / `ucm-why.sh` / `fix-ucm.sh` | UCM-import diagnózis + javítás (miért nincs sink) | pmOS |
| `set-vol.sh` / `sink-check.sh` | pipewire/pulse sink + hangerő ellenőrzés/állítás | pmOS |
| `verify-spk.sh` / `verify-spk2.sh` | hangszóró-helyreállítás verifikáció (card0 regisztrál, tiszta tónus) | pmOS |
| `pmos-baseline.sh` / `post-reboot.sh` / `capture-dbg.sh` | reboot utáni baseline-állapot + DBG-dmesg gyűjtés | pmOS |
| `diag-pw.sh` | pipewire/wireplumber gráf-diag | pmOS |
| `build_fg.sh` / `gen_ocv.py` | fuel-gauge OCV-tábla generátor + build (lásd 9.12) | host |
| `voicehold.py` | voice-call PCM nyitva-tartás (hívás-audio útvonal-teszthez) | pmOS |
| `thermprobe.sh` | thermal-zóna probe (akku- vs CPU-oldali szenzor) | pmOS/TWRP |

### ADSP firmware offline RE + framing-START fw-cave család (folyt.135–154)
A framing-START trigger bemérésének eszközei. **Offline RE** (eszköz nélkül, a durable `scratchpad-durable-adsp.mbn`-ből + `adsp-coredump.elf`-ből):

| script | mit csinál | mód |
|---|---|---|
| `coredump_resolve.py` | ADSP VIRTUÁLIS cím (0xf0xxxxxx) → coredump-offszet (VA→PA a statikus mbn phdr-ből → PA→foff a coredump phdr-ből). RUNTIME értékeket ad (heap/BSS). Resting ctx-mezők így cave NÉLKÜL olvashatók (folyt.147) | host |
| `make_disasm_elf.py` | Hexagon-raw blob → objdumpolható ELF32 (`llvm-objdump-21 -d --mcpu=hexagonv60`). Egy VA-ablak disasm-jához | host |

**fw-cave család** (splice→cave→SMEM-stash→sign→SSR-reload pmOS/slot_b; a builder patchel + `qtestsign.py adsp -v 3` signol; az onboard SSR-eli + olvassa + healeli; SMEM-stash AP-oldalról 0x86300000+HDR):

| script | mit csinál | mód |
|---|---|---|
| `build_snapFST1_patch.py` + `smem_snapFST1_read.py` + `fst1_pmos_onboard.sh` | **LIVE framing-START capability-wait TRACE:** splice a wait (0xf0174eb4) UTÁN 0xf04d15bc-nél; elkapja a wait return-értékét + ctx-mezőket. Bizonyította a −2 (TIMEOUT)-ot (folyt.149). Elsőre működött | pmOS root |
| `build_snapFSF1_patch.py` (+FST1 reader/onboard mintára) | **force-success kísérlet:** ctx+0xe54=0 → success-ág; a framer FS marad 0 (gyenge negatív, folyt.150) | pmOS root |
| `build_snapFWT1_patch.py` + `smem_snapFWT1_read.py` | **framer register-WRITE tracer:** hook a HAL write-tail 0xf04bfe80-nál, framer-aperture-re (0xee14xxxx) szűrt ring. ⚠️ **HOT-HAL HOOK → megakasztotta az ADSP SSR-t → reboot** (folyt.152); ne futtasd ebben a formában, ritka/specifikus hook kell | pmOS root (VESZÉLYES) |

**Kulcs-RE-tények (folyt.152, részletek: context §0):** framer register-HAL write=`0xf04bfe54` (`memw(base+table[id])=val`, táblák @0xf0726400); **6 register-csoport** {0x200/0x400/0x600/0x800/0x1000/0x2000}; a `+0x600` frame-enable MÁR byte-azonos → nincs beállítatlan SW-bit. A **block2 (0xc104000)=SLIMbus-BAM/DMA** (=`regdump_pmos.py` „BAM v1.7.0"), a framing DOWNSTREAM-je → nem trigger. UT-oldali MMIO CSAK loadable-modullal (a stock UT /dev/mem korlátozott: MMIO=0x40 fill).

## Kulcs-tények
- `fastboot boot X.img` az FP3 abooton **FAILED ('unknown reason')** → flash+reboot helyette.
- A/B: boot_a=mmcblk0p27, boot_b=mmcblk0p28, userdata=mmcblk0p62. Aktív slot most `a`.
- `set_active` NEM mindig nullázza a retry-count-ot; igazi reset = SIKERES boot (qbootctl).
- pmOS jelszó/SSH: user `fp3` / `$FP3_PW`, USB-net `$FP3_DEV_IP`.
- ✅ MEGOLDVA (2026-06-28): a „Fairphone powered by android → fastboot, lk2nd-képernyő nélkül, pstore üres"
  tünet oka a **hiányzó `dtbo` flash** volt (NEM AVB!). FIX: `fastboot flash dtbo dtbo.img`
  (z3ntu/dtbo-fp3 v1.0) a lk2nd+rootfs ELŐTT. pmOS edge / kernel 7.0.9-msm8953 mainline bootol, phosh fut.
- Boot-watch tanulság: ≥90s ablak kell (a 25s rövid a kernel+phoshhoz; téves BACK_IN_FASTBOOT-ot adott).
- ⚡ TÖLTÉS MEGOLDVA (2026-06-29): saját PMI632-charger driver `qcom_smbx.c`-ben TÖLT pmOS-ben
  (`/sys/class/power_supply/pmi632-charger` status=Charging, ~200mA SDP-ről, akku 37°C). Lásd
  `../references/archive/hw-facts.md` (charger/PMI632 szakasz). Telepítés: kernel-csomag
  `apk add --allow-untrusted` (pmbootstrap `sideload` kulcsos SSH-t vár → manuális scp+apk add kell).
  Régi workaround (ha kell): TWRP-töltés `./to-twrp.sh` ⇄ `./to-pmos.sh`.
- ✅ health=Warm MEGOLDVA (2026-06-29): a spurious `health=Warm` 2 bug volt — (1) SMB5-ön a JEITA temp-status
  nem a STATUS_2 (0x07)-ben van, hanem a STATUS_7 (0x0D)-ben +2 bit-eltolással; a mainline a rossz regisztert
  dekódolta; (2) `switch(stat)` egész-regiszter-egyezést várt. Fix `qcom_smbx.c`-ben (`smb_variant` + bit-teszt).
  Eszközön verifikálva: STATUS_2=0x28 (BIT3 set) mellett is `health=Good`. Regiszter-olvasás:
  `sudo grep -E "^100[7d]:" /sys/kernel/debug/regmap/0-02/registers` (USID 0-02=PMI632). Lásd dosszié §11.
- ✅ WiFi MŰKÖDIK (2026-06-29): scan/assoc/DHCP/internet/DNS OK (`wlan0`, wcn36xx). A blokkoló a boot-idői
  rfkill SOFT-BLOCK volt → `sudo rfkill unblock wifi` (systemd-rfkill megőrzi reboot után). NM-profil
  `HUAWEI-2.4G-V8qK`. Hibakeresés: `4way_handshake→disconnected`+`no-secrets` = ROSSZ PSK (nem driver-hiba).
- ✅ AUDIO (hangszóró) MŰKÖDIK (2026-06-29): user megerősítette a 440Hz teszthangot. ALSA card0 „Fairphone 3"
  (`c051000.sound-card`), UCM `Fairphone_3` HiFi, `aw8898` amp OK. Teszt: `XDG_RUNTIME_DIR=/run/user/$(id -u)`
  + `pactl set-sink-mute ...HiFi__Speaker__sink 0` + `set-sink-volume 70%` + `paplay tone.wav`. Furcsaság:
  valódi PulseAudio 17.0 + PipeWire párhuzamosan (Pulse vitte az ALSA-kártyát). Modem: `mmcli -m 0` =
  `sim-missing` (stack fent, SIM kell).
- 🔋 FUEL-GAUGE MEGOLDVA (2026-06-29): pmOS-ben VAN akku-% (`pmi632-battery` node + UPower → phosh-ikon).
  NEM a downstream qpnp-qg full-port: a QG feszültség-alapú, a mainline `power_supply_batinfo_ocv2cap`
  kész OCV→SoC interpolátor. 56-pontos `ocv-capacity-table-0` a downstream Kayo-profil 25°C oszlopából +
  `vbat`=ADC5_VBAT_SNS csatorna + új `pmi632-battery` (type=BATTERY) psy a `qcom_smbx.c`-ben. Ellenőrzés:
  `./fg-verify.sh`. Korlát: töltés alatt kissé felfelé olvas (megemelt VBAT; IR-drop komp = jövő).
- ⚠️ pmOS→fastboot FLAKY: a `reboot bootloader` néha visszabootol pmOS-be → `to-twrp.sh` most TÖBB PRÓBÁS
  (get_fastboot 4×/90s). TWRP→fastboot (adb) megbízható. Slot-művelet előtt MINDIG `adb get-state` ellenőrzés.
- Charger-port: lásd `../references/archive/hw-facts.md` (charger/PMI632 szakasz) + `charge-test.sh` (duty-cycle harness).
- 🌡️ THERMAL (mért, 2026-06-29, pmOS full 8-mag `sha256sum` terhelés): a CPU-zónák ~76°C-on
  PLATEAU-znak (HW-throttle, A53 junction biztonságos ~95-105°C-ig). A `pmi632-thermal`
  (AKKU-OLDALI szenzor = a valódi tűzkockázat-jelző) VÉGIG **37°C**, meg se rezzen. Ezért a
  `discharge.sh` guardja az AKKU-oldalra megy (abort 45°C), nem a CPU-max-ra → folyamatos terhelés,
  max merítés, nulla akku-kockázat. (Tanulság: `max-of-all-zones` guard hamis-trippel a gyors
  CPU-die szenzoron; az akku-relevens zónát kell figyelni.) pmOS-ben NINCS battery node → a SoC-ot
  csak TWRP olvassa (`/sys/class/power_supply/battery/{capacity,temp,status}`).
- pmOS terhelés-indítás GOTCHA: fire-and-forget `setsid nohup yes &` SSH-n NEM marad életben;
  a megbízható minta a host-oldalon háttérbe rakott, nyitva tartott SSH `'...; wait'`-tel (amíg a
  host-process él, a remote terhelés is). Leállítás: host `kill` + remote `pkill`.

## Installer-mentes OS-váltás (pmOS ↔ dev-enabled UT)
A `$FP3_PMOS/ut-backup-20260630/` tartalmazza a **developer-enabled UT 24.04** teljes
partíció-image-eit (boot_a/dtbo_a/vbmeta_a/vendor_a/system_a/userdata, gz-tömörítve, slot a).
Ezzel **GUI-installer és kézi beavatkozás nélkül** lehet váltani — pl. a working-framer
capture-höz UT kell, a kísérletekhez pmOS:
```bash
cd $(dirname "$0")
# fastbootból:
./swap-to-ut.sh         # UT visszaállítása (TWRP-boot + dd; kezeli a 48G userdata-t)
./swap-to-ut.sh quick   # gyors: csak boot/dtbo/vbmeta/userdata (system+vendor túléli a pmOS-t)
./swap-to-pmos.sh       # vissza pmOS-re (z3ntu dtbo + flash-pmos full = a friss build)
```
A két oldal csak a `userdata`-t írja felül kölcsönösen; `system_a`/`vendor_a` érintetlen marad
egy pmOS-session alatt. Új UT-backup: `ut-backup.sh` (booted UT-ról, adb+sudo).

## Tipikus folyamatok
```bash
cd $(dirname "$0")
./diag.sh                      # TWRP-ből: mi van a boot_a-n, miért nem indul
sudo adb reboot bootloader     # TWRP -> fastboot
./flash-pmos.sh vbmeta         # AVB ki
./flash-pmos.sh lk2nd          # lk2nd a boot-ra (ha kell újra)
./boot-watch.sh from_fastboot 120 &   # reboot+figyelés (run_in_background)
./slot.sh get                  # retry-count ellenőrzés
```
