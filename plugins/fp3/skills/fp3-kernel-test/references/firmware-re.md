# fp3-kernel-test — ADSP firmware RE & patching (full text)

> Split out of `SKILL.md`; loaded on demand when you build a cave / patch the firmware.

## Inspecting and patching the ADSP firmware (the RE track)

When AP-side probes exonerate the AP (the driver is byte-complete, registers show
the *remote* side silent), the question moves into the co-processor firmware. The
method is: establish it's the *same* firmware as the oracle, read what it decides,
then — if needed — instrument or patch it and re-measure.

### First, decide whether the firmware can even be the differentiator
- **How:** byte-compare the oracle's and test-side's firmware. Mount both slots'
  firmware partitions read-only and `cmp` (real byte diff, not just a hash the user
  won't trust). (Example layout: PIL `adsp.mdt`+`adsp.bNN` on the vfat *modem*
  partition; AVS `.so` on the ext4 *dsp* partition; pmOS loads the concatenated
  `adsp.mbn`.)
- **Interpret:** identical firmware ⇒ any difference is *environmental* (how the AP
  brings the co-processor up / what clock+bus environment it sees), not the code.
  That single result reframes the whole investigation.

### Disassembling the image
- **How:** it's an unencrypted QDSP6 ELF32 (Hexagon, `e_machine=164`) — use LLVM
  (`llvm-objdump`/`llvm-mc`, Hexagon target; capstone has no Hexagon). llvm-objdump
  has no `-b binary`, so disassemble **each PT_LOAD separately at its own vaddr**:
  wrap the segment bytes in a minimal elf32-hexagon (one `.text` at the seg vaddr)
  and `-d`. Disassembling the whole file as one blob gives wrong addresses because
  each segment has a different vaddr↔offset delta. Verify a real prologue
  (`allocframe`) appears at a segment start.
- **Interpret:** string cross-refs use constant-extenders (`immext` base + low
  bits), not plain pointers; `##`-immediates are absolute+encoded so they resolve
  regardless of load base — grep the disasm for the `immext` base to find who
  references a string.

### Reading what the firmware decides (config/devcfg)
- **How:** find the property-read pattern (`combine(##name_ptr, r17); call
  <GetProperty>; value = memw(out+8)`), then map the config-struct field offsets the
  code branches on.
- **Interpret:** those offsets are the decision inputs; tracing which one gates the
  behavior tells you what to force/observe. (Worked example: SLIMbus devcfg fields
  `is_master`→`+0x58`, `sat_hw_owner`→`+0x74`, framer-mode→`+0x78`.)
- **☠️ A "linear function" you assume (`framer_start(){ wait; superframe; capability; enumerate; }`)
  is often really an EVENT-DRIVEN STATE MACHINE — and its "wait_for_precondition" is a HARDWARE
  STATUS-BIT POLL, not a flippable software gate.** Don't hunt for a linear function or a toggleable
  `.bss`/config condition. Localise it instead: (1) the `adsp.mbn` is DIRECTLY llvm-objdump-able as
  ELF32 (`--triple=hexagon --start/stop-address` on the code segment; `make_disasm_elf.py` is only for
  the RAW coredump blob, not the signed mbn); (2) convert `strings -td` DECIMAL file-offsets to VAs via
  the program headers (`llvm-readelf -l`: VA = off − p_offset + p_vaddr); (3) grep the ULOG format-string
  VA's high part `& ~0x3f` as `immext(#…)` (⚠️ high addresses render NEGATIVE: `##0xf0726bca` →
  `##-0xf8d9436`, grep both forms); (4) the target function surrounds the log call. When the "precondition"
  turns out to be a HW status bit (not `.bss`/config), static RE tells you WHERE the wait is, but the
  lever is PHYSICAL — there is nothing to overwrite; that positively closes the "is there a software
  branch?" question. (Worked example, folyt.185: framer-START = a timer-driven poll `0xf04c3ca8` on the
  FS/SFS/MS bits (`+0x604` bit 11/12/13, extractors `0xf04c0218/24/30`), 51 polls then a timeout handler
  `0xf04c3538` "Hardware failed to enumerate FS/SFS/MS" → HW-reset (runs, "successful") → mode decision;
  capability/enumerate are gated behind FS=1.)
- **A DIFFERENT variant of the vendor kernel — one that doesn't even run on your SoC — can DOCUMENT the
  co-processor's register map; cross-validate it against your co-processor disasm.** The AP-side FP3 NGD
  is the *satellite* (`slim-msm-ngd.c`, no framer-register access), but the AP-*master* variant
  (`slim-msm-ctrl.c`) has enums giving the framer/interface register offsets + bit positions that the
  co-processor firmware uses identically. (Worked example, folyt.185: `+0x604`, which the ADSP disasm
  polls for FS/SFS/MS bit 11/12/13, is per the vendor enum **`INTF_STAT` (interface status), NOT
  `FRM_STAT`(0x404)** → the framer waits not on its own flag but on the INTERFACE (PHY-side) bus sync;
  the same file gives the HW activation preconditions `clk_set_rate(rclk,24576000)`+gear10+`FRM_CFG`
  FRM_ACTIVE and a lost-sync workaround "wait 20 superframes after a clock-pause" → sync acquisition is
  physics-sensitive even on the *working* stack.) Method: after identifying a co-proc register offset,
  grep the downstream `drivers/<subsys>/*.{c,h}` for the offset AND the named enums (`0x600`, `0x604`,
  `FRM_`, `INTF_`, `_STAT`) — the bit-names and workaround comments may be there even if the code path
  doesn't run on your SoC. Artifact: `references/slimbus-vendor-register-map.txt`.

