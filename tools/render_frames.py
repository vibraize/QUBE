"""
tools/render_frames.py - render visual modes to PNG images using the fake audio.

Handy for checking what a mode looks like without a mic or panels:
    python3 tools/render_frames.py                          # every mode, 6 seconds each
    python3 tools/render_frames.py --mode river --seconds 10 --every 0.5
    python3 tools/render_frames.py --start 31               # the fake song's quiet breakdown

Writes one PNG per mode into renders/. Each row of the image is a snapshot of all
four faces (LEDs drawn as dots, faces separated by a gap). Brightness settings
from config.py are NOT applied, so the colors are easy to judge.
No extra libraries needed: the PNG file is written by hand.
"""
import argparse
import os
import struct
import sys
import time
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402

import config  # noqa: E402
from audio_analysis import AudioAnalyzer  # noqa: E402
from audio_input import FakeAudioInput  # noqa: E402
from layout import CubeLayout  # noqa: E402
from visuals import EXTRA_MODES, MODES, find_mode  # noqa: E402

FPS = 40


def write_png(path, rgb):
    """Save a uint8 array shaped (height, width, 3) as a PNG file."""
    height, width, _ = rgb.shape
    raw = b"".join(b"\x00" + rgb[y].tobytes() for y in range(height))

    def chunk(kind, data):
        crc = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)   # 8-bit RGB
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
                + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def led_snapshot(frame, layout, scale, gap=6):
    """Upscale a frame so each pixel becomes a round LED dot, with gaps between faces."""
    rgb = (np.clip(frame, 0.0, 1.0) * 255).astype(np.uint8)
    yy, xx = np.mgrid[0:scale, 0:scale]
    center = (scale - 1) / 2.0
    dot = ((xx - center) ** 2 + (yy - center) ** 2 <= (scale * 0.45) ** 2).astype(np.uint8)
    faces = []
    for i in range(layout.faces):
        face = layout.face_view(rgb, i)
        big = np.repeat(np.repeat(face, scale, axis=0), scale, axis=1)
        big *= np.tile(dot, (layout.face, layout.face))[..., None]
        faces.append(big)
        if i < layout.faces - 1:
            faces.append(np.full((big.shape[0], gap, 3), 40, dtype=np.uint8))
    return np.concatenate(faces, axis=1)


def render_mode(mode_class, layout, args):
    fake = FakeAudioInput(48000, 4096)
    clock = {"t": args.start}
    fake.clock = lambda: clock["t"]          # drive the fake song from our own clock
    analyzer = AudioAnalyzer(48000, config)
    mode = mode_class(layout)
    mode.start()

    dt = 1.0 / FPS
    frames = int(args.seconds * FPS)
    snapshots, times = [], []
    next_shot = args.every
    render_seconds = 0.0
    for i in range(frames):
        clock["t"] = args.start + i * dt
        audio = analyzer.process(fake.get_samples(), dt)
        started = time.perf_counter()
        frame = mode.step(audio, dt)
        render_seconds += time.perf_counter() - started
        if (i + 1) * dt >= next_shot - 1e-9:
            if snapshots:
                snapshots.append(np.full((args.scale * 2, snapshots[0].shape[1], 3), 25, dtype=np.uint8))
            snapshots.append(led_snapshot(frame, layout, args.scale))
            times.append(round(clock["t"], 2))
            next_shot += args.every

    name = mode_class.name.lower().replace(" ", "_")
    path = os.path.join(args.out, name + ".png")
    write_png(path, np.concatenate(snapshots, axis=0))
    print(f"{mode_class.name}: {path}")
    print(f"    render time {render_seconds / frames * 1000:.2f} ms/frame on this computer; "
          f"snapshots at t = {times}")


def main():
    parser = argparse.ArgumentParser(description="Render visual modes to PNG using fake audio.")
    parser.add_argument("--mode", help="one mode (number or part of its name); default: all")
    parser.add_argument("--seconds", type=float, default=6.0, help="how long to simulate per mode")
    parser.add_argument("--every", type=float, default=1.0, help="seconds between snapshots")
    parser.add_argument("--start", type=float, default=0.0,
                        help="start time in the fake song (its quiet breakdown starts near 31 s)")
    parser.add_argument("--scale", type=int, default=6, help="screen pixels per LED")
    parser.add_argument("--out", default=os.path.join(ROOT, "renders"), help="output folder")
    args = parser.parse_args()

    layout = CubeLayout(config.FACE_SIZE, config.NUM_FACES)
    modes = [find_mode(args.mode)[0]] if args.mode else MODES + EXTRA_MODES
    os.makedirs(args.out, exist_ok=True)
    for mode_class in modes:
        render_mode(mode_class, layout, args)


if __name__ == "__main__":
    main()
