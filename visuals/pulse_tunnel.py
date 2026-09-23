"""
Pulse Tunnel - pulsing polygons fly out of the middle of every face, leaving
video-feedback trails (the classic feedback-loop look).

  bass     -> red square outline: size and thickness, shockwave rings on beats
  bassMid  -> yellow square outline inside it, turned the other way
  mid      -> swirl speed and the green star
  midHigh  -> cyan ring in the middle of the star
  high     -> blue sparkles
  highTop  -> magenta sparkles
All faces show the same tunnel, but faces 1 and 3 are mirrored, so the swirl
changes direction as you walk around the cube.
"""
import numpy as np

from colors import bass_color, bass_mid_color, high_color, mid_color, mid_high_color, high_top_color
from visuals.base import VisualMode
from visuals.effects import ZoomFeedback, fade, polygon_distance, ring


class PulseTunnel(VisualMode):
    name = "Pulse Tunnel"
    hue_cycle_seconds = 10    # every colour goes round the rainbow once every 10 s

    def __init__(self, layout):
        super().__init__(layout)
        self.trail = layout.new_face()                        # feedback buffer for one face
        self.feedback = ZoomFeedback(self.face)
        _, _, self.radius, self.angle = layout.face_grid()    # polar coordinates, radius 0..~1.4
        self.spin = 0.0
        self.shockwaves = []                                  # radius of each expanding beat ring
        self.rng = np.random.default_rng()

    def start(self):
        self.trail[:] = 0.0
        self.shockwaves = []

    def draw(self, audio, dt):
        bass = max(audio.bass, audio.bassMid)
        mid = max(audio.mid, audio.midHigh)
        frames = dt * 40.0     # zoom and swirl amounts are tuned "per frame at 40 fps"

        # 1. Feedback: zoom last frame's trail outward, swirl it, and fade it quickly.
        zoom = (1.035 + 0.035 * bass) ** frames
        swirl = (0.004 + 0.02 * mid) * frames
        trail = self.feedback.apply(self.trail, zoom, swirl)
        fade(trail, half_life=0.035 + 0.03 * audio.volume, dt=dt)

        # 2. This frame's shapes, on a fresh layer.
        layer = np.zeros_like(trail)
        self.spin += (0.3 + 1.5 * mid) * dt
        sides = 4
        size = 0.20 + 0.15 * bass + 0.35 * audio.beat_pulse
        shape = polygon_distance(self.radius, self.angle, sides, rotation=self.spin)
        outline = ring(shape, size, thickness=0.05 + 0.08 * bass)
        layer += outline[..., None] * bass_color(audio.bass) * (0.5 + 0.5 * bass)

        # ...and a second, smaller one for the bassMid, turned the other way.
        shape = polygon_distance(self.radius, self.angle, sides, rotation=np.pi / sides - self.spin)
        outline = ring(shape, 0.7 * size + 0.08 * audio.bassMid, thickness=0.04 + 0.06 * audio.bassMid)
        layer += outline[..., None] * bass_mid_color(audio.bassMid) * (0.35 + 0.65 * audio.bassMid)

        # 3. Inner star in the mid color, spinning the other way, with a midHigh ring
        # in its middle.
        star = polygon_distance(self.radius, self.angle, sides * 2, rotation=-1.7 * self.spin)
        inner = ring(star, 0.10 + 0.10 * mid, thickness=0.04)
        layer += inner[..., None] * mid_color(audio.mid) * (0.3 + 0.7 * mid)
        core = ring(self.radius, 0.04 + 0.06 * audio.midHigh, thickness=0.035)
        layer += core[..., None] * mid_high_color(audio.midHigh) * (0.3 + 0.7 * audio.midHigh)

        # 4. Beats launch shockwave rings that race outward.
        if audio.beat:
            self.shockwaves.append(size)
        self.shockwaves = [r + 1.8 * dt for r in self.shockwaves if r < 1.5]
        for r in self.shockwaves:
            layer += ring(self.radius, r, 0.06)[..., None] * bass_color(1.0) * 0.7

        # 5. Highs: random sparkles, blue for the high band and magenta for the highTop.
        for level, color in ((audio.high, high_color(audio.high)),
                             (audio.highTop, high_top_color(audio.highTop))):
            count = int(level * 20)
            if count:
                ys = self.rng.integers(0, self.face, count)
                xs = self.rng.integers(0, self.face, count)
                layer[ys, xs] = np.maximum(layer[ys, xs], color)

        # Feed only a dimmer copy of the shapes back into the trail, and merge with
        # max() instead of adding. That keeps the trails as distinct rings instead
        # of letting them smear into one solid glow.
        np.maximum(trail, layer * 0.6, out=trail)
        np.clip(trail, 0.0, 1.0, out=trail)
        self.trail = trail

        img = np.maximum(trail, layer)
        np.clip(img, 0.0, 1.0, out=img)
        return self.layout.tile(img, mirror_alternate=True)
