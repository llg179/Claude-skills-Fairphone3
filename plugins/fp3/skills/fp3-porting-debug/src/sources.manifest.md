# fp3-porting-debug — source trees & build system (portable manifest)

> ⚠️ **AI-generated.** This page — and the code, device tree and tooling it
> describes — was written by Claude (Opus 5) working under the direction of
> Lajosházi, László Gergely, who reviewed every change and made or reviewed
> every measurement it rests on. Kernel commits carry `Co-authored-by: Claude`;
> anything prepared for the LKML carries `Assisted-by:` instead and never a
> `Signed-off-by` from the assistant, since only a human can certify the DCO.

The symlinks in this `src/` dir point at the working checkouts. **Portability rule
(the skill owns this):** if a symlink's target is missing (fresh machine), clone it from the
URL+branch below and re-point the symlink here — never hardcode an absolute path elsewhere.

| link (`src/<name>`) | role | git URL | branch | notes |
|---|---|---|---|---|
| `linux-fp3` | mainline / PAS kernel (SUT) | `https://github.com/msm8953-mainline/linux.git` | working branch `f0-clean-baseline` (local; base = fork default) | commits are **local**, never push |
| `ubports-fp3-kernel` | downstream / PIL kernel (oracle) | `https://gitlab.com/ubports/porting/community-ports/android10/fairphone/android_kernel_fairphone_sdm632.git` | `halium-10.0` (= 4.9.218; default protected branch; tip `12d9b944c` SQUASHFS_LZO). ☠️ NOT `ubuntutouch` (4.9.112) nor `halium-13` (4.9.337, builds but won't boot UT) | oracle DEVMEM kernel source — see `references/devmem-oracle-kernel.md` |
| `pmbootstrap` (or `pmos-root`) | build system | `https://gitlab.postmarketos.org/postmarketOS/pmbootstrap.git` | default | invoked via wrapper `$FP3_PMOS/pmb` (`cd $FP3_PMOS && ./pmb build --src src/linux-fp3 …`) |

## Bootstrap (create-if-absent)
```bash
# example: recreate the oracle kernel checkout on a fresh machine
git clone -b halium-10.0 \
  https://gitlab.com/ubports/porting/community-ports/android10/fairphone/android_kernel_fairphone_sdm632.git \
  /path/to/ubports-fp3-kernel
ln -sfn /path/to/ubports-fp3-kernel  "$(dirname "$0")/ubports-fp3-kernel"
```
Repeat per row. The build wrapper `pmb` lives at the pmbootstrap checkout root.
