#!/usr/bin/env python3
"""What stride does the GPU itself require for a linear R8 buffer?

libcamera imports the packed Bayer frame as DRM_FORMAT_R8 and unpacks it in the
shader, so the question that decides whether a zero-copy import is possible is
what pitch alignment this GPU wants for a linear R8 surface. Asking Mesa to
allocate one and reporting the stride it picks answers that without needing the
camera, the compositor, or a kernel change: the allocator and the importer share
the same layout code.

Widths tested are the two sensor modes' packed line lengths, and for each the
stride camss grants against the stride Mesa wants.
"""
import ctypes as C
import os

gbm = C.CDLL("libgbm.so.1")
gbm.gbm_create_device.restype = C.c_void_p
gbm.gbm_create_device.argtypes = [C.c_int]
gbm.gbm_bo_create.restype = C.c_void_p
gbm.gbm_bo_create.argtypes = [C.c_void_p, C.c_uint, C.c_uint, C.c_uint, C.c_uint]
gbm.gbm_bo_get_stride.restype = C.c_uint
gbm.gbm_bo_get_stride.argtypes = [C.c_void_p]
gbm.gbm_bo_destroy.argtypes = [C.c_void_p]
gbm.gbm_device_get_backend_name.restype = C.c_char_p
gbm.gbm_device_get_backend_name.argtypes = [C.c_void_p]


def fourcc(s):
    return s[0] | (s[1] << 8) | (s[2] << 16) | (s[3] << 24)


GBM_FORMAT_R8 = fourcc(b"R8  ")
GBM_BO_USE_LINEAR = 1 << 4
GBM_BO_USE_RENDERING = 1 << 2

fd = os.open("/dev/dri/renderD128", os.O_RDWR)
dev = gbm.gbm_create_device(fd)
if not dev:
    raise SystemExit("gbm_create_device failed")
print("gbm backend:", gbm.gbm_device_get_backend_name(dev).decode())

# (packed line length, what camss hands out, sensor mode it belongs to)
cases = [
    (2400, "1920x1080 mode"),
    (5040, "4032x3024 mode"),
]

print()
print("%-14s %-16s %-10s %-10s %s" % ("sensor mode", "packed line", "camss",
                                      "GPU wants", "verdict"))
for width, mode in cases:
    bo = gbm.gbm_bo_create(dev, width, 256, GBM_FORMAT_R8,
                           GBM_BO_USE_LINEAR | GBM_BO_USE_RENDERING)
    if not bo:
        print("%-14s %-16s allocation failed" % (mode, width))
        continue
    stride = gbm.gbm_bo_get_stride(bo)
    gbm.gbm_bo_destroy(bo)
    verdict = "matches" if stride == width else "PADDED by %d" % (stride - width)
    print("%-14s %-16d %-10d %-10d %s" % (mode, width, width, stride, verdict))

# Where the boundary is, stated as a number rather than inferred from two points.
print()
prev = None
align = None
for w in range(4096, 4096 + 130):
    bo = gbm.gbm_bo_create(dev, w, 8, GBM_FORMAT_R8,
                           GBM_BO_USE_LINEAR | GBM_BO_USE_RENDERING)
    if not bo:
        continue
    s = gbm.gbm_bo_get_stride(bo)
    gbm.gbm_bo_destroy(bo)
    if prev is not None and s != prev:
        align = s - prev
        print("stride steps from %d to %d at width %d -> alignment %d bytes"
              % (prev, s, w, align))
        break
    prev = s
if align:
    for width, mode in cases:
        need = -(-width // align) * align
        print("  %s: %d -> %d (%s)" % (mode, width, need,
              "already aligned" if need == width else "needs %d more" % (need - width)))