### Following a runtime pointer chain (when static disasm bottoms out at a vtable)
Static disasm stops the moment the code does `callr memw(obj+N)` or reads a register
base out of a runtime-allocated struct — the target isn't in the image, it's populated
at boot. Don't guess it (rule: a cave derefs only what the code derefs). Instead **walk
one pointer level per cold boot**: reuse a *proven* splice site and change only the
cave payload to stash `{ptr, memw(ptr+0), memw(ptr+K)…}` — the raw fields at that level
— then resolve the next hop offline and repeat.
- **A resolved pointer that lands in rodata/text is followable offline — no extra cold
  boot.** If the stashed value is a *static* address (a vtable in rodata, a function in
  text), dump/disassemble it from the image directly; only *runtime* addresses (bss/heap
  allocations) cost another boot to walk. (Worked example: the SLIMbus core-clock op was
  `memw(handle+0x48)` = a runtime fn-ptr — one boot to read — but it pointed at a HAL
  vtable in *rodata*, so its methods resolved offline for free, saving a boot.)
- **Know when you've hit a framework, not a leaf.** The Qualcomm clock enable bottoms
  out not in a register poke but in a **full NPA (Node Power Architecture) vote/rate
  framework**: the "op" methods aggregate frequency votes (`minu/maxu`) and write
  computed rates into node structs; the physical CBCR write is behind *runtime-registered
  driver nodes* several hops further. The load-bearing insight this yields: **an NPA
  clock "enable success" (rc = 0) means a vote was registered and a rate computed — it is
  decoupled from whether the physical clock branch actually toggled.** That is exactly
  how a "false success" arises without any error code to find.
- **A clock "enable" has TWO sub-paths — walking one does not cover the other.** The
  NPA vote/rate path (above) is the *power/rate* side. The actual register poke is a
  *separate* call from the same enable primitive: DAL-clock → config-group processor →
  `ClkRgm_EnableClock` → `HalHwIo_EnableClock`/`halHwIo_EnableCgcClock` (the HWIO
  register-level clock-gate control, in `hal_hwio_clkctrl.c`). If a prior walk bottomed
  out in the NPA framework and reported "zero MMIO / all runtime fn-ptr", that only
  exonerated the *vote* side — the config-group/HalHwIo register path may be entirely
  un-walked. Re-check the enable primitive's *other* calls before concluding the whole
  enable is MMIO-free. (Worked example: an earlier cave walked handle→subobj→apply_fn and
  found pure NPA aggregation; a later static RE found the enable primitive *also* calls
  the config-group processor, which reaches the HWIO register HAL — the actual poke.)
- **"No materialized MMIO constant in the disasm" does NOT mean "no MMIO".** The HWIO
  clock HAL maps its register base at init (`HalHwIo_Init` → "HWIO memory region created",
  a DAL/devcfg attach) and stores it in a `.bss` descriptor table; the actual poke is
  `memw(runtime_base + offset)`. So a segment-wide scan for absolute hardware addresses
  finds *nothing* even though the fw does register writes. When such a scan comes back
  empty, suspect a runtime-mapped base (devcfg-derived), not an RPM-only/MMIO-free design.
  Corollary when scanning: `immext(#0xffXXXXXX)` paired with a `call`/`jump` is a
  *PC-relative branch displacement*, not an address; `memw(rN+##0xffffffc4)` is a
  *negative struct offset* (rN−0x3c), not an absolute read; `##-0xf0xxxxxx` resolves to a
  `0xf0xxxxxx` rodata string pointer. Filter these out before believing a "hardware read".
