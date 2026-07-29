# FP3 — DATA-INDEX (kereshető kulcsszavakkal)

> **Note:** paths under `report-attachments/` are kept locally and are not part of
> this repository (personal outreach drafts and raw device captures). The entries
> below are retained as a record of what was collected.
# Cél: gyorsan felismerni, hogy egy témát MÁR megvizsgáltunk-e, és MELYIK fájlban van.
# Használat: keress rá a témádra (pl. "bb_clk1", "proxy", "QMI", "PLL", "mem_setup") — a
# találat sora megmondja, hol nézd meg, mielőtt újra futtatnád.
#
# HELY: ez a fájl (és a legtöbb alább listázott adat-pack) a `fp3-porting-debug/references/`
# alatt van (co-located). A NEM migrált fájlok a projektben (`$FP3_ROOT/`):
# a napló (`FP3-slim-debug-journal.md`), a dátumozott eredmény-/task-logok, a `scripts/`,
# és a kernel-fák (`$FP3_PMOS/…`).
#
# ┌─ OLVASÁSI SORREND ÚJ SESSIONBEN ─────────────────────────────────────────────┐
# │ 0. FP3-2026-Jul-13-startup-instructions.md  (SESSION-INDÍTÓ: cél+skillek+next;   │
# │    a PROJEKTBEN: $FP3_ROOT/) ← EZT ELŐSZÖR ÚJRAINDÍTÁS UTÁN             │
# │ 1. fp3-pmaports/docs/  (AKTUÁLIS ÁLLAPOT: docs/kernel = kié melyik kód,           │
# │    docs/<alrendszer>/bringup = hogyan jött össze)  ← EZ A MÉRVADÓ                 │
# │ 2. slimbus-audio-red-herrings.md  (mit zártunk ki és miért; references/)          │
# │ 3. FP3-tierA-results-2026-Jul-10.md  (F1-UT + Tier A; a PROJEKTBEN maradt)        │
# │ 4. fp3-porting-debug + fp3-kernel-test SKILLEK (módszer, guardrailek)              │
# └───────────────────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════
  ★ AKTUÁLIS / MÉRVADÓ (ezeket használd)
═══════════════════════════════════════════════════════════════════════════════

AUDIO (SLIMbus/WCD9335) → A MÉRVADÓ HELY A DOKUMENTÁCIÓ, NEM EZ A SKILL:
  github.com/llg179/fp3-pmaports/tree/main/docs/audio          (hogyan működik ma)
  github.com/llg179/fp3-pmaports/tree/main/docs/audio/bringup  (hogyan jött össze)
  Itt maradt: slimbus-audio-red-herrings.md (vakvágány-katalógus — nem évül el).
  A dátumozott nyomozási naplók: references/archive/ (lásd archive/README.md);
  a komponens-címtérkép: archive/slimbus-audio-context.md §7.

FP3-tierA-results-2026-Jul-10.md
  Tier A + F0 + F1 + F10/F11 + firmware-disasm-analízis részletes eredményei. Kulcs:
  F1-UT, F6 fw-byte-azonos, HWL leaf-trace, HalHwIo, PLL-lock, bb_clk1, SCM-ftrace.

FP3-tasks-v2-2026-Jul-10.md
  MÉRVADÓ task-lista (red-teamelt). Kulcs: T1-T7, marker 0x2c OPEN, Delta A halott,
  next-lépések. Felülírja a régi task-fájlokat.

FP3-guardrails.md
  VÉGREHAJTÁSI (mérés-integritási) tiltólista. Kulcs: soft-vs-hard evidence,
  confirmation-theater, static-vs-live, one-sided-diff, marker-vs-lever. (Device
  brick-safety KÜLÖN, a skillben.)

FP3-slim-debug-journal.md
  TELJES NAPLÓ (448 KB, folyt.1-103). Minden hipotézis→teszt→verdikt kronológiában.
  Ide grepelj, ha "megvizsgáltuk-e már X-et" a kérdés. Kulcs: MINDEN.

