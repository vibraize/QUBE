"""
Ember Bloom - glowing particles with smoky trails; every face gets its own swarm.

  bass, bassMid   -> beats burst blooms (expanding rings) on alternating pairs of
                     faces, so the rhythm travels around the cube: red when the bass
                     is louder, yellow when the bassMid is
  mid, midHigh    -> green orbs (mid) and cyan orbs (midHigh) drifting through a
                     swirling flow field (more of each band = more of its orbs, faster)
  high, highTop   -> tiny blue (high) and magenta (highTop) sparks that flicker and
                     vanish quickly
Blur + fade blend everything into soft trails.
"""
import numpy as np

from colors import (bass_color, bass_mid_color, high_color, high_top_color, mid_color,
                    mid_high_color)
from visuals.base import VisualMode
from visuals.effects import add_dots, add_glow, add_ring, blur, fade

MAX_ORBS = 90
MAX_SPARKS = 160
BLOOM_SECONDS = 0.6
BRIGHTNESS = 3.0      # the finished picture is multiplied by this: the blur and fade that
                      # make the soft trails also keep the particles dim


def spawn_counts(budgets, levels, power, rate, dt):
    """How many new particles each band gets this frame. `budgets` carries the
    fractions over from frame to frame, so slow rates still add up."""
    budgets += np.asarray(levels, dtype=np.float32) ** power * rate * dt
    counts = budgets.astype(np.int32)
    budgets -= counts
    return counts


class EmberBloom(VisualMode):
    name = "Ember Bloom"
    hue_cycle_seconds = 10    # every colour goes round the rainbow once every 10 s

    def __init__(self, layout):
        super().__init__(layout)
        self.canvas = layout.new_canvas()
        self.rng = np.random.default_rng()
        self.start()

    def start(self):
        self.canvas[:] = 0.0
        # Particles live in numpy arrays, one row per particle. `band` is 0 for the
        # lower band of the pair and 1 for the upper one, and picks the colour.
        self.orbs = np.zeros((0, 5), dtype=np.float32)     # x, y, age, lifetime, band
        self.sparks = np.zeros((0, 6), dtype=np.float32)   # x, y, age, lifetime, brightness, band
        self.blooms = []                                    # [x, y, age, power, colour]
        self.beat_count = 0
        self.orb_budget = np.zeros(2, dtype=np.float32)     # mid, midHigh
        self.spark_budget = np.zeros(2, dtype=np.float32)   # high, highTop

    def draw(self, audio, dt):
        bass = max(audio.bass, audio.bassMid)
        mid = max(audio.mid, audio.midHigh)
        high = max(audio.high, audio.highTop)
        c = self.canvas
        fade(c, half_life=0.15, dt=dt)
        blur(c, amount=0.3)

        # --- Bass: blooms on alternating face pairs (0 & 2, then 1 & 3) ------------
        if audio.beat:
            self.beat_count += 1
            power = 0.6 + 0.4 * bass
            # Red for a bass hit, yellow when the bassMid is the louder of the two
            color = bass_color(power) if audio.bass >= audio.bassMid else bass_mid_color(power)
            for face in range(self.beat_count % 2, self.layout.faces, 2):
                x = face * self.face + self.rng.uniform(10, self.face - 10)
                y = self.rng.uniform(10, self.face - 10)
                self.blooms.append([x, y, 0.0, power, color])
        for bloom in self.blooms:
            bloom[2] += dt
        self.blooms = [b for b in self.blooms if b[2] < BLOOM_SECONDS]
        for x, y, age, power, color in self.blooms:
            life = age / BLOOM_SECONDS                          # 0 -> 1
            radius = 2.0 + 11.0 * (1.0 - (1.0 - life) ** 3)    # bursts fast, then slows
            color = color * power * (1.0 - life)
            add_glow(c, x, y, radius * 0.5, color * 1.5 * dt)
            add_ring(c, x, y, radius, 1.2, color * 10.0 * dt)

        # --- Mids: orbs drifting through a flow field, green (mid) and cyan (midHigh) ---
        counts = spawn_counts(self.orb_budget, (audio.mid, audio.midHigh), 1.5, 40.0, dt)
        spawn = int(counts.sum())
        if spawn:
            new = np.column_stack([
                self.rng.uniform(0, self.width, spawn),     # x
                self.rng.uniform(0, self.height, spawn),    # y
                np.zeros(spawn),                            # age
                self.rng.uniform(1.2, 2.8, spawn),          # lifetime (seconds)
                np.repeat([0.0, 1.0], counts),              # band: mid, then midHigh
            ]).astype(np.float32)
            self.orbs = np.vstack([self.orbs, new])[-MAX_ORBS:]
        if len(self.orbs):
            x, y, t = self.orbs[:, 0], self.orbs[:, 1], self.time
            speed = 3.0 + 14.0 * mid                  # pixels per second
            vx = np.cos(y * 0.21 + t * 0.9) + 0.5 * np.sin(x * 0.13 - t * 0.6)
            vy = 0.8 * np.sin(x * 0.17 + t * 0.7)
            self.orbs[:, 0] = (x + vx * speed * dt) % self.width
            self.orbs[:, 1] = y + vy * speed * dt
            self.orbs[:, 2] += dt
            alive = ((self.orbs[:, 2] < self.orbs[:, 3])
                     & (self.orbs[:, 1] > -1.0) & (self.orbs[:, 1] < self.height))
            self.orbs = self.orbs[alive]
            envelope = np.sin(np.pi * self.orbs[:, 2] / self.orbs[:, 3])     # fade in, then out
            brightness = envelope * (0.5 + 0.7 * mid)
            colors = np.where(self.orbs[:, 4:5] > 0.5, mid_high_color(audio.midHigh), mid_color(audio.mid))
            add_dots(c, self.orbs[:, 0], self.orbs[:, 1],
                     colors * brightness[:, None] * 14.0 * dt)

        # --- Highs: short-lived flickering sparks, blue (high) and magenta (highTop) ---
        counts = spawn_counts(self.spark_budget, (audio.high, audio.highTop), 1.2, 140.0, dt)
        spawn = int(counts.sum())
        if spawn:
            new = np.column_stack([
                self.rng.uniform(0, self.width, spawn),
                self.rng.uniform(0, self.height, spawn),
                np.zeros(spawn),
                self.rng.uniform(0.06, 0.25, spawn),        # lifetime (seconds)
                self.rng.uniform(0.4, 1.0, spawn),          # brightness
                np.repeat([0.0, 1.0], counts),              # band: high, then highTop
            ]).astype(np.float32)
            self.sparks = np.vstack([self.sparks, new])[-MAX_SPARKS:]
        if len(self.sparks):
            self.sparks[:, 2] += dt
            self.sparks = self.sparks[self.sparks[:, 2] < self.sparks[:, 3]]
            flicker = self.rng.uniform(0.3, 1.0, len(self.sparks)) * self.sparks[:, 4]
            colors = np.where(self.sparks[:, 5:6] > 0.5, high_top_color(audio.highTop),
                              high_color(audio.high))
            add_dots(c, self.sparks[:, 0], self.sparks[:, 1], colors * flicker[:, None])

        np.clip(c, 0.0, 1.5, out=c)
        return np.clip(c * BRIGHTNESS, 0.0, 1.0)
