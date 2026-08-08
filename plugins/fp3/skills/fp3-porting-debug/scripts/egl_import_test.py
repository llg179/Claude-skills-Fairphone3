#!/usr/bin/env python3
"""Ask the GPU, not the log, whether the raw Bayer input buffer is importable.

libcamera's software ISP imports the packed Bayer frame as a single-channel
DRM_FORMAT_R8 texture and unpacks it in the shader. Two things have to hold for
that to work, and the camss stride complaint only implicates the second:

  1. Mesa must accept R8 for dmabuf import at all.
  2. It must accept it at the stride the buffer actually has.

This tries both, on a real dma-heap buffer, at the stride camss grants (5040)
and the stride the software ISP asks for (5120). Nothing here needs the camera,
so it can run while wireplumber holds it.
"""
import ctypes as C
import os
import struct
import fcntl

EGL = C.CDLL("libEGL.so.1")
GL = C.CDLL("libGLESv2.so.2")


def fourcc(s):
    return s[0] | (s[1] << 8) | (s[2] << 16) | (s[3] << 24)


def unfourcc(v):
    return "".join(chr((v >> (8 * i)) & 0xFF) for i in range(4))


DRM_FORMAT_R8 = fourcc(b"R8  ")
DRM_FORMAT_ARGB8888 = fourcc(b"AR24")

EGL_DEFAULT_DISPLAY = C.c_void_p(0)
EGL_NO_CONTEXT = C.c_void_p(0)
EGL_NONE = 0x3038
EGL_LINUX_DMA_BUF_EXT = 0x3270
EGL_WIDTH, EGL_HEIGHT = 0x3057, 0x3056
EGL_LINUX_DRM_FOURCC_EXT = 0x3271
EGL_DMA_BUF_PLANE0_FD_EXT = 0x3272
EGL_DMA_BUF_PLANE0_OFFSET_EXT = 0x3273
EGL_DMA_BUF_PLANE0_PITCH_EXT = 0x3274
EGL_OPENGL_ES_API = 0x30A0
EGL_CONTEXT_CLIENT_VERSION = 0x3098
EGL_SURFACE_TYPE, EGL_RENDERABLE_TYPE = 0x3033, 0x3040
EGL_OPENGL_ES2_BIT, EGL_PBUFFER_BIT = 0x0004, 0x0001

EGL.eglGetDisplay.restype = C.c_void_p
EGL.eglGetProcAddress.restype = C.c_void_p
EGL.eglCreateContext.restype = C.c_void_p
EGL.eglGetError.restype = C.c_int

# Surfaceless: the DRM master is the running compositor, and this test has no
# business taking it. Mesa's surfaceless platform gives a render-only context.
EGL_PLATFORM_SURFACELESS_MESA = 0x31DD
_gpd = EGL.eglGetProcAddress(b"eglGetPlatformDisplayEXT")
if _gpd:
    GetPlatformDisplay = C.CFUNCTYPE(C.c_void_p, C.c_uint, C.c_void_p,
                                     C.POINTER(C.c_int))(_gpd)
    dpy = C.c_void_p(GetPlatformDisplay(EGL_PLATFORM_SURFACELESS_MESA,
                                        EGL_DEFAULT_DISPLAY, None))
else:
    dpy = C.c_void_p(EGL.eglGetDisplay(EGL_DEFAULT_DISPLAY))
major, minor = C.c_int(), C.c_int()
if not EGL.eglInitialize(dpy, C.byref(major), C.byref(minor)):
    raise SystemExit("eglInitialize failed: 0x%x" % EGL.eglGetError())
print("EGL %d.%d" % (major.value, minor.value))

EGL.eglBindAPI(EGL_OPENGL_ES_API)

cfg_attrs = (C.c_int * 7)(EGL_SURFACE_TYPE, EGL_PBUFFER_BIT,
                          EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT,
                          EGL_NONE, 0, 0)
cfg = C.c_void_p()
n = C.c_int()
EGL.eglChooseConfig(dpy, cfg_attrs, C.byref(cfg), 1, C.byref(n))

