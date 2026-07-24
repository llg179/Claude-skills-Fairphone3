#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# SN97 reader (folyt.97): resolve the runtime-dispatched physical framer-clock poke leaf.
import mmap, struct
SMEM_PA=0x86300000; WIN=0x40000; STASH=0x2ab0
with open("/dev/mem","rb") as f:
    m=mmap.mmap(f.fileno(),WIN,mmap.MAP_SHARED,mmap.PROT_READ,offset=SMEM_PA)
    buf=m.read(WIN); m.close()
magic=buf[STASH:STASH+4]
print("magic         :", magic, "->", "SN97 OK" if magic==b"SN97" else "NOT PRESENT (cave didn't run / stale)")
if magic!=b"SN97": raise SystemExit
names=[("counter (invocations)",0x04),
       ("handle (ctx+0xe18)",0x08),
       ("subobj (handle+0x10)",0x0c),
       ("classptr (subobj+0x00)",0x10),
       ("rodata vtable (subobj+0x14)",0x14),
       ("drivernode (subobj+0x04)",0x18),
       (">>> RESOLVED_FN (node+0x04) = THE LEAF",0x1c),
       ("node_class (node+0x00)",0x20),
       ("handle+0x48 (=f019eb40?)",0x24),
       ("handle+0x44 (status bit0)",0x28),
       ("handle+0x38",0x2c)]
for nm,off in names:
    v=struct.unpack_from("<I",buf,STASH+off)[0]
    print(f"  +0x{off:02x} {nm:38s} = {v:#010x}")
