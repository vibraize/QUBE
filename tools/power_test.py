"""
tools/power_test.py - measure what the panels draw, for the power limit in config.py.

    sudo systemctl stop qube              # if the boot service is running, it has the panels
    sudo python3 tools/power_test.py      # lights face 0
    sudo python3 tools/power_test.py --face 2

Lights ONE panel, one colour at a time, in five steps of 20 seconds each, then round
again (n = next step now, q = quit):
    dark    nothing lit: what the panels on that port draw while doing nothing
    red     the whole panel full red
    green   the whole panel full green
    blue    the whole panel full blue
    white   the whole panel white at level 0.7, as a check (see below)
For each step, read the watts on the meter for the USB-C port feeding that panel (the
power bank's display, or an inline USB-C meter). Switch the fans off while measuring, or
their draw ends up in every reading.

Then in config.py:
    PANEL_FULL_WATTS = (red - dark, green - dark, blue - dark)
    LED_WATTS_PER_SUPPLY = 15 - dark - fans - a margin of 1-2 W
and run this again: the white step prints what config.py now expects, and its reading
minus dark should come out close. If it's far off, measure again before trusting the limit.

Measure with all the panels chained, the way QUBE runs, and again after changing
gpio_slowdown, pwm_bits or the number of panels. The LED library clocks the next data in
while the LEDs are lit, so those settings change how long the LEDs are lit at full.

This is the one tool that skips MASTER_BRIGHTNESS and the power limit. That's why it
lights one colour on one panel at a time: full white adds all three colours together.
"""
import argparse
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import config  # noqa: E402
from controls import KeyReader, key_to_command  # noqa: E402
from display import create_display, led_on_time  # noqa: E402
from layout import CubeLayout  # noqa: E402

WHITE_CHECK_LEVEL = 0.7    # lit about 41% of the time: enough to read, well within one port
STEPS = [("dark", ()), ("red", (0,)), ("green", (1,)), ("blue", (2,)), ("white", (0, 1, 2))]


def describe(step, face):
    """What a step lights, and the watts config.py expects above the dark reading."""
    name, channels = STEPS[step]
    title = f"Step {step + 1} of {len(STEPS)} - {name}"
    if not channels:
        return f"{title}: nothing lit. This reading is the dark draw."
    level = WHITE_CHECK_LEVEL if name == "white" else 1.0
    on_time = float(led_on_time(level, config.MATRIX_OPTIONS.get("brightness", 100)))
    watts = sum(config.PANEL_FULL_WATTS[c] for c in channels) * on_time
    if name == "white":
        return (f"{title}: face {face} white at {level} (lit {on_time:.0%} of the time). "
                f"config.py expects dark + {watts:.1f} W.")
    return f"{title}: face {face} full {name}. config.py expects dark + {watts:.1f} W."


def main():
    parser = argparse.ArgumentParser(description="Measure the panels' power, one colour at a time.")
    parser.add_argument("--face", type=int, default=0, help="the face (panel) to light, 0-3")
    parser.add_argument("--seconds", type=float, default=20.0, help="time per step")
    parser.add_argument("--display", default="matrix", choices=["web", "matrix", "none"])
    parser.add_argument("--chain", type=int,
                        help="panels chained right now (overrides MATRIX_OPTIONS['chain_length'])")
    args = parser.parse_args()

    if args.chain:
        config.MATRIX_OPTIONS = dict(config.MATRIX_OPTIONS, chain_length=args.chain)
    layout = CubeLayout(config.FACE_SIZE, config.NUM_FACES)
    if not 0 <= args.face < layout.faces:
        parser.error(f"--face has to be 0-{layout.faces - 1}")
    display = create_display(args.display, layout, config)
    keys = KeyReader()
    print(f"Read the watts on the meter for the port feeding face {args.face} at each step. "
          f"Fans off. n = next step, q = quit.")

    step, step_start = 0, time.monotonic()
    print(describe(step, args.face))
    try:
        while True:
            now = time.monotonic()
            commands = [key_to_command(k) for k in keys.read_keys()] + display.poll_commands()
            if "quit" in commands:
                break
            if "next" in commands or now - step_start >= args.seconds:
                step = (step + 1) % len(STEPS)
                step_start = now
                print(describe(step, args.face))

            name, channels = STEPS[step]
            frame = layout.new_canvas()
            face = layout.face_view(frame, args.face)
            for channel in channels:
                face[..., channel] = WHITE_CHECK_LEVEL if name == "white" else 1.0
            display.show(frame, {"mode": "power test: " + name, "bass": 0, "mid": 0, "high": 0,
                                 "beat": 0, "fps": 20, "volume_db": 0, "silent": True})
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        keys.close()
        display.close()


if __name__ == "__main__":
    main()