- **The false success can extend through EVERY software layer.** Measured register-close:
  not only the NPA vote returns rc=0, the config-group register-config path *also* returns
  rc=0 — the entire software chain reports success while the physical framer stays dead.
  Confirming this at successive layers is worthwhile (it rules out "a lower SW layer
  noticed the failure"), but it also means no rc/error anywhere localises the fault — only
  a *hardware-state* read (PLL lock / CGC status) or a two-sided `.bss`-input diff can.
- **A candidate leaf is only "the poke" once a positive control confirms it runs on the
  WORKING side.** The config-group→`halHwIo_EnableCgcClock` HWIO leaf (above) *looked* like the
  register poke, but a positive control refuted it: a cave spliced at its splice-return, built
  into a *working*-slot firmware and cold-booted with the framer verified alive, showed the cave
  **never fired** — so that leaf is not on the framer bring-up path on *either* OS. Lesson: before
  building a differential on "leaf X is the enable", splice X on the **oracle** and prove the cave
  fires while the feature works; a cave that's absent on the working side exonerates X, it doesn't
  confirm it. (This is the firmware-layer form of "one-sided is not a differential".)
- **When the real poke is runtime-DISPATCHED, static RE bottoms out for good — capture it
  dynamically.** For this clock the physical CBCR write is reached via `callr memw(memw(subobj+4)+4)`
  where `subobj+4` is a **runtime-registered driver node** (the fn address is written into the
  runtime vtable at init, not present in rodata/text). No amount of static disasm pins it. The
  resolution is a **dynamic-capture cave**: splice on the enable path, stash the *resolved* fn
  pointer (`memw(memw(subobj+4)+4)`) to SMEM, and read it back — then disassemble that address for
  the actual `memw(base+off)` poke + poll-mask. Crucially, the **runtime-PM re-trigger** (above)
  makes this iterable: once a caved fw is loaded (one flash+boot), each `echo on > .../power/control`
  re-runs the enable and re-fires the cave — no reflash per hop. Verify first (invocation counter in
  the cave) that the runtime resume re-enters the same enable primitive as boot, since a runtime-PM
  path *can* differ from the cold-boot path.
- **The register base IS reachable — capture it at the clock's own enable-method, filtered by the
  clock's identity.** The breakthrough that got past "runtime base, un-pinnable": find the clock's
  static registry entry (name→ID→ops-vtable→enable-method — e.g. the framer's `audio_core_slimbus_core_clk`
  entry at a fixed rodata addr holds `+0x04`=clock-ID `0x12014`, `+0x14`=HW-desc, `+0x2c`=ops-vtable
  whose `[0]`=the enable-method). Splice **inside the enable-method** at a point where the handle arg
  (`r0`) is still live *and* the base has been loaded (`r17 = memw(handle+0)`), and stash it. The
  **runtime handle layout** (worked example): `+0x00`=**register base (real MMIO, e.g. `0xee012000`)**,
  `+0x04`=**pointer to the static registry entry**, `+0x0c`=ops-vtable, `+0x1c`=a *second* MMIO ptr
  (the branch CBCR). **Filter by the registry-entry pointer, not the raw ID** — the clock ID is not
  stored flat in the handle; `memw(handle+0x04)` *is* the registry-entry address (a constant you know
  from the static RE), so scan the handle words for that. The base is domain-mapped deterministically
  (`domain 0xNN000 → 0xee0NN000`), so a sibling clock's capture cross-checks yours. **Two splice points,
  two questions:** splice at method *entry* (pre-write) to read the reset/default RCGR; splice at the
  method's *UPDATE-poll read* (a single-word `r2=memw(base+0)` packet — trivial single-exit) to read the
  settled RCGR. Never deref the base until a capture has proven it valid (CGP2b lesson); once proven
  (the method itself reads/writes it), reading the whole RCGR block `memw(base+0..0x14)` = CMD/CFG/M/N/D
  is safe (clock-controller regs are always accessible).
- **☠️ Offline-disassemble the *patched image* before every cave deploy — it costs nothing and catches
  encoding bugs a boot-hang would otherwise reveal expensively.** After assemble+splice+patch, read the
  bytes back *from the built `.mbn`* and disassemble (1) the splice word (→ must jump to the cave), (2)
  the whole cave (filter constants, guard branches, RCGR reads), (3) each trampoline/exit jump (→ must
  land on the exact intended VA). Verify the enc_jump displacements arithmetically. A cave spliced into
  a hot path (a clock enable-method runs for *every* clock at boot) that has one bad instruction hangs
  the ADSP for *all* clocks — the disasm-verify turns that into a caught typo.
- **Multi-exit cave (replicating a conditional packet): local labels + hand-encoded trampolines; prefer
  a single-word non-branch splice when one exists.** If you must splice a packet that ends in a
  conditional jump, replicate it as: internal control flow via **local labels** (llvm-mc resolves those
  PC-relative displacements correctly inside the blob), and each *external* target as a 1-word
  placeholder (`{ r17 = r17 }`) that you **overwrite post-assembly** with a hand-encoded absolute
  `enc_jump`. Place the trampolines as the last words so their positions are known. Far simpler: pick a
  splice point that is a **single-word non-branch instruction** (e.g. a `memw` load) — then the cave has
  one clean exit (append one `enc_jump` back, snapCGP-style) and no conditional to reproduce.
- **The cleanest splice of all: a leaf that returns via `jumpr r31` — the cave needs NO return address.**
  When you splice inside a function that ends in `jumpr r31` (returns to whatever called it), the cave can
  do its work and end with its own `{ jumpr r31 }` — no trampoline, no fixed return VA, no `enc_jump`
  except the one splice jump *in*. Registers r0–r5 are caller-saved (scratch) across a Hexagon call, so a
  leaf cave may freely clobber them (preserve only what the replicated instructions need). (Worked example:
  the CBCR-enable leaf `memw(CBCR)|=mask; jumpr r31` — spliced one packet earlier, the cave replicated the
  `|=`, re-read the register post-write, stashed, and returned with `jumpr r31`.)
- **RCGR (rate) vs CBCR (gate) are different registers — and the branch CBCR is where a clock actually
  turns on/off.** A Qualcomm clock has a root/rate generator (RCGR: CMD/CFG/M/N/D) *and* a branch control
  (CBCR: bit0=ENABLE, bit31=CLK_OFF). Programming the RCGR sets the *rate*; the clock only runs when its
  CBCR is enabled *and* its parent is feeding it (CLK_OFF clears). So "is the clock running?" is a **CBCR**
  question, not an RCGR one. **Finding the branch CBCR's address at runtime — capture what the enable
  primitive actually writes, not a handle heuristic.** The **CBCR-enable** is its own leaf
  (`memw(memw(desc+12)) |= memw(desc+16)`, separate from the RCGR enable-method, with a sibling
  **status-poll** leaf that reads the CBCR and tests CLK_OFF). Splice the *convergent* store of that leaf
  and read the target register it writes — that captured target is the real branch (worked example: framer
  branch CBCR = RCGR-base + `(id & 0xfff)` = `0xee012000 + 0x14` = `0xee012014`; splice post-write to see
  whether the branch actually starts). ☠️ **Do NOT trust the handle-field/registry-offset heuristic here:**
  `handle+0x1c` and registry `+0x3c` (=`0xd01c`) plausibly look like a CBCR pointer (`0xee00d01c`) and even
  survive a force-write, but that address is a *different* clock the framer never enables — weeks were spent
  on it (see "a cross-verified address can still be the WRONG register" below). Only the captured store
  target is the lever.
- **These ADSP clock registers are NOT AP-readable — confirm before reaching for `/dev/mem`.** The framer
  clock is owned by the ADSP's AFE clock service (q6afe); msm8953 has no `lpasscc`/AP clock-controller for
  it, so its CBCR/RCGR (`0xee0xxxxx` in *ADSP* address space) cannot be read from the AP at all — an ADSP
  cave is the only instrument. Grep the kernel DT/clk-driver for an AP mapping first; a co-processor-owned
  clock has none, and the "read it live from `/dev/mem` on both slots" shortcut is simply unavailable.
- **UNTESTED LEAD (soft — from upstream sources, not yet measured on-device): the framer/codec clock may be
  reachable as an APR `AFE_SET_CLK` request to q6afe — a THIRD channel beyond "AP clock" and "ADSP-internal
  clock".** The skill currently closes "no AP-side lever exists" because there is no `lpasscc` AP
  clock-controller. But the ADSP's AFE clock service (q6afe) is itself a *message* interface: the downstream
  enables the digital-codec/reference clock by sending an APR clock-set command to the DSP, not by toggling
  an AP register. Upstream msm8953 audio (the `apq8016_sbc` msm8953/msm8976 series) turns on the **Q6AFE CLK
  API version** as the SoC's key differentiator — msm8953 is **API V2** (`Q6AFE_LPASS_CLK_ID_*` per-interface
  IDs), realized through `q6afe-clocks`. The FP3 ADSP runs the legacy AVS (`ADSP.VT.3.0`, confirmed by the
  SMEM version-string exfil) → APR-based (not AudioReach), so the q6afe/APR path *should* apply. **Testable
  hypothesis + its own deploy vehicle (ASoC/APR edit, NOT an NGD/QMI edit):** (1) confirm a live APR/GLINK
  ADSP channel exists at all on the mainline FP3 stack (`q6afe`/`q6core`/`q6adm` in the DT, an `apr`/GLINK
  node, a `/dev/apr*`); (2) capture whether the *downstream* fires an AFE clock-set for the codec/framer
  reference that mainline never sends; (3) if so, request that q6afe clock ID from mainline and re-measure
  `FRM_STAT`. This has not been run — label it PUHA until an on-device differential exists; it is here so the
  next session tries the APR lever before re-deriving "no AP lever."

