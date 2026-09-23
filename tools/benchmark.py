"""
tools/benchmark.py - how fast does each visual mode run on this computer?

    python3 tools/benchmark.py                # 10 seconds per mode
    python3 tools/benchmark.py --seconds 20

Runs every mode with the fake beat and no display, as fast as it can, and prints
the average time per frame. For 40 fps everything has to fit in 25 ms (33 ms for
30 fps). On the Pi the LED panel library also needs time and a CPU core, so leave
some headroom. Sending the frame to the panels or browser isn't included.
"""
import argparse
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402

import config  # noqa: E402
from audio_analysis import AudioAnalyzer  # noqa: E402
from audio_input import FakeAudioInput  # noqa: E402
from display import PowerLimit, to_uint8  # noqa: E402
from layout import CubeLayout, orient_for_panels  # noqa: E402
from visuals import EXTRA_MODES, MODES  # noqa: E402

SIMULATED_FPS = 40     # animations advance as if running at this frame rate


def benchmark(mode_class, layout, seconds, power):
    fake = FakeAudioInput(48000, 4096)
    clock = {"t": 0.0}
    fake.clock = lambda: clock["t"]
    analyzer = AudioAnalyzer(48000, config)
    mode = mode_class(layout)
    mode.start()
    dt = 1.0 / SIMULATED_FPS
    totals = {"analysis": 0.0, "draw": 0.0, "output": 0.0}
    frames = 0
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        clock["t"] += dt
        samples = fake.get_samples()       # not timed: making up fake music isn't part of the real loop
        t0 = time.perf_counter()
        audio = analyzer.process(samples, dt)
        t1 = time.perf_counter()
        frame = mode.step(audio, dt)
        t2 = time.perf_counter()
        out = power.apply(frame, config.MASTER_BRIGHTNESS)
        out = orient_for_panels(out, layout, config.FACE_ORDER, config.FACE_ROTATION, config.FACE_MIRROR)
        to_uint8(out)
        t3 = time.perf_counter()
        totals["analysis"] += t1 - t0
        totals["draw"] += t2 - t1
        totals["output"] += t3 - t2
        frames += 1
    return frames, {name: seconds_total / frames * 1000.0 for name, seconds_total in totals.items()}


def main():
    parser = argparse.ArgumentParser(description="Time each visual mode.")
    parser.add_argument("--seconds", type=float, default=10.0, help="seconds per mode")
    args = parser.parse_args()

    layout = CubeLayout(config.FACE_SIZE, config.NUM_FACES)
    power = PowerLimit(config, layout)
    print(f"Python {sys.version.split()[0]}, numpy {np.__version__}, {os.cpu_count()} CPU cores")
    print(f"{'mode':16}{'frames':>8}{'analysis':>10}{'draw':>8}{'output':>8}{'total':>8}   (ms per frame)")
    for mode_class in MODES + EXTRA_MODES:
        frames, ms = benchmark(mode_class, layout, args.seconds, power)
        total = sum(ms.values())
        print(f"{mode_class.name:16}{frames:>8}{ms['analysis']:>10.2f}{ms['draw']:>8.2f}"
              f"{ms['output']:>8.2f}{total:>8.2f}   -> up to about {1000.0 / total:.0f} fps")


if __name__ == "__main__":
    main()
