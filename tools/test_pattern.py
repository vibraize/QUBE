"""
tools/test_pattern.py - test patterns for bringing up the panels.

    sudo python3 tools/test_pattern.py                  # on the Pi: send to the panels
    sudo python3 tools/test_pattern.py --chain 3        # while fewer panels are wired up
    python3 tools/test_pattern.py --display web         # preview in a browser

Use this after the panels light up, to work out FACE_ORDER, FACE_ROTATION, FACE_MIRROR
and PANEL_COLUMN_OFFSET in config.py from what you actually see.

Patterns advance every 8 seconds, or press n in the terminal:
  1. faces  - each face its own color, a border, its number (1-4) and an arrow
              pointing up. Checks panel order and orientation (FACE_ORDER / ROTATION).
  2. bands  - the horizontal bands (8 rows each = the RD1..RD5 data groups) in
              different colors with their numbers. Shows if band order or row
              addressing is off.
  3. colors - red, green, blue and white stripes on every face. Checks color wiring.
  4. sweep  - one lit column and one lit row moving across everything.
              Finds dead pixels, stuck rows and gaps.
"""
import argparse
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402

import config  # noqa: E402
from controls import KeyReader  # noqa: E402
from display import PowerLimit, create_display  # noqa: E402
from layout import CubeLayout  # noqa: E402

# Tiny 3x5 pixel digits: "1" = lit, "0" = off
DIGITS = {
    "1": ["010", "110", "010", "010", "111"],
    "2": ["111", "001", "111", "100", "111"],
    "3": ["111", "001", "111", "001", "111"],
    "4": ["101", "101", "111", "001", "001"],
    "5": ["111", "100", "111", "001", "111"],
    "6": ["111", "100", "111", "101", "111"],
    "7": ["111", "001", "001", "001", "001"],
    "8": ["111", "101", "111", "101", "111"],
}
PALETTE = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.3, 1.0), (1.0, 1.0, 0.0), (1.0, 0.0, 1.0),
           (0.0, 1.0, 1.0), (1.0, 0.5, 0.0), (1.0, 1.0, 1.0)]


def draw_digit(img, digit, x, y, scale, color=(1.0, 1.0, 1.0)):
    for row, bits in enumerate(DIGITS[digit]):
        for col, bit in enumerate(bits):
            if bit == "1":
                img[y + row * scale:y + (row + 1) * scale, x + col * scale:x + (col + 1) * scale] = color


def faces_pattern(layout, t):
    frame = layout.new_canvas()
    size = layout.face
    scale = max(1, size // 10)
    for i in range(layout.faces):
        face = layout.face_view(frame, i)
        color = np.array(PALETTE[i % len(PALETTE)], dtype=np.float32)
        face[:] = color * 0.12
        face[0, :] = face[-1, :] = color
        face[:, 0] = face[:, -1] = color
        draw_digit(face, str(i + 1 if i < 8 else 8), size // 2 - (3 * scale) // 2, size // 2 - scale, scale)
        tip = size // 2 - 3 * scale                   # arrow pointing up, above the number
        for step in range(scale * 2):
            face[max(tip - scale * 2 + step, 1), size // 2 - step:size // 2 + step + 1] = (1.0, 1.0, 1.0)
    return frame


def bands_pattern(layout, t):
    frame = layout.new_canvas()
    rows_per_band = int(config.MATRIX_OPTIONS.get("rows", 8))
    for band in range(layout.height // rows_per_band):
        top = band * rows_per_band
        color = np.array(PALETTE[band % len(PALETTE)], dtype=np.float32)
        frame[top:top + rows_per_band] = color * 0.25
        frame[top] = color                            # brighter first row of each band
        for i in range(layout.faces):
            x = i * layout.face + 2
            if rows_per_band >= 6:
                draw_digit(frame, str(min(band + 1, 8)), x, top + (rows_per_band - 5) // 2, 1)
    return frame


def colors_pattern(layout, t):
    frame = layout.new_canvas()
    stripe = layout.face // 4
    for i in range(layout.faces):
        face = layout.face_view(frame, i)
        for n, color in enumerate([(1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 1)]):
            face[:, n * stripe:(n + 1) * stripe] = color
    return frame


def sweep_pattern(layout, t):
    frame = layout.new_canvas()
    x = int(t * 20) % layout.width                  # 20 columns per second
    y = int(t * 5) % layout.height                  # 5 rows per second
    frame[:, x] = (1.0, 1.0, 1.0)
    frame[y, :] = (0.0, 0.6, 1.0)
    return frame


PATTERNS = [("faces", faces_pattern), ("bands", bands_pattern),
            ("colors", colors_pattern), ("sweep", sweep_pattern)]


def main():
    parser = argparse.ArgumentParser(description="LED panel test patterns")
    parser.add_argument("--display", default="matrix", choices=["web", "matrix", "none"])
    parser.add_argument("--seconds", type=float, default=8.0, help="time per pattern")
    parser.add_argument("--chain", type=int,
                        help="panels chained right now (overrides MATRIX_OPTIONS['chain_length'])")
    args = parser.parse_args()

    if args.chain:
        config.MATRIX_OPTIONS = dict(config.MATRIX_OPTIONS, chain_length=args.chain)
    layout = CubeLayout(config.FACE_SIZE, config.NUM_FACES)
    power = PowerLimit(config, layout)
    display = create_display(args.display, layout, config)
    keys = KeyReader()
    index, pattern_start = 0, time.monotonic()
    print(f"Pattern: {PATTERNS[index][0]}  (n = next, q = quit)")
    try:
        while True:
            now = time.monotonic()
            if any(k in ("n", "N", " ") for k in keys.read_keys()) or now - pattern_start > args.seconds:
                index = (index + 1) % len(PATTERNS)
                pattern_start = now
                print(f"Pattern: {PATTERNS[index][0]}")
            name, make = PATTERNS[index]
            frame = make(layout, now - pattern_start)
            if display.wants_brightness:        # same brightness and power limit as the show
                frame = power.apply(frame, config.MASTER_BRIGHTNESS)
            display.show(frame, {"mode": "test: " + name, "bass": 0, "mid": 0, "high": 0,
                                 "beat": 0, "fps": 30, "volume_db": 0, "silent": True})
            if "quit" in display.poll_commands():
                break
            time.sleep(1 / 30)
    except KeyboardInterrupt:
        pass
    finally:
        keys.close()
        display.close()


if __name__ == "__main__":
    main()
