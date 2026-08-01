#!/usr/bin/env python3
"""Ramp the lens slowly between its two extremes, for a human to watch.

The machine test measures a still frame; this one is for the eye. It walks the
full focus range in small steps so the viewfinder shows a continuous pull
rather than a jump, and prints where it is so what you see can be tied to a
position afterwards.

Run it with the camera app open. The lens subdev is a separate device node from
the video node, so setting the control does not disturb whoever is streaming.
"""
import argparse, os, subprocess, sys, time

def find_lens_subdev():
    for entry in sorted(os.listdir('/dev')):
        if not entry.startswith('v4l-subdev'):
            continue
        p = '/dev/' + entry
        try:
            out = subprocess.run(['v4l2-ctl', '-d', p, '-l'],
                                 capture_output=True, text=True, timeout=10).stdout
        except (OSError, subprocess.SubprocessError):
            continue
        if 'focus_absolute' in out:
            return p
    return None

def focus_range(sd):
    out = subprocess.run(['v4l2-ctl', '-d', sd, '-l'],
                         capture_output=True, text=True).stdout
    for line in out.splitlines():
        if 'focus_absolute' in line:
            lo = hi = None
            for f in line.split():
                if f.startswith('min='):
                    lo = int(f[4:])
                elif f.startswith('max='):
                    hi = int(f[4:])
            if lo is not None and hi is not None:
                return lo, hi
    raise SystemExit('focus_absolute has no min/max')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seconds', type=float, default=3.0,
                    help='time for one end-to-end pull (default 3)')
    ap.add_argument('--steps', type=int, default=40, help='steps per pull')
    ap.add_argument('--sweeps', type=int, default=10, help='number of pulls')
    ap.add_argument('--hold', type=float, default=1.0,
                    help='pause at each end, so the extremes are visible')
    ap.add_argument('--subdev')
    args = ap.parse_args()

    sd = args.subdev or find_lens_subdev()
    if not sd:
        raise SystemExit('no subdev exposes focus_absolute - is the driver bound?')
    lo, hi = focus_range(sd)
    dt = args.seconds / args.steps
    print('lens %s, range %d..%d, %.1fs per pull, %d pulls'
          % (sd, lo, hi, args.seconds, args.sweeps))
    print('watch the viewfinder; each line is where the lens is being told to go')
    sys.stdout.flush()

    # One long-lived v4l2-ctl per step would spend most of the time in process
    # startup, so the control is written through a single open file descriptor
    # instead - otherwise "3 seconds" is mostly exec() and the pull is jerky.
    for n in range(args.sweeps):
        for direction in (1, -1):
            a, b = (lo, hi) if direction == 1 else (hi, lo)
            print('pull %d/%d: %d -> %d' % (n + 1, args.sweeps, a, b))
            sys.stdout.flush()
            for i in range(args.steps + 1):
                pos = a + (b - a) * i // args.steps
                subprocess.run(['v4l2-ctl', '-d', sd,
                                '--set-ctrl', 'focus_absolute=%d' % pos],
                               capture_output=True)
                time.sleep(dt)
            time.sleep(args.hold)
    print('done')

if __name__ == '__main__':
    main()
