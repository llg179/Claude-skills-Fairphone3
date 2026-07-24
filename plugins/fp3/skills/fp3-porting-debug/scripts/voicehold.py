#!/usr/bin/env python3
# Open both playback+capture of the q6voice VoiceMMode1 PCM (hw:0,4) and HOLD
# them open without transferring data. The Gerhold q6voice driver starts the
# CS-voice DSP session only when BOTH substreams are open (started==3); it has
# no copy op, so we must NOT read/write. Hold until SIGTERM, then close (which
# stops the voice session).
import ctypes, sys, time, signal

asound = ctypes.CDLL("libasound.so.2")
SND_PCM_STREAM_PLAYBACK = 0
SND_PCM_STREAM_CAPTURE  = 1
SND_PCM_FORMAT_S16_LE   = 2
SND_PCM_ACCESS_RW_INTERLEAVED = 3

dev = sys.argv[1] if len(sys.argv) > 1 else "hw:0,4"

def opn(stream, label):
    pcm = ctypes.c_void_p()
    r = asound.snd_pcm_open(ctypes.byref(pcm), dev.encode(), stream, 0)
    if r < 0:
        print(f"{label}: snd_pcm_open failed: {r}", flush=True); return None
    # configure (open already triggered the DAI .startup -> q6voice_start)
    r = asound.snd_pcm_set_params(pcm, SND_PCM_FORMAT_S16_LE,
                                  SND_PCM_ACCESS_RW_INTERLEAVED,
                                  1, 8000, 1, 200000)
    if r < 0:
        print(f"{label}: set_params warn: {r}", flush=True)
    print(f"{label}: open OK", flush=True)
    return pcm

p = opn(SND_PCM_STREAM_PLAYBACK, "playback")
c = opn(SND_PCM_STREAM_CAPTURE,  "capture")
if not p or not c:
    print("FAILED to open both directions", flush=True); sys.exit(1)
# trigger RUNNING without writing (q6voice has no trigger op, but harmless)
asound.snd_pcm_start(c)
print("VOICE PCM HELD (both dirs open) -- DSP session should be active", flush=True)

run = {"go": True}
signal.signal(signal.SIGTERM, lambda *a: run.__setitem__("go", False))
signal.signal(signal.SIGINT,  lambda *a: run.__setitem__("go", False))
while run["go"]:
    time.sleep(0.5)
asound.snd_pcm_close(p); asound.snd_pcm_close(c)
print("closed", flush=True)
