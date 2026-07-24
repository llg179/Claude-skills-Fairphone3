# fp3-porting-debug — DEVMEM oracle-kernel recipe (repack + from-source build)

> Split out of `SKILL.md` (pure recipe/data). You only need this if the stock UT kernel
> lacks `/dev/mem` — first check whether you even need MMIO (a debugfs `clk_summary` diff
> often answers the question with no custom kernel). See SKILL.md "the oracle" for that decision.

> **☠️ Correction (folyt.154): the UT *stock* kernel has `/dev/mem`, but its MMIO reads are
> RESTRICTED, not just present-or-absent.** In practice on this UT boot, a `/dev/mem` MMIO read
> returns gated junk — a known-clocked GCC block (`0x1800000`) reads all-ZERO, and the LPASS
> framer/block2 read all-`0x40` fill — while the *same* read on pmOS returns real values (after NGD
> force-resume). So an **oracle-side MMIO capture cannot rely on plain `/dev/mem`**; use the
> **loadable module** (`framer_mmio_dump.ko`, ioremap+readl in-kernel — the folyt.143 "byte-identical
> two-sided /dev/mem" actually used the module on the UT side) OR this DEVMEM oracle-kernel. **Verify
> your UT `/dev/mem` against a known-clocked non-LPASS register (GCC) before trusting any UT MMIO
> capture** — if GCC reads 0, the path is restricted and you need the module/this kernel.

- **If you must build the DEVMEM oracle kernel — repack, don't rebuild.** The custom
  kernel (`CONFIG_DEVMEM=y`, `# CONFIG_STRICT_DEVMEM is not set`) is already built; what
  ages out is the packed `boot.img`. Repack in minutes from the stock UT `boot.img`
  (`~/.cache/ubports/FP3/firmware/boot.img`): parse the ANDROID! hdr-v0 (base
  `0x80000000`, page 2048, keep its exact cmdline/addrs); the stock kernel blob is
  `Image.gz-dtb`, so split it at the first device-tree magic `0xd00dfeed` to recover the
  **appended dtb**, `cat` that dtb onto your freshly-built `Image.gz`, keep the stock
  ramdisk, repack (id = SHA1 over each part+its size). `boot_a/boot_b` are 64 MiB.
  **Flash to the oracle slot only with the user's approval, keep the stock `boot.img` as
  the one-command revert** — the DEVMEM kernel keeps the oracle's rootfs, only the kernel
  swaps, so the oracle still boots normally with live `/dev/mem`.
- **Building the DEVMEM kernel from source (the recipe behind the repack).** Exact UT
  source = UBports `android_kernel_fairphone_sdm632` branch **halium-10.0** (= 4.9.218,
  matches the running kernel; NOT `ubuntutouch`/4.9.112 nor `halium-13`/4.9.337 — the
  4.9.337 tree builds but **won't boot UT**: structural drift, both clang-19 and gcc-11
  hung identically pre-USB, no A/B fallback). Host toolchain
  `gcc-11-aarch64-linux-gnu`+`binutils`; `CC=aarch64-linux-gnu-gcc-11` (gcc-4.9 too old,
  clang-19 miscompiles→hang, gcc-11 clean), `CROSS_COMPILE=aarch64-linux-gnu-`,
  `KCFLAGS="-fcommon -Wno-error=incompatible-pointer-types
  -Wno-error=implicit-function-declaration"`, disable `CC_STACKPROTECTOR` (gcc-11 arm64
  guard mismatch fails the compiler-check), `DEBUG_INFO` OFF (else the vmlinux link OOMs
  14 GB+swap), symlink `python`→python3 **and** rewrite `scripts/gcc-wrapper.py` to a py3
  passthrough (`sys.exit(subprocess.call(sys.argv[1:]))`), and use **GNU make 4.3** (make
  4.4 breaks the audio techpack: "prerequisites cannot be defined in recipes" — build
  make-4.3 from ftp.gnu.org). Target `Image.gz`, then repack as above. Result: boots
  `4.9.218-perf-ubuntutouch+`, `/dev/mem` live, framer works (tasha-slim-pgd/ifd
  enumerated, snd-card present). UT is Ubuntu not Android: `adb push` to `/data` fails,
  use `adb shell 'cat > /home/phablet/x'`; UT has python3.
