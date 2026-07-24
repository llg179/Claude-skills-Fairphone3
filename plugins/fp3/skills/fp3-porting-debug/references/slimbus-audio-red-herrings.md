# FP3 audio (SLIMbus) — VAKVÁGÁNYOK / red herrings (archívum)

> Ez a fájl a `slimbus-audio-context.md`-ból kivett történeti/kizárt tartalom.
> Célja az ISMÉTLŐDÉS-ŐR: mielőtt bármit újra megnéznél, keresd ki innen — sok lead már
> lezárva, a bizonyíték helyével (folyt.X) együtt. A folyt.X hivatkozások a naplókra mutatnak:
> `FP3-slim-debug-journal.md` (teljes napló) + `slimbus-audio-tracker.md` (élő tracker) + `data-index.md`.
>
> **★★★★★ MEGOLDVA (folyt.196, 2026-07-23): a lenti „konszolidált verdikt" (a fal FIZIKAI/ADSP-belső/PLL)
> TÉVES VOLT — SUPERSEDED.** A tényleges gyökér: **QDSP6SS `0x0c20002c` bit3**, amit a mainline PAS set-ben
> hagy (downstream PIL törli). Törölve a framer felframel. Az AP-oldal exoneráció + a byte-azonos mérések
> IGAZAK maradnak, de a belőlük levont „boot-env-függő fizikai fal" konklúzió hibás volt: a különbség EGY
> AP-írható regiszter-bit, amit a load-út (PIL vs PAS) állít. Lásd `slimbus-audio-context.md` első ★★★★★ szakaszát.
> A lenti kizárt-leadek listája (mint ismétlés-őr) továbbra is érvényes és hasznos.
>
> **[TÖRTÉNELMI verdikt, SUPERSEDED] A konszolidált verdikt (miért holt MIND): azonos fw + azonos TZ + azonos AP-környezet → a framer
> PIL alatt framel, PAS alatt halott. Az AP-oldal teljesen exonerálva. A fal FIZIKAI, ADSP-belső,
> boot-env-függő (PIL vs PAS): a framer-branch óra-enable byte-azonos working↔dead, mégsem jár a dead
> oldalon → a parent RCG-root / source LPASS-audio-PLL nem táplál PAS alatt.**

---

## 1. KIZÁRT LEADEK (ne futtasd újra — bizonyíték helye)

| téma | verdikt | bizonyíték (hol) |
|---|---|---|
| **firmware** | NEM a különbség (döntő swap: pmOS fw UT/PIL-en FRAMEL) | folyt.99 → tracker |
| **AP proxy-erőforrások** | ekvivalens (xo, cx, crypto) — valódi downstream forrásból | folyt.101/102 → tracker |
| **AP proxy-POWER** | ÉLŐ kísérlettel kizárva (cx@INT_MAX+xo VÉGIG tartva → framer halott) | folyt.103 → tracker |
| **QMI 301 forgalom** | = downstream (SELECT_INSTANCE MASTER + POWER_REQ, ack-olt) | folyt.103 + golden-ipc |
| **QMI-payload / SELECT_INSTANCE „3. TLV"** | HOLT LEAD — a „21B" = 7B QMI-hdr + 14B TLV, a TLV byte-azonos a mainline-nal; a QMI-tartalom EXONERÁLVA, „not the lever" | journal:134-136 + folyt.58c |
| **ACDB-mint-framer-trigger (path A)** | HOLT LEAD (arany-trace timing) — részletek: §3 | journal:44-63 + folyt.58c/127 |
| **NGD setup / NGD_CFG** | = downstream (ENABLE\|RX\|TX write megvan; CFG=0 = tünet) | folyt.103 addendum |
| **QDSP6SS AP-poke** | nem AP-felület msm8953-on (ADSP = pure TZ-PAS) | folyt.102 |
| **AP RPM-vote / bb_clk1** | kizárva (bb_clk1 force = red herring; nincs AP-látható LPASS-óra) | folyt.92 / journal 17/928 |
| **cx-corner** | kizárva (PAS INT_MAX ≥ PIL TURBO) | folyt.82/101 |
| **SMMU/mem-permisszió, pinmux/reset/interconnect** | nincs delta (strukturális) | folyt.79/83 |
| **Delta A (feltételes MEM_SETUP)** | halott (mbn relocatable → MEM_SETUP tüzel) | folyt.92 |
| **0x2c marker (QDSP6SS 0x10b)** | ADSP-írt OUTPUT, nem kar; gate=0 mindkét oldalon | folyt.91/93/94 |
| **Bjorn 1075549 NGD-race** | tesztelve, no change | github-reply-to-z3ntu-2 |
| **q6_core_clk clock-fail (F3, ss=2 CVD)** | red herring — byte-azonos fw statikus registry, `q6_core_clk` nincs regisztrálva (Q6SS-órák más néven), rossz domain (voice) → boot-út-független, nem PAS≠PIL | folyt.117 (registry-RE) |

