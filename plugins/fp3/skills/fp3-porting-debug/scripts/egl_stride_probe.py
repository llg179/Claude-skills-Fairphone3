#!/usr/bin/env python3
"""Does Mesa's dmabuf importer reject the stride camss grants, or accept it?

The allocator's opinion is not the importer's. gbm_bo_create told us this GPU
pads a linear R8 surface up to a 64-byte pitch, and it was tempting to read
that as "an unpadded pitch cannot be imported" - but the only thing that
settles it is asking the importer.

So allocate one buffer generously through GBM, export it, and import the same
fd several times while claiming different pitches. The allocation is larger
than every pitch claimed, so nothing here reads out of bounds; the only
variable is the number handed to EGL_DMA_BUF_PLANE0_PITCH_EXT.
"""
import ctypes as C
import os

EGL = C.CDLL("libEGL.so.1")
gbm = C.CDLL("libgbm.so.1")

# Without this the returned function pointer is truncated to 32 bits and the
# first call through it lands nowhere.
EGL.eglGetProcAddress.restype = C.c_void_p
EGL.eglGetProcAddress.argtypes = [C.c_char_p]

for f, res, args in (
    ("gbm_create_device", C.c_void_p, [C.c_int]),
    ("gbm_bo_create", C.c_void_p, [C.c_void_p, C.c_uint, C.c_uint, C.c_uint, C.c_uint]),
    ("gbm_bo_get_stride", C.c_uint, [C.c_void_p]),
    ("gbm_bo_get_fd", C.c_int, [C.c_void_p]),
):
    fn = getattr(gbm, f); fn.restype = res; fn.argtypes = args


def fourcc(s):
    return s[0] | (s[1] << 8) | (s[2] << 16) | (s[3] << 24)


R8 = fourcc(b"R8  ")
GBM_BO_USE_LINEAR, GBM_BO_USE_RENDERING = 1 << 4, 1 << 2

EGL_NONE, EGL_NO_CONTEXT = 0x3038, C.c_void_p(0)
EGL_LINUX_DMA_BUF_EXT = 0x3270
EGL_WIDTH, EGL_HEIGHT = 0x3057, 0x3056
EGL_LINUX_DRM_FOURCC_EXT = 0x3271
EGL_DMA_BUF_PLANE0_FD_EXT = 0x3272
EGL_DMA_BUF_PLANE0_OFFSET_EXT = 0x3273
EGL_DMA_BUF_PLANE0_PITCH_EXT = 0x3274
EGL_PLATFORM_SURFACELESS_MESA = 0x31DD

GetPlatformDisplay = C.CFUNCTYPE(C.c_void_p, C.c_uint, C.c_void_p, C.c_void_p)(
    EGL.eglGetProcAddress(b"eglGetPlatformDisplayEXT"))
CreateImage = C.CFUNCTYPE(C.c_void_p, C.c_void_p, C.c_void_p, C.c_uint,
                          C.c_void_p, C.POINTER(C.c_int))(
    EGL.eglGetProcAddress(b"eglCreateImageKHR"))
DestroyImage = C.CFUNCTYPE(C.c_uint, C.c_void_p, C.c_void_p)(
    EGL.eglGetProcAddress(b"eglDestroyImageKHR"))

dpy = GetPlatformDisplay(EGL_PLATFORM_SURFACELESS_MESA, None, None)
maj, mnr = C.c_int(), C.c_int()
if not EGL.eglInitialize(C.c_void_p(dpy), C.byref(maj), C.byref(mnr)):
    raise SystemExit("eglInitialize failed")
print("EGL %d.%d" % (maj.value, mnr.value))

HEIGHT = 256
drm = os.open("/dev/dri/renderD128", os.O_RDWR)
dev = gbm.gbm_create_device(drm)
# Allocate wider than any pitch tested below, so every import stays in bounds.
bo = gbm.gbm_bo_create(dev, 6144, HEIGHT, R8,
                       GBM_BO_USE_LINEAR | GBM_BO_USE_RENDERING)
if not bo:
    raise SystemExit("gbm_bo_create failed")
alloc_stride = gbm.gbm_bo_get_stride(bo)
fd = gbm.gbm_bo_get_fd(bo)
print("allocated pitch %d, exported fd %d" % (alloc_stride, fd))
print()

cases = [
    (2400, "1920 mode, packed - what camss grants"),
    (2432, "1920 mode, rounded up to 64"),
    (2560, "1920 mode, rounded up to 256 - what the ISP asks for"),
    (5040, "4032 mode, packed - what camss grants"),
    (5056, "4032 mode, rounded up to 64"),
    (5120, "4032 mode, rounded up to 256 - what the ISP asks for"),
]
for pitch, label in cases:
    attrs = (C.c_int * 13)(
        EGL_WIDTH, pitch,
        EGL_HEIGHT, HEIGHT,
        EGL_LINUX_DRM_FOURCC_EXT, R8,
        EGL_DMA_BUF_PLANE0_FD_EXT, fd,
        EGL_DMA_BUF_PLANE0_OFFSET_EXT, 0,
        EGL_DMA_BUF_PLANE0_PITCH_EXT, pitch,
        EGL_NONE)
    img = CreateImage(C.c_void_p(dpy), EGL_NO_CONTEXT, EGL_LINUX_DMA_BUF_EXT,
                      None, attrs)
    err = EGL.eglGetError()
    print("pitch %-5d %-52s %s" % (
        pitch, label,
        "IMPORT OK" if img else "FAILED (eglGetError 0x%x)" % err))
    if img:
        DestroyImage(C.c_void_p(dpy), img)