fp3-skill-feedback-log.md  (a skill hozza létre create-if-absent módon a sablonból)
  SKILL-FEEDBACK LOG. Átvihető módszertani tanulságok (safety-osztály, mérés-integritási
  csapda, jobb recept, skill-korrekció) — a fp3-porting-debug / fp3-kernel-test skillek és a
  references/ fájlok KÖVETKEZŐ szerkesztésének nyersanyaga. NEM a nyomozási napló. NEW/PROMOTED/DROPPED.
  Sablon: fp3-porting-debug/references/skill-feedback-log.template.md (a napló sablonja: journal.template.md).

hw-facts.md   (references/archive/ — az Opus-fp3-facts.txt ÁLLANDÓ-TÉNYEK fele)
  PERMANENS HW-TÉNYEK. Kulcs: USB-gadget ID-k, partíciós térkép (mmcblk0p*), boot-header
  verziók, boot-image paraméterek, VID:PID szekvenciák.
archive/boot-debug-log.md   (ARCHÍVUM — dátumozott napló, nem módszer)
  BOOT/RAMDISK BRING-UP NAPLÓ + architektúra-jegyzetek (kronológia). Kulcs: pstore/SD/eMMC
  log-csatornák, A/B retry, skip_initramfs, NCM ramdisk, KOMPONENSEK.

═══════════════════════════════════════════════════════════════════════════════
  FIRMWARE RE / DISASSEMBLY (ADSP adsp.mbn, Hexagon/QDSP6)
═══════════════════════════════════════════════════════════════════════════════

report-attachments/adsp-firmware-framer-strings.txt
  ADSP fw ULOG string-ek. Kulcs: "Switching driver mode (master: %d)", framer-mód
  döntés, device.cfg/ACDB, ADSP.VT.3.0-00161 build 2020-05-18, ELF32 nem-titkosított.

report-attachments/adsp-framer-decision-disasm.txt
  Framer-MÓD döntés disasm. Kulcs: immext constant-extender xref, ctx+0x74
  satellite_hw_owner, ctx+0x78 framer_mode, ph4 0xf015f000.

report-attachments/adsp-slimbus-clock-disasm.txt
  SLIMbus ref-clock enable path disasm. Kulcs: LPASS core clock, clock_manager,
  afe_lpass_core_clk, ctx-struct, HalHwIo.

ai-rebuttal-afe-framer.md
  Cáfolat egy AI-hipotézisre. Kulcs: AFE clock/APR vektor a framer előtt = NINCS a
  downstreamben (megcáfolva), msm-dai-slim, boot-timing. (AFE-pre-framer = HALOTT.)

MORNING-HANDOFF-m9.md
  m9 LPASS-core-clock lelet. Kulcs: f0617928 clock_manager.cpp, AFEDeviceDriver
  boot-init, afe_lpass_core_clk, DAL-proxy-creation bukás. (folyt.46 vonal.)

═══════════════════════════════════════════════════════════════════════════════
  TRACE-EK / REGISZTER-DUMPOK / GOLDEN CAPTURE
═══════════════════════════════════════════════════════════════════════════════

pil_bringup.txt
  UT PIL ADSP bring-up ftrace (scm/rpm_smd/clock). Kulcs: rpm_smd_send, clk2,
  MARK-UNBIND, subsys-pil-tz. (folyt.100 capture.)

boot_trace.txt
  Boot-time ftrace (scm_call_start/end). Kulcs: func id 0x42000404, PAS SCM funcId-k.

report-attachments/downstream-golden-ipc-trace.txt
  GOLDEN: működő UT framer bring-up ipc_logging. Kulcs: SELECT_INSTANCE + POWER_REQ
  SvcId 0x301, NINCS CHECK_FRAMER, ~2ms után master capability.

report-attachments/pmos-slim-ctx-devmem.txt
  pmOS (FAILING) /dev/mem dump. Kulcs: NGD_STATUS=0x40c, NGD_CFG=0x0, INT_STAT=0x0.

report-attachments/ut-slim-ctx-devmem.txt
  UT (WORKING) /dev/mem dump. Kulcs: uniform 0x70 (idle clock-gated blokk = tooling
  artifact, NEM valós 0), framer verified working.

report-attachments/pmos-dmesg-full.txt
  Teljes pmOS boot dmesg (2026-07-02). Kulcs: qcom-ngd-ctrl DBG, bb_clk1 force,
  capability timeout, teljes bring-up.

scratchpad/ut-enabled-clocks.txt
  UT enabled_clocks debugfs snapshot. Kulcs: xo_clk_src, bimc, pcnoc, snoc, qdss.