---

## 2. AZ AP-OLDAL KIMERÍTÉSE — ÉJSZAKAI KAMPÁNY (folyt.104–113)

A folyt.103 utáni fork MINDHÁROM AP-közeli ága lezárva
(1: TZ SCM metadata-diff, 2: globális boot-állapot, 3: ADSP PLL-leaf):

| taszk | ág | verdikt | folyt |
|---|---|---|---|
| **T1** SSR-diszkriminátor (élő) | boot-sorrend/timing | friss PAS `auth_and_reset` MINDEN más subsystem UTÁN → framer így is DEAD → timing-ág KIZÁRVA | 104 |
| **T5** TZ-input checklist (offline) | (a) TZ SCM metadata | metadata-alloc (dma_alloc_coherent 4K/non-cache) + SCM arg-szemantika (SCM_RW) + call-sorrend EKVIVALENS, nincs közbülső hyp_assign, a PAS-auth SIKERES → (a) NEM támogatott (a divergencia a sikeres auth UTÁN van) | 107 |
| **T2** warm-chain (élő) | (b) globális-állapot-öröklés | UT(framer él, PIL) → warm reboot pmOS-be power-off NÉLKÜL → framer DEAD; a warm reboot megőrzi az RPM/PMIC always-on-t, mégis halott → (b) KIZÁRVA (T1+T2 együtt kiüti) | 110 |
| **T3** TZ-log two-sided (élő) | TZ runtime | `tzlog.py` mindkét oldalon (pointer @0x08600720 → diag PA 0x866fb000, valid tzdbg_t); 15 közös TZ-msg-kód (RPM/SPM/clock), semmi error/fault/xpu. Konstrukciós korlát: a TZ-ring TZ/RPM/SPM/PSCI-t naplóz, NEM az ADSP-framert → (c) láthatatlan, TZ-RE-seed nem nyílik. Dumpok: `report-attachments/tzlog-night/` | 110 |
| **T6** icc/RPM-bw-vote (élő) | utolsó AP-vote | a mainline `scm` node-hoz `interconnects=<&pcnoc MAS_CRYPTO &bimc SLV_EBI>` → `qcom_scm_bw_enable()` UINT_MAX-ot votol crypto→EBI-re PAS alatt (bizonyítva: `firmware:scm` icc-kliens) → framer így is DEAD → utolsó AP-látható divergencia KIZÁRVA | 105/113 |
| **T4** ADSP F3 DIAG-tap | DSP-belső log | ISMÉTLŐDÉS-ŐR: a CNTL-bind FATÁLIS (SoC-fagyás→reboot), a DATA-csatorna maszk nélkül framer-bukáskor 0 frame → NEM futtatva | 106 |
| **T12** web | upstream | nulla új mozgás (#255 + fórum unresolved); új (c)-ötlet a #255-ből: „LPASS xPU access gate" a fizikai framer-óra előtt (TZ/PIL-programozott, nem AP) | 109 |

**Konszolidált éjszakai verdikt:** AP + fw + TZ-input(T5) + boot-sorrend(T1) + globális-állapot-öröklés(T2) +
TZ-runtime(T3) + utolsó bw-vote(T6) — MIND kizárva/ekvivalens. A fal tisztán (c): ADSP-BELSŐ framer/PLL-precondíció,
a sikeres PAS-auth UTÁN, az ADSP fw-ben.

---

## 3. DEPREKÁLT CAPTURE-HELYEK / FW-CAVE ZSÁKUTCÁK

### `f019abb0` / HWL4 statikus CGC-leaf (folyt.111)
A snapHWL4 fix-VA leaf-cave (`f019abb0` = `halHwIo_EnableCgcClock` return, fix `r14=0xe1302ab0`,
disasm-verify PASSED) → **capture ABSENT** pmOS-en. A chain validált volt (snapVA: a `0xe1302ab0` írható+perzisztens
a config-group-fázisból) → NEM törött mérés. Verdikt: a leaf a KORAI fázisban ír (vagy nincs a framer-óra útján,
vagy a késői SMEM item-469 alloc kinullázza a config-group fázis ELŐTT) → **capture-helyként DEPREKÁLVA.**

### config-group dinamikus capture — a szoftver-dispatch AZONOS (folyt.114–118)
A `f04bfba0` splice-cave TÜZELT (magic 'CGP1'). Live dispatch: handle=`memw(ctx+0xe18)`,
`memw(handle+0x48)=0xf019eb40` resolver-thunk →…→ `memw(memw(handle+0x3c)+0)` driver-node.
- **UT pozitív-kontroll (folyt.116):** a level-1 dispatch-állapot AZONOS működő↔halott (a „feloldatlan thunk" a
  MŰKÖDŐ UT-n is ott van) → a thunk NEM kar.
- **snapCGP2/CGP2b (folyt.118):** `0xf04df244` disasm: `r17=memw(handle+#0)` = RCGR/CBCR MMIO-bázis (adat-mező, NEM
  immediate) → nincs hardkódolt regiszter, a bázis futásidejű. snapCGP2 UT (framer ÉL): `handle+0x3c=NULL` a MŰKÖDŐ
  oldalon is, `+0x38=0`, `+0x40=0xf098cab0` → a deeper-hop holt ág. snapCGP2b pmOS (dead): `handle+0x38/+0x3c(NULL)/
  +0x40/+0x44/+0x48(0xf019eb40)/rc` MIND BYTE-AZONOS working↔dead.
- **Verdikt:** a config-group dispatch-objektum és ptr-graf teljesen azonos mindkét oldalon; a szoftver NEM divergál.
  A config-group ÚTVONAL LEZÁRVA — a fal tisztán fizikai realizáció.

### `0xee00d01c` mint framer-branch CBCR — FÉLREAZONOSÍTVA (folyt.122 → 127b)
A snapCKB3 handle+0x1c = CBCR-cím `0xee00d01c` (= 0xee000000+0xd01c) → először ezt hittük a framer-branch-nek.
**CKB7 UT-golden (folyt.127b) cáfolta:** a `0xf04df0c8` enable-primitív a framer-blokkban a `0xee012014`+`0xee012018`
regisztereket enable-eli, a `0xee00d01c` SOSEM enable-elődik a working oldalon. ⇒ a `0xee00d01c` **más óra,
félreazonosítva** — ezért nem vezetett sehová a CKB3, és ezért hangolt a CKB6-force.

### snapCKB4 / CKB5 (post-enable + discovery) — hamis-negatív (folyt.119–126)
A `0xf04df0b4`-be splice-olt cave csak az egyik CBCR-enable ágat fogta el (a SET két útja a `0xf04df0c8` store-nál
egyesül) → **hamis-negatív** („a HW-desc accessor-vtable soha nem fut"). A helyes splice-pont a `0xf04df0c8`.

### snapCKB6 (force-CBCR write lever) — DETERMINISZTIKUS NO-BOOT (folyt.126)
A CBCR-bit brute-force HANG-eli az ADSP-bootot → a branch a rendes enable-szekvenciát igényli,
NEM fixálható erőltetéssel.

### q6afe / APR untested-lead — KIMERÍTVE (folyt.125–126)
1. **AFE-clock ág HALOTT** — 0/54 SLIMbus clock ID a Q6AFE enumban (a framer-óra nem AFE-exponált).
2. **AFE-port ág CÁFOLT** (folyt.9.30).
3. **AFE-config(SLAVE)** = `afe_set_config(AFE_SLIMBUS_SLAVE_CONFIG)` = param `AFE_PARAM_ID_CDC_SLIMBUS_SLAVE_CFG
   0x00010235` — a mainline q6afe.c DEFINIÁLJA + van `q6afe_set_param()` plumbing, DE nincs hívó, és a mainline
   wcd9335 nem generál blobot. Scoping: ez a codec PROBE UTÁN megy (post-framer port-config), NEM a framer-trigger.

### ACDB-mint-framer-trigger — CÁFOLVA (folyt.127 korrekció)
A folyt.126 „framer-trigger = ACDB-bring-up" állítás TÉVES volt (soft regresszió). Az arany-trace (journal:44-63,
KEMÉNY élő időrend): a framer t=22.262-kor keretez — pusztán a slim QMI (SvcId 0x301) SELECT_INSTANCE+POWER_REQ
handshake-től —, MINDEN ACDB/audio-QMI forgalom (t=25+) ELŐTT. Az ACDB post-framer. Megerősíti folyt.58c:
a teljes AP→ADSP QMI-tartalom (a SELECT_INSTANCE „3. TLV"-vel együtt) EXONERÁLVA — „not the lever".

---

## 4. LEZÁRT MÉRÉSEK, AMIK A JELENLEGI FRONTIERHEZ VEZETTEK (folyt.119–127c)

Ezek NEM zsákutányok, hanem a fal fizikai-realizációig szűkítő lépések — itt archiválva, mert
a `summary.md` §0-ból kikerült a részletük:

- **folyt.119 (pmOS, HIT):** a framer-óra (0x12014) enable-metódusa LEFUT a halott oldalon, RCGR BASE=`0xee012000`
  (domain 0x12000→runtime-map). → a kód NEM skippel, valós MMIO-bázis.
- **folyt.120–121:** post-enable RCGR `CMD_RCGR=0x80000000, CFG_RCGR=0x00000509 (src=5,div=9)` — **BYTE-AZONOS**
  UT↔pmOS. A poll-idejű ROOT_OFF=1 NEM differenciál (a működő UT-n is 1); az RCGR csak a rátát állítja. ⇒ a kapu nem
  a root, hanem a BRANCH-óra (CBCR) szintjén.
- **folyt.127b–c (CKB7/CKB7b) — DÖNTŐ:** a helyes framer-branch = `0xee012014`+`0xee012018`; az enable BYTE-AZONOS
  a UT-golddal (mindkettő ENABLED, caller `0xf01d41ec`, value `0x1`). ⇒ a branch-enable megtörténik a halott oldalon
  is, azonosan → a fal FIZIKAI (a parent RCG-root `0xee012000` / source LPASS-audio-PLL nem táplál PAS alatt).
- **Módszer-győzelem:** dead-oldali mérés SSR-reload deploy-jal (`cp mbn; echo stop/start > remoteproc2/state`, ~8s,
  reboot NÉLKÜL) — megkerüli a cold-boot/fastboot-flakiséget.

**→ A jelenlegi NYITOTT frontier (TESZTELENDŐ, l. summary.md §0): CKB8 — a parent-óra táplálásának mérése.**

---

## 5. INCIDENSEK / TANULSÁGOK (nem lead, hanem guardrail-forrás)

- **Journal disk-full reboot-loop (folyt.119):** sok cold-reboot közben a systemd-journal 289M-re hízott → 2.4G
  loop-rootfs MEGTELT → reboot-loop. FIX: journal-sapka `/etc/systemd/journald.conf.d/cap.conf` (SystemMaxUse=40M) +
  vacuum. Guardrail: cold-boot deploy előtt journal-vacuum + df-gate.
- **CKB3-wedge „incidens" (folyt.121):** FÉLREÉRTÉS volt — tranziens retry-fastboot, a cave ártalmatlan (pmOS bootolt
  CKB3-mal, remoteproc=running).
