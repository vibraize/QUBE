"""
Spectrum River - six glowing ribbons that flow all the way around the cube, one for
each band, lowest at the bottom:

  bass     -> thick, slow, heavy swell       (red)
  bassMid  -> heavy, a little quicker         (yellow)
  mid      -> lively wiggle                   (green)
  midHigh  -> quicker, thinner                (cyan)
  high     -> thin, fast shimmer              (blue)
  highTop  -> thinnest and fastest            (magenta)
Along each ribbon, brightness and colour follow the live spectrum inside that
ribbon's frequency range. Every beat sends a warm pulse racing around the cube.
Waves repeat a whole number of times around the strip, so there's no seam where
face 3 meets face 0.
"""
import numpy as np

from colors import (BASS_LOUD, BASS_MID_LOUD, BASS_MID_QUIET, BASS_QUIET, HIGH_LOUD,
                    HIGH_QUIET, HIGH_TOP_LOUD, HIGH_TOP_QUIET, MID_HIGH_LOUD, MID_HIGH_QUIET,
                    MID_LOUD, MID_QUIET, bass_color)
from visuals.base import VisualMode
from visuals.effects import blur, fade

TWO_PI = 2.0 * np.pi

# One entry per ribbon - edit these to restyle the river.
#   level:  which audio value drives it          height: 0 = top edge, 1 = bottom edge
#   waves:  wave repeats around the cube (whole numbers keep it seamless)
#   speed, thickness (pixels), wiggle: (value when quiet, value when loud)
#   bands:  part of audio.spectrum that colors this ribbon (0 = lowest, 1 = highest)
RIBBONS = [
    dict(level="bass", height=0.84, waves=2, speed=(0.8, 3.0), thickness=(2.0, 6.5),
         wiggle=(0.04, 0.12), bands=(0.0, 0.2), quiet=BASS_QUIET, loud=BASS_LOUD),
    dict(level="bassMid", height=0.70, waves=3, speed=(1.1, 3.8), thickness=(1.8, 5.5),
         wiggle=(0.04, 0.12), bands=(0.12, 0.35), quiet=BASS_MID_QUIET, loud=BASS_MID_LOUD),
    dict(level="mid", height=0.56, waves=3, speed=(1.5, 5.0), thickness=(1.5, 4.5),
         wiggle=(0.05, 0.14), bands=(0.30, 0.55), quiet=MID_QUIET, loud=MID_LOUD),
    dict(level="midHigh", height=0.42, waves=4, speed=(2.2, 6.5), thickness=(1.3, 3.8),
         wiggle=(0.05, 0.13), bands=(0.50, 0.72), quiet=MID_HIGH_QUIET, loud=MID_HIGH_LOUD),
    dict(level="high", height=0.28, waves=6, speed=(3.0, 9.0), thickness=(1.0, 2.5),
         wiggle=(0.03, 0.08), bands=(0.68, 0.88), quiet=HIGH_QUIET, loud=HIGH_LOUD),
    dict(level="highTop", height=0.14, waves=8, speed=(3.8, 11.0), thickness=(0.9, 2.0),
         wiggle=(0.03, 0.07), bands=(0.82, 1.0), quiet=HIGH_TOP_QUIET, loud=HIGH_TOP_LOUD),
]


def blend(pair, level):
    """Pick a value between pair[0] (quiet) and pair[1] (loud)."""
    return pair[0] + (pair[1] - pair[0]) * level


class SpectrumRiver(VisualMode):
    name = "Spectrum River"
    hue_cycle_seconds = 10    # every colour goes round the rainbow once every 10 s

    def __init__(self, layout):
        super().__init__(layout)
        self.canvas = layout.new_canvas()
        u, _ = layout.strip_grid()
        self.u = u[0]                                              # 0..1 around the cube, per column
        self.rows = np.arange(self.height, dtype=np.float32)[:, None]
        self.phases = np.zeros(len(RIBBONS), dtype=np.float32)
        self.pulses = []                                           # [position, strength, direction]
        self.rng = np.random.default_rng()
        # Each column looks at a spot on the spectrum that sweeps low -> high -> low
        # twice around the cube, so every face shows the whole range with no seam.
        self.column_spot = 0.5 - 0.5 * np.cos(TWO_PI * 2.0 * self.u)

    def start(self):
        self.canvas[:] = 0.0
        self.pulses = []

    def draw(self, audio, dt):
        fade(self.canvas, half_life=0.12, dt=dt)
        layer = np.zeros_like(self.canvas)
        n = len(audio.spectrum)

        for i, rib in enumerate(RIBBONS):
            level = getattr(audio, rib["level"])

            # Wave shape: a main wave plus a smaller one for organic movement
            self.phases[i] += blend(rib["speed"], level) * dt
            k = rib["waves"]
            wave = (np.sin(TWO_PI * k * self.u - self.phases[i])
                    + 0.4 * np.sin(TWO_PI * (k + 1) * self.u + 0.7 * self.phases[i]))
            wiggle = blend(rib["wiggle"], level)
            center = (rib["height"] + wiggle * wave) * self.height

            # Soft glowing band around the center line (band * sqrt(band) = band^1.5, faster).
            # Only the rows this ribbon can reach are worked out: the wave swings at most
            # 1.4 x wiggle from the ribbon's height, and the glow reaches `thickness` past that.
            thickness = blend(rib["thickness"], level)
            reach = 1.4 * wiggle * self.height + thickness
            top = max(int(rib["height"] * self.height - reach), 0)
            bottom = min(int(np.ceil(rib["height"] * self.height + reach)) + 1, self.height)
            band = np.clip(1.0 - np.abs(self.rows[top:bottom] - center[None, :]) / thickness, 0.0, 1.0)
            band *= np.sqrt(band)

            # Loudness per column from this ribbon's slice of the spectrum
            lo = int(rib["bands"][0] * (n - 1))
            hi = int(np.ceil(rib["bands"][1] * (n - 1)))
            local = audio.spectrum[lo + np.round(self.column_spot * (hi - lo)).astype(np.int32)]

            quiet = np.asarray(rib["quiet"], dtype=np.float32)
            loud = np.asarray(rib["loud"], dtype=np.float32)
            colors = quiet + (loud - quiet) * local[:, None]          # one color per column
            strength = (0.25 + 0.75 * level) * (0.4 + 0.6 * local)
            layer[top:bottom] += band[..., None] * (colors * strength[:, None])[None, :, :]

        # Beats: a warm glow races around the cube, strongest near the bottom
        if audio.beat:
            self.pulses.append([self.rng.random(), 1.0, self.rng.choice([-1.0, 1.0])])
        for pulse in self.pulses:
            pulse[0] = (pulse[0] + pulse[2] * 0.7 * dt) % 1.0
            pulse[1] *= 0.5 ** (dt / 0.35)
        self.pulses = [p for p in self.pulses if p[1] > 0.03][-6:]
        if self.pulses:
            glow = np.zeros(self.width, dtype=np.float32)           # all pulses, one row
            for position, strength, _ in self.pulses:
                du = (self.u - position + 0.5) % 1.0 - 0.5            # distance around the cube
                glow += np.exp(-(du * self.width / 3.0) ** 2) * strength
            height_fade = (self.rows / self.height) ** 1.5
            layer += (height_fade * glow[None, :])[..., None] * bass_color(1.0) * 0.9

        np.maximum(self.canvas, layer, out=self.canvas)
        blur(self.canvas, amount=0.2)
        return np.clip(self.canvas, 0.0, 1.0)