═══════════════════════════════════════════════════════════════════════════════
  PIL vs PAS BOOT-ÖSSZEHASONLÍTÁS (source-diff)
═══════════════════════════════════════════════════════════════════════════════

pas-launch-diff.md  (+ azonos: report-attachments/pas-launch-diff.txt)
  PAS(mainline,FAIL) vs PIL(downstream,WORK) source-diff. Kulcs: qcom_q6v5_pas.c,
  msm8996_adsp_resource, pas-id=1, carveout 0x8d600000, mdt_loader, Delta A
  (feltételes MEM_SETUP — később HALOTT: mbn relocatable).

report-attachments/pil-tz-vs-pas-boot-comparison.md
  subsys-pil-tz vs qcom_q6v5_pas lépésről-lépésre. Kulcs: TZ PAS SCM, proxy-reg
  vdd_cx TURBO, crypto clocks, azonos carveout, "funkcionálisan ekvivalens".

═══════════════════════════════════════════════════════════════════════════════
  KÜLSŐ KOMMUNIKÁCIÓ (GitHub #255 / fórum / Fairphone support / Matrix)
═══════════════════════════════════════════════════════════════════════════════

fairphone-slimbus-framer-report.md
  A fő publikus report (framer-never-comes-up). Kulcs: SDM632, összefoglaló ask.

report-attachments/issue-comment-firmware-analysis.md   fw-disasm komment #255
report-attachments/issue-comment-register-level.md      v1: framer HW nem fut PAS-on
report-attachments/issue-comment-register-level-v2.md   v2: ground-truth ADSP-belülről
report-attachments/issue-comment-register-level-v3.md   v3: root-clock force fires, mégsem indul
report-attachments/issue-comment-register-level-v4.md   v4: rc=0 false-success, teljes cím-térkép
report-attachments/issue-comment-runtime-tests.md       6 runtime datapoint, APR/AVS működik
report-attachments/issue-comment-draft.md               raw evidence attach lista
report-attachments/github-reply-to-z3ntu.md             z3ntu válasz: DT-plumbing egyezik
report-attachments/github-reply-to-z3ntu-2.md           Bjorn 1075549 series tesztelve: no change
report-attachments/fairphone-forum-post-draft.md        fórum draft v1
report-attachments/fairphone-forum-post-draft-v2.md     fórum draft v2 (LPASS core-clock)
report-attachments/forum-reply-to-yvmuell.md            fórum válasz (ticket #1453513)
report-attachments/fairphone-support-ticket.md          FP support ticket szöveg
report-attachments/fairphone-support-followup-1.md      support follow-up (Noah)
report-attachments/pmos-matrix-message.md               pmOS Matrix üzenet
report-attachments/slimbus-false-success-consolidation.md  "false success" konszolidált konklúzió
report-attachments/issue-comment-draft.md               (ld. fent)

═══════════════════════════════════════════════════════════════════════════════
  PORTOLÁS (nem-audio) — charger, audio-DT, Sailfish/hybris build
═══════════════════════════════════════════════════════════════════════════════

charger-port/CHARGER-PORT-PMI632.md
  PMI632 töltés mainline-port. Kulcs: qcom_smbx.c, SMB5, fuel-gauge, Li-ion safety.

charger-port/UPSTREAMING.md
  Charger patch beküldés. Kulcs: DCO, Signed-off-by, git identitás.

audio-port/README.md
  pmOS earpiece/in-call audio port TERV. Kulcs: aw8898 MI2S, PM8953 WCD, DT dai-links,
  mixer_paths.xml, EAR_S/RX1/DEC1. (Kezdeti — később kiderült: WCD9335 SLIMbus a jó.)

audio-port/wcd9335-slimbus-bringup.md
  WCD9326 SLIMbus DT draft. Kulcs: slim-ngd, tasha_ifd, tlmm67/73/74, msm8996.dtsi ref.

sailfish-components.md
  Sailfish hybris port komponens-eredet. Kulcs: hybris-22.2, /e/OS A15, provenance,
  soong/RAM build-recept.

sailfish-akcioterv.md
  Sailfish FP3 port akcióterv (HADK). Kulcs: droid-config-fp4 ref, MSM8953, hybris.

sailfish-customizations.md
  Sailfish build customizations. Kulcs: hybris-boot init, SD-log, ramdisk, fail().

pmos-bringup.md
  pmOS mainline bring-up (88 KB). Kulcs: feature-matrix, §9.x execution log, charger,
  fuel-gauge, modem, a SLIMbus fal. Display/GPU/WiFi/modem OK.

scripts/README.md
  Eszköztár. Kulcs: fp3-env.sh, slot.sh, boot-watch.sh, flash-pmos.sh, test-slim-kernel.sh,
  qrtr_lookup.py, regdump_pmos.py, adsp-smem-log.py.

kcomp/lvm-config.txt / kcomp/twrp-config.txt
  Kernel .config fragmentek (configfs/gadget/RNDIS). Kulcs: USB_CONFIGFS, IKCONFIG.

═══════════════════════════════════════════════════════════════════════════════
  ☠️ ELAVULT — NE használd kiindulásnak (csak történeti referencia)
═══════════════════════════════════════════════════════════════════════════════

FP3-slim-STATUS.md                     (2026-07-07 folyt.17; superseded a context+tracker által)
FP3-slim-session-handoff-2026-07-04.md      (ELAVULT; Option-2 ADSP-fw instrumentálás terv)
FP3-slim-session-handoff-2026-07-04#2.md    (ELAVULT; M2 code-injection + wedge-recovery)
FP3-tasks-2026-Jul-10.md               (superseded: FP3-tasks-v2; §0.2 N-létra elavult)
FP3-tasks-v2-DRAFT-2026-Jul-10.md      (SUPERSEDED a v2-FINAL által; premisszák megcáfolva)
FP3-tasks-2026-Jul-10-executed-log#1.md     (folyt.91 végrehajtási napló + red-team kritika)
FP3-run-log-Jul-10.md                  (folyt.91 session-napló; a journal a tömör verzió)
FP3-redteam-prompt.md                  (red-team session-indító sablon)
last.txt                               (csak egy claude --resume parancs)

═══════════════════════════════════════════════════════════════════════════════
  ★ GYORS "MÁR KIZÁRT" EMLÉKEZTETŐ (hol a bizonyíték)
═══════════════════════════════════════════════════════════════════════════════
  firmware NEM a hiba .............. folyt.99 (fw-swap) → runtime-trigger-progress
  AP proxy-erőforrások ekviv. ..... folyt.101/102 → runtime-trigger-progress
  AP proxy-POWER (cx@max hold) .... folyt.103 ÉLŐ kísérlet → runtime-trigger-progress
  QMI 301 = downstream ............ downstream-golden-ipc-trace + prior driver-note
  NGD-setup / NGD_CFG = downstream  folyt.103 addendum
  QDSP6SS NEM AP-felület .......... folyt.102 (msm8953 = pure TZ-PAS)
  bb_clk1 force-enable ............ red herring (journal 17/928)
  Delta A (feltételes MEM_SETUP) .. HALOTT (mbn relocatable) → tasks-v2 §0
  0x2c marker (QDSP6SS 0x10b) ..... ADSP-írt OUTPUT, nem AP-kar (E1c pre=0)
  Bjorn 1075549 NGD-race series ... tesztelve, no change → github-reply-to-z3ntu-2
  AFE-pre-framer clock vektor ..... megcáfolva → ai-rebuttal-afe-framer
  MEM_SETUP tüzel mainline-on ..... élő ftrace igazolva → tierA-results
  wcd-mclk force-ON .............. no-op (folyt.145; codec-enum a framer-CLK-t kéri, nem MCLK)
  framing-START = 0xf04d14cc ...... LIVE wait-return −2 TIMEOUT igazolva (folyt.149 FST1 cave)
  force-success (ctx+0xe54=0) ..... NEM keretel, FS marad 0 (folyt.150 FSF1; gyenge negatív)
  framer frame-enable (+0x600) .... byte-azonos both-sides → nincs beállítatlan SW-bit (folyt.152)
  block2/SLIMbus-BAM (0xc104000) .. data-plane/DMA, framing-DOWNSTREAM → nem trigger (folyt.153-154)
  FWT1 write-tracer (hot-HAL) ..... megakasztja az ADSP SSR-t → reboot; ne futtasd (folyt.152)