### Patching + re-signing (the firmware is writable if secure-boot is off)
- **Why it works here:** the device ships with firmware secure-boot **off**, so
  testkey-signed images load. A bare byte-patch fails PAS auth with `-22` — but that
  is a **hash-segment mismatch, not a cert lock**; re-signing fixes it.
- **How:** map vaddr→file-offset via the ELF32 phdrs **per segment** (each PT_LOAD
  has its own delta, and re-signed offsets differ from stock). Assemble Hexagon
  patch bytes with `llvm-mc --arch=hexagon --mcpu=hexagonv60` + `llvm-objcopy -O
  binary`. Re-sign with `qtestsign -v3 adsp`. Confirm the patched bytes survive
  re-signing (segments realign to 1 MB but content is preserved).
- **Deploy:** swap the firmware file, SSR-reload (above). Keep a `.stockbak`.
- **☠️ A PAS-signed `.mbn` (pmOS) is NOT accepted by the oracle's PIL path.** The pmOS/PAS
  loader takes the whole concatenated `adsp.mbn` and TZ auths it; the vendor UT/PIL loader
  (`subsys-pil-tz`) instead loads a **split** `adsp.mdt` (ELF header + phdrs + hash segment)
  + `adsp.b00..bNN` (one file per segment), and passes only the *mdt* to
  `qcom_scm_pas_init_image`. A `qtestsign -v3` mbn that loads fine under PAS is **rejected
  by PIL with `Initializing image failed(rc:-22)`** (EINVAL, a hash-seg/mdt-format reject) —
  because a hand-extracted `mdt = mbn[0:end-of-hash]` is *page-aligned* (hash at file offset
  0x1000 with padding) whereas the stock mdt is **compact** (`stock mdt size == b00 + b01`,
  hash packed right after the phdrs). (The pmOS/PAS cave has no such issue.)
  **The full fix (proven to load an oracle-side cave):** (1) **compact mdt** — build it as
  `mdt = signed_mbn[0 : ph[0].filesz] + signed_mbn[ph[1].p_offset : +ph[1].p_filesz]`
  (the ELF-header+phdrs segment, then the hash segment, *contiguous, no padding* — matches
  the stock layout; the phdr[1].p_offset staying page-aligned is fine, PIL/TZ reads the hash
  compact right after the header, exactly as the stock mdt does). That clears the `-22`.
  (2) Then PIL loads the `.bNN` segments and you hit **`Blob size 0 doesn't match <N>` /
  `Failed to load the segment[i]`** if you kept the *stock* `.bNN` alongside your re-signed
  mdt — because a `qtestsign` re-pack can shift some loadable segment sizes by a few bytes,
  so the stock `.bNN` no longer matches your mdt's phdr sizes. Fix: deploy the **full split
  of your own signed mbn** (every `adsp.b{i:02d}` = `signed_mbn[ph[i].p_offset : +filesz]`
  for each PT_LOAD, plus the compact mdt) so mdt and all segments are self-consistent. With
  both, the oracle ADSP loads (`Brought out of reset`), the framer comes up, and the cave
  runs. Verified 2026-07-11.