ctx_attrs = (C.c_int * 3)(EGL_CONTEXT_CLIENT_VERSION, 2, EGL_NONE)
ctx = C.c_void_p(EGL.eglCreateContext(dpy, cfg, EGL_NO_CONTEXT, ctx_attrs))
if not ctx:
    raise SystemExit("eglCreateContext failed: 0x%x" % EGL.eglGetError())
EGL.eglMakeCurrent(dpy, None, None, ctx)

GL.glGetString.restype = C.c_char_p
print("GL_RENDERER:", GL.glGetString(0x1F01).decode())

# --- 1. Which formats will Mesa import at all? -------------------------------
addr = EGL.eglGetProcAddress(b"eglQueryDmaBufFormatsEXT")
if not addr:
    print("eglQueryDmaBufFormatsEXT: MISSING - cannot enumerate")
else:
    QueryFormats = C.CFUNCTYPE(C.c_uint, C.c_void_p, C.c_int,
                               C.POINTER(C.c_int), C.POINTER(C.c_int))(addr)
    cnt = C.c_int()
    QueryFormats(dpy, 0, None, C.byref(cnt))
    fmts = (C.c_int * cnt.value)()
    QueryFormats(dpy, cnt.value, fmts, C.byref(cnt))
    have = list(fmts)
    print("importable formats: %d" % len(have))
    for want, name in ((DRM_FORMAT_R8, "R8  "), (DRM_FORMAT_ARGB8888, "AR24")):
        print("  %s (0x%08x): %s" % (name, want,
              "SUPPORTED" if want in have else "NOT in the list"))

# --- 2. Does an actual import succeed, and does the stride decide it? --------
HEAP = next((h for h in ("/dev/dma_heap/system",
                         "/dev/dma_heap/default_cma_region",
                         "/dev/dma_heap/reserved")
             if os.path.exists(h)), None)
if HEAP is None:
    raise SystemExit("no usable dma_heap - cannot allocate a test buffer")
print("heap:", HEAP)

DMA_HEAP_IOCTL_ALLOC = 0xC0184800  # _IOWR('H', 0, struct dma_heap_allocation_data)


def heap_alloc(size):
    fd = os.open(HEAP, os.O_RDWR)
    try:
        buf = bytearray(struct.pack("QIIQ", size, os.O_RDWR, 0, 0))
        fcntl.ioctl(fd, DMA_HEAP_IOCTL_ALLOC, buf, True)
        return struct.unpack("QIIQ", bytes(buf))[1]
    finally:
        os.close(fd)


CreateImage = C.CFUNCTYPE(C.c_void_p, C.c_void_p, C.c_void_p, C.c_uint,
                          C.c_void_p, C.POINTER(C.c_int))(
    EGL.eglGetProcAddress(b"eglCreateImageKHR"))
DestroyImage = C.CFUNCTYPE(C.c_uint, C.c_void_p, C.c_void_p)(
    EGL.eglGetProcAddress(b"eglDestroyImageKHR"))

# The full-resolution sensor mode: 4032 wide, 10-bit MIPI packed.
WIDTH_BYTES, HEIGHT = 5040, 256
for stride, label in ((5040, "5040  what camss grants (4032 x 1.25)"),
                      (5120, "5120  what the software ISP asks for")):
    fd = heap_alloc(stride * HEIGHT)
    attrs = (C.c_int * 13)(
        EGL_WIDTH, WIDTH_BYTES,
        EGL_HEIGHT, HEIGHT,
        EGL_LINUX_DRM_FOURCC_EXT, DRM_FORMAT_R8,
        EGL_DMA_BUF_PLANE0_FD_EXT, fd,
        EGL_DMA_BUF_PLANE0_OFFSET_EXT, 0,
        EGL_DMA_BUF_PLANE0_PITCH_EXT, stride,
        EGL_NONE)
    img = CreateImage(dpy, EGL_NO_CONTEXT, EGL_LINUX_DMA_BUF_EXT, None, attrs)
    err = EGL.eglGetError()
    print("stride %s -> %s%s" % (
        label,
        "IMPORT OK" if img else "FAILED",
        "" if img else " (eglGetError 0x%x)" % err))
    if img:
        DestroyImage(dpy, img)
    os.close(fd)