- **Writing a RO vendor firmware partition (the oracle's `firmware_mnt`) — go through the
  block device, not the mount.** On UT/Halium the firmware lives on a **RO vfat**
  (`/dev/mmcblk0p1`, `/vendor/firmware_mnt`) inside the Android LXC container;
  `mount -o remount,rw` *returns success but stays RO* (`WRITE_FAIL`, "Read-only file
  system"). Method that works and is brick-safe: `dd` the **whole** partition to a file
  (this is your full backup), pull it to the host, **loopback-mount it RW on the host** and
  replace the files there, push it back, then on-device `umount /vendor/firmware_mnt` (the
  fw is already in DDR post-boot, so it's free) and `dd` the modified image **onto the block
  device** (bypasses the RO mount) + `sync` + immediate reboot. Verify by reading the block
  device back (`dd … | md5sum`). Recovery is a `dd` of the stock image back — keep it. This
  is heavier than the pmOS rootfs-file swap; it is oracle-partition surgery, so full-image
  backup first, and confirm the framer/ADSP recovers after restoring stock.

### Getting data *out* of the co-processor (the exfil channel)
You can't read its private carveout (rule 5) and it has no bound DIAG/trace char
device on this kernel — so a firmware patch that **writes into a shared region the
AP can read** is the observation channel.
- **How the channel works:** SMEM (the shared-memory heap) is AP-readable via Python
  `mmap` and co-processor-writable. Find a heap item whose address the firmware
  already computes (e.g. the version-string item) and stash your data at a known pad
  offset inside it; the AP mmaps SMEM base and reads it back.
- **Validate the channel before trusting a measurement through it:** patch a
  *known constant* into the stash, reload, read it back on the AP. Only once the
  end-to-end patch→sign→load→run→SMEM-write→AP-read chain returns your constant do
  you trust a real trace through it. (Worked example: the "C0DED" marker test at
  SMEM PA `0x86300000`, item id 469.)
- **Locate the stash offset from the live TOC, never a hardcoded constant.**
  `fp3-porting-debug/scripts/smem_toc_read.py` (SAFE — single bounded mmap of *only*
  `0x86300000`) parses the legacy header (heap_info @+0xC0: free_offset/remaining)
  + TOC (entry @ `0xD0 + id*16` = {alloc,off,size,aux}) → item 469 lives at
  in-SMEM offset **0x2470**, size 0x1000, so the ADSP slot #12 is at
  **PA 0x86302a70** (in-SMEM 0x2a70). Confirmed live 2026-07-09: that slot holds
  `12:ADSP.VT.3.0-00161-00000-1`. NOTE the version strings on this build are the
  **short `NN:NAME.VT…` form, NOT the literal `QC_IMAGE_VERSION_STRING`** — a
  search for that magic returns nothing and falsely reads as "item moved" (it
  never moved). The 128-byte slot has ~100 pad bytes after the string for a stash.

### The reusable ENTRY-trace pattern (does function F run? with what args?)
This is the workhorse firmware measurement — a non-destructive way to answer
"is this code path even reached, and what does it see?":
1. Assemble a **cave stub** in a zero-filled executable hole in the image. The stub
   guards/locates the SMEM stash, bumps a counter and records a few argument
   registers, then **replicates the instruction(s) you displaced** and jumps back.
2. **Splice** a single 4-byte PC-relative jump over the first word of F's entry
   packet (a self-contained parse=11 jump; the stale rest of the old packet becomes
   dead code). Re-sign, reload, read the counter/args from SMEM.
- **Interpret:** counter 0 = F never runs (the fault is upstream of F); counter >0
  with the args = F runs, inspect the args to see which branch/condition it takes.
  (Worked example: entry-traces on the framer gate and its caller both read back
  **0**, proving the bring-up is never even invoked — which moved the search
  upstream of the co-processor's decision entirely.)
- **☠️ "F runs on one slot but not the other" ≠ "F is dead code" — the bring-up paths DIVERGE.** When
  the oracle succeeds and the SUT fails, the *late* functions are side-specific: the failure handler
  (e.g. an enumerate-**timeout** logger) runs only on the dead side; the success handler (e.g.
  logical-address-**assign**) runs only on the working side. A cave spliced in either reads back on one
  slot and MISS on the other — not because the firmware differs, but because the paths forked. For a
  two-sided differential you need an anchor that fires on **both**: an **event/state-change handler that
  runs post-event on the working side and during bring-up on the dead side**. (Worked example, folyt.132–133:
  splices at the enumerate-timeout fn and a laddr-assign fn each fired on only one slot; the **framer
  mode-update fn entry** `0xf04c36e8` fired on *both* — on the dead side during bring-up, and on the
  working side just after the "Framer active state changed" handler activates the framer, i.e. with the
  status already showing framing — giving the clean same-anchor two-sided read.)
- **☠️ Splice the function ENTRY, not a log-CALL inside it — log calls are transition-gated.** A
  driver's `MSG("Switching to X mode")` typically fires only when the state *changes*; if the firmware
  initialises straight into the final state (no transition), the log call never executes and a cave
  spliced *on it* reads MISS even though the deciding function ran. Splice the function's entry (fires on
  every invocation, unconditionally) and read the decision variable/inputs directly. (Worked example,
  folyt.130–130b: caves on the "Switching to active/external framer mode" log calls both read MISS on
  pmOS — the mode never *transitioned*; the entry-splice of the same fn read the mode flag `=1`/active
  unconditionally, refuting the "switches to external framer" hypothesis.)
- **☠️ "counter/magic absent" is AMBIGUOUS — it can mean the STASH wasn't ready, not
  that F didn't run. Always run a positive control before concluding "F skipped."** The
  SMEM stash pointer is populated by the co-processor's *own* SMEM/rpmsg init, which
  happens *after* early boot phases like clock bring-up. A cave that guards on
  `if (*stash_ptr==0) return;` and splices a function that runs *before* that init writes
  **nothing** — magic absent — even though F ran fine. (Worked example, 2026-07-11: the
  HalHwIo CGC-enable-leaf splice at `f019abb0` read back absent on pmOS *and* on the UT
  oracle **where the framer works** — so absent ≠ "leaf skipped"; it was a capture-phase
  artifact. The UT positive control is the only thing that caught it before a false "pmOS
  skips the clock poke" conclusion.) If your target runs early, don't derive the stash from
  a pointer that's null then — **read the pointer's value once at a late (SMEM-ready) splice,
  confirm it's a boot-constant, then hardcode that SMEM ADSP-VA** in the early cave (the
  static carveout MMU mapping is valid from boot; only the *pointer* is late).
- **☠️ A cave must NEVER issue its own MMIO read.** Loads from the co-processor's struct
  fields / .bss are fine; a read of a *hardware* register is not. A posted *write* to a
  clock/CGC reg succeeds fire-and-forget, but a *read* to it needs a response and **stalls
  the ADSP if the block isn't fully clocked** → co-processor hang. (Worked example: a cave
  re-read `base+offset` to sample a CGC status "for free" since the leaf had just written
  it — the write had posted but the read hung the ADSP and killed the *working* UT framer.
  Capture only what the firmware itself already loaded into a register.)
  - **Refinement (the safe exception): a cave MAY read a hardware block you have INDEPENDENTLY
    PROVEN is clocked, and doing so can be decisive.** The hang risk is *unclocked* blocks; a block
    whose clock you have already confirmed running is safely readable from the cave. Do it with two
    guards: (1) a **null-guard** on the base register before dereferencing, and (2) a **bounded-probe
    marker** — write a sentinel (e.g. `0xF00D`) to the stash *after* the last MMIO read, so if any read
    hung you see the stash filled only up to the offset before the culprit (and SSR/reboot recovers).
    Read the runtime base the firmware itself uses (a struct field like `memw(ctx+0x5c)`), then read the
    block's registers off it. (Worked example, folyt.131–133: the SLIMbus framer block base `0xee140000`
    — captured at runtime, its clock already exonerated — read 16 registers with zero hang on both
    slots, and gave the decisive result below. `0xee140000` is a **fixed HW address**, so once captured
    on one run every later cave reads it as an *absolute* immediate — no ctx/pointer-chain needed.)
  - **★ Whole-block two-sided read isolates config (levers) from status (markers).** When you can read a
    hardware block on the oracle AND the SUT, read the *entire* register window on both, not just the
    one status reg. If **every config/control register is byte-identical** working↔dead and **only a
    status register differs**, you have proven the co-processor programs the block identically — the
    divergence is a **non-configuration hardware dependency** (a different clock feeding the block, a
    PHY/pad, a sampled external input), not anything the firmware writes. The differing status reg is a
    marker, not a lever. (Worked example, folyt.133: framer block config regs `+0x004/+0x010/+0x600/+0x610`
    all byte-identical UT↔pmOS; only `+0x604` status differed — UT `0x3e04` FS/SFS/MS=1 framing, pmOS `0x0`
    not framing. Combined with the clock already exonerated, this localised the wall to a physical
    dependency the config doesn't cover — a register-level proof of a "realization-layer" fault.)
- **☠️ Keep the SMEM stash footprint within the proven-safe window (here ~0x50 B at
  `stashbase+0x640`).** The stash sits inside one SMEM item; a fat ring overruns into a
  neighbour item and corrupts co-processor state. (Worked example: a 704 B ring degraded the
  ADSP/audio so the UT Halium container failed to start → USB fell to File-Stor/charging-only,
  no adb; a 0x24 B single-record version was benign, framer stayed alive.) Also note UT
  reboots are independently flaky — the container race drops to File-Stor/charging-only even
  on **stock** fw; recovery is a device-side login+replug, not a cave issue.
- **Filtered ctx-scan cave — hunt pointer fields through the tiny SMEM window when you can't dump
  everything (the stepping-stone to a coredump).** If the coredump is unavailable (no `DEV_COREDUMP`,
  or a selective-minidump skipped the heap) or you only want a struct's *pointer* fields, splice a cave
  that walks the ctx (a proven-safe DDR range) and saves **only the (offset,value) pairs matching a
  filter** — e.g. value in a chosen range (LPASS `0xee..` / image `0xf0..`). The filter condenses a big
  struct to the few pointer fields that fit the stash. **The filter choice decides what you see** — if
  the first filter is empty/symmetric, widen it. (Worked example, folyt.71: FRS7 filtered `0xee..`-only
  → just the framer base; FRS8 widened to `0xee..` OR `0xf0..` → surfaced the parent-struct pointers,
  which pointed into runtime heap → proved a *full coredump* was needed, not a wider cave.)
- **No linker needed — hand-encode the jumps.** lld-hexagon usually isn't
  installed, and llvm-mc can't resolve a jump to an absolute external address. But
  a Hexagon `J2_jump` reaches ±8 MB in a single 4-byte word (no immext), which
  covers any cave↔hook distance in one segment. Encoder (verify it against a known
  `{ jump 0xADDR }` from the disasm before trusting it):
  `imm=((target-pc)//4)&0x3FFFFF; word=(0b0101100<<25)|(((imm>>13)&0x1FF)<<16)|(0b11<<14)|((imm&0x1FFF)<<1)`.
  Assemble the straight-line stub body (loads/stores + any *internal* `.Lskip`
  branch, which llvm-mc resolves) with `llvm-mc --arch=hexagon --mcpu=hexagonv60`,
  then append/overwrite the external jump words by hand. `fp3-porting-debug/scripts/build_snap*_patch.py`
  are the reusable template (self-test asserts the encoder reproduces 0x599ecccc).
- **ALWAYS disasm-verify before signing.** Wrap the patched cave + splice bytes
  back into a throwaway elf32-hexagon (`make_elf.py`) at their real vaddr and
  `llvm-objdump -d` them; confirm the stub reads the fields you intend and the
  jumps land on the right addresses. This catches an encoder/offset slip on the
  bench instead of via a wedged device. Then re-sign and confirm the patched bytes
  survive (signed ph4 file_off = `0x15f000 + (vaddr-0xf015f000)`).
- **Entry splices are far safer than mid-function splices.** A splice over a
  function *entry* (fresh context, you replicate the prologue) has reloaded cleanly
  every time. A splice over a *mid-function conditional packet* (to capture a
  call's return value / rc) once took the device down on SSR-reload where the
  neighbouring entry-splice experiments did not — the mid-function replication (a
  `.new` predicate jump + two trampoline exits) is more fragile. Prefer capturing a
  value at the *entry of the next function that receives it* over splicing the
  caller's return site. If you must splice a return site, `sync` first and expect a
  possible reboot. **But the fragility is the *replication*, not the location:** a
  later rc-capture at the *same* mid-function address that had bricked reloaded
  cleanly once the trampoline was removed — instead of replicating the displaced
  conditional packet (`.new` predicate + two trampoline exits), the redesigned cave
  captured its values and closed with a single **unconditional** `J2_jump` straight
  to the function's return point (skipping only the error/ULOG path, which is
  unreadable anyway). So a mid-function splice is safe when the cave is straight-line
  (loads/stores + one unconditional exit) and you can afford to short-circuit the
  rest of the function; it is the conditional/`.new`-predicate replication that is
  the real hazard. (Worked example: Stage-2 with trampolines took the device to
  physical recovery; Stage-2b at the identical splice address, trampoline-free with
  an unconditional jump to the return, reloaded clean and read back the rc.)
- **SSR-reload is mostly reliable but occasionally reboots.** When it does, the
  firmware `cp` into the nested loop-rootfs is rolled back by the journal (you come
  back up on stock — usually a *good* failsafe), and the rootfs has survived intact
  each time so far. Still `sync` before every reload and re-check rootfs health
  (`dmesg | grep -iE "EXT4-fs error|orphan_present"`) after any unexpected reboot.
- **A boot-time-once event won't re-run on SSR-reload after a clean cold boot —
  deploy that probe by cold boot, not SSR.** A one-shot bring-up (e.g. the framer
  clock enable) runs once at cold boot; a later `stop/start` often finds the state
  already settled and the function early-exits *before* your splice, so the stash is
  never written (its magic stays absent). It fired on SSR in an earlier session only
  because many back-to-back reloads had churned the state. Reliable vehicle: write the
  signed firmware to disk and clean-`reboot` so the co-processor cold-boots your patch
  and runs the one-shot path. A cold-boot splice is safe **when it is on a specific,
  single-caller function doing fixed-address reads** — the boot-loop hazard (the
  folyt.43 worked example) was a splice on a *generic, hot* clock worker reading
  *heterogeneous ctx offsets*, a different thing. Two operational notes: `/tmp` is
  tmpfs, so re-`scp` the reader after every reboot (the firmware on `/lib` persists);
  and **ration SSR reloads** — repeated `stop/start` in one session jams the CDC-NCM
  gadget (`NETDEV WATCHDOG: transmit queue timed out`; ping-alive but TCP/ssh dead),
  a *device-side* stall no host-side USB poke clears. It self-recovers in minutes —
  poll passively for TCP to return; **never** force a USB rebind (see the NCM-link entry
  under "Reading the device state" — that makes it *worse*, not better).
- **Prove the reboot actually happened, or you will read a *stale* stash as if it were
  fresh data.** A backgrounded reboot issued over SSH (`ssh '(sleep 1; reboot) &'`)
  gets SIGHUP'd when the session closes and often never fires — the device stays up on
  the *old* firmware, SMEM still holds the *previous* run's stash, and you "capture" a
  value that looks plausible but is last session's (spotting it: the magic is a *prior*
  experiment's tag, not this one's). Method: issue a **synchronous** `systemctl reboot`
  (let the connection drop, ignore the non-zero rc), then **confirm a real cold boot by
  detecting down-then-up** — poll until SSH stops answering (`[down]`), *then* poll until
  it answers again (`[up]`). Only a proven down→up transition means your patch loaded.
  A cheap magic tag per experiment (`SNPA`, `SNPB`, …, not a shared constant) is what
  lets you catch a stale read.
- **☠️ NEVER kill `systemctl reboot` with a short `timeout … || true`.** A short outer
  timeout (e.g. `timeout 5 ssh '… systemctl reboot' || true`) SIGKILLs the SSH before the
  reboot signal propagates → **the device stays up, uptime keeps climbing, and the cave
  never runs** — yet the deploy script logs "cold reboot" and proceeds into `waitdown`,
  which then either hangs or eventually mis-reports. The tell: after "reboot", `/proc/uptime`
  is *large and still growing* and the on-disk `adsp.mbn` is the *patched* md5 but the
  running fw is stock (loaded at the last real boot). Method: issue the reboot
  **synchronously with generous room** (`timeout 15 ssh '… systemctl reboot; echo rc=$?'`,
  expect `rc=0` then the link drops), and confirm down→up as above. If a deploy wedges this
  way, kill the deploy, issue one clean synchronous reboot manually, then catch+read.
- **Keep the deploy rootfs-flat — the pmOS `/` is a ~94%-full nested loop image (~130 MB
  free).** Stage the signed mbn in `/tmp` (tmpfs = RAM, cleared on reboot, zero rootfs
  cost) and **overwrite `adsp.mbn` in place** (same size) — never leave a second
  full-size mbn on the rootfs. If space gets tight, `journalctl --vacuum-size=20M`
  reclaims the most (the journal grows ~tens of MB across a debug session). A persistent
  cap is now in place (`/etc/systemd/journald.conf.d/10-fp3-cap.conf`, SystemMaxUse=30M)
  so the journal no longer refills the rootfs mid-session — but still check `df -h /`
  before a deploy.
- **A single-slot stash captures a *random* invocation when the spliced function
  runs for many instances.** If F is called once per instance (e.g. one clock *group*
  after another, reusing the same config buffer), a last-write-wins stash holds
  whichever fired last — which varies per boot, so successive captures of the "same"
  field disagree (it reads `0x3`, then `0x13`, then `0x2`). Before trusting a
  single-slot value, prove F runs once (a counter — see the ring pattern): if it runs
  N times, either **filter** (stash only when an id field matches your target) or
  capture a **ring** of `(id, …)` across all invocations. You need the target's id to
  filter, so a ring-of-ids capture usually comes first.
- **A post-return splice reads a callee's transient/scratch buffer as STALE — don't walk
  its pointers.** If you splice *after* a function returns (e.g. at the rc-capture site,
  to grab the caller's continuation) and from there read the callee's argument buffer /
  config struct, that memory may already be **reused** by the time your cave runs — the
  callee's transient scratch is only valid *during* the call. The tell: the same absolute
  address reads a *different* value on a second boot, or holds obviously-unrelated content
  (e.g. a version string where you expected a config descriptor). So a persistent global
  read at a post-return splice is fine, but a *pointer walk into a callee's scratch* from
  there is unreliable — capture live data only from a splice that runs *while* the owning
  function is on the stack (accepting the hot/generic-splice hazard), or stick to
  persistent globals. (Worked example: reading the config-group's `cfg@0xf0c854xx` at the
  post-return rc-site gave stable-looking pointers on one boot but a CNSS *firmware version
  string* on the next — the region is transient scratch; only the persistent gate global
  and the live ctx fields were trustworthy from that splice.)

### Firmware-measurement safety (generalise the rule, don't just memorise the crash)
- **Never put a full memory barrier (`syncht`) on the fast path of a HOT hook.** A
  hook that fires thousands of times per second, each doing a barrier, storms the
  co-processor into a watchdog crash → truncated firmware + dirty rootfs +
  boot-loop. Method: **filter first** (branch out on the cheap condition — e.g. the
  opcode you care about — *before* any barrier or SMEM write), or drop the barrier
  entirely on hot hooks. Rule of thumb: know your hook's call frequency *before* you
  put anything expensive in it. (Worked example: entry-traces on rarely-called
  functions were safe; the same pattern on the hot opcode dispatcher crashed on
  boot.)
- **Splice at a function's CONVERGENCE point, not one of its branches — or "never runs"
  may be a path-blind false negative.** A small accessor often has two entry paths that
  do the same store (e.g. a bit-set primitive: `if selector: target=memw(desc+0xc) else:
  target=memw(desc+4), val=1`) which only merge at the common `memw(target)|=val` packet.
  Splicing *one* branch measures only that path; if the event you want takes the *other*
  branch, your cave never fires and you wrongly conclude the function is dead code. Read
  the whole CFG first and hook the merge point (the shared store), so you catch every
  invocation. (Worked example: a CBCR branch-enable primitive was declared "never runs for
  the framer" from a one-branch splice; hooking the convergent store showed it runs 34× and
  identified the *real* target register — the earlier splice was simply on the path the
  framer's enable didn't take.)
- **A "cross-verified" address can still be the WRONG register — let the golden two-sided
  capture name the real target, don't trust a static offset match.** An address derived from
  a handle field + a plausible offset coincidence (`0xee00d01c` = base + registry+0x3c) read
  as a real register and even changed a force-write's behaviour, so it *looked* confirmed —
  but a golden capture of what the working side actually enables showed a *different* register
  (`0xee012014` = base + `id&0xfff`) and that the "confirmed" one is never touched on the
  live path. Weeks of caves aimed at the wrong register. Rule: an offset/heuristic match is a
  *candidate*; only a capture of the value/target the live code actually writes promotes it to
  the lever. (Ties to the marker-vs-lever discipline above.)
- **When you splice ONE word of a multi-word packet, the other words become a separate packet
  that your jump SKIPS — replicate any load-bearing sibling instruction in the cave.** E.g. the
  leaf packet `{ jumpr r31 ; memw(r2)|=r3 }`: overwriting the `jumpr r31` word with a
  jump-to-cave makes the `|=` its own trailing packet that never executes (you branch away
  first), silently dropping the store — harmless for a read-only clock but a boot-breaker for
  a generic enable primitive. The **mandatory offline disasm-verify catches this** (you'll see
  the store split off into its own packet after the jump); fix = do the store inside the cave
  before returning.
- **Never leave a crash-inducing firmware under `recovery=enabled`** — a crash-loop
  dirties the rootfs. Use a non-crashing trace, or set `restart_level=RELATED` so a
  crash stays a co-processor-only SSR (not a whole-AP reboot), and grab your data
  *before* any reboot (a devcoredump is lost across the reboot it triggers).
- **A cave may dereference only pointers the original code itself dereferences.** A
  stub that reads live registers and the small ctx-offsets the displaced code already
  uses is safe; a stub that *walks a guessed pointer chain* (you assumed field X of a
  struct is a pointer to a register) faults the co-processor the instant the guess is
  wrong — an unaligned or wild-address `memw` hangs/crashes it, and the crash can be
  *delayed* (it reads back garbage first, then dies). Method: capture the *raw* fields,
  resolve the struct layout **offline**, and dereference one level only after a value
  has proven to be a valid pointer. (Worked example: a cave that walked `ctx+0xe18` as
  a clock handle read an odd address in image space and text bytes `"AAAQ"`, then
  crashed the DSP — that field was not the handle.)

---

