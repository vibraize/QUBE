"""
Radial Waveform - audio waveform wrapped into a circle.
The shape pulses outward on bass hits, rotates with mids, and every band has
its own colour:

  bass     -> the outer ring (red)
  bassMid  -> the centre dot, which pulses on beats (yellow)
  mid      -> the inner ring (green)
  midHigh  -> a thin ring between the two (cyan)
  high     -> sparkles on the outer ring (blue)
  highTop  -> more sparkles on the outer ring (magenta)

Draws audio.waveform: the sound wave held still like an oscilloscope and scaled
to fill the space (see audio_analysis.py). The raw samples are far too small to
draw directly - at a microphone, music peaks at a few thousandths of full scale.
"""
import numpy as np

from colors import (bass_color, bass_mid_color, high_color, high_top_color, mid_color,
                    mid_high_color)
from visuals.base import VisualMode
from visuals.effects import fade


def seam_taper(n, fraction=0.1):
    """1.0 in the middle, easing to 0.0 over the first and last `fraction` of n points."""
    edge = max(1, int(n * fraction))
    ramp = 0.5 - 0.5 * np.cos(np.linspace(0.0, np.pi, edge))     # 0 -> 1, smoothly
    taper = np.ones(n, dtype=np.float32)
    taper[:edge] = ramp
    taper[-edge:] = ramp[::-1]
    return taper


class RadialWaveform(VisualMode):
    name = "Radial Waveform"
    hue_cycle_seconds = 10    # every colour goes round the rainbow once every 10 s

    def __init__(self, layout):
        super().__init__(layout)
        self.trail = layout.new_face()
        self.spin = 0.0
        
        # Precompute pixel coordinates centered at 0,0 range -1 to 1
        size = layout.face  # 40
        lin = np.linspace(-1.0, 1.0, size)
        self.px, self.py = np.meshgrid(lin, lin)
        
        # Polar coordinates for every pixel
        self.pixel_angle = np.arctan2(self.py, self.px)  # -pi to pi
        self.pixel_radius = np.sqrt(self.px**2 + self.py**2)
        self.taper = None     # built on first use, to match the waveform's length

    def start(self):
        self.trail[:] = 0.0
        self.spin = 0.0

    def _waveform_radius_at_angle(self, samples, angles, base_radius, amplitude):
        """
        For each angle in `angles`, find where the waveform puts the ring.

        samples:     audio.waveform, -1.0 to 1.0
        angles:      array of angles in radians (any range - it wraps around)
        base_radius: float, center ring radius (0.0 to 1.0)
        amplitude:   float, how far the waveform can deviate from base
        """
        if self.taper is None or len(self.taper) != len(samples):
            self.taper = seam_taper(len(samples))
        # The wave's first and last points are different moments in time, so they
        # wouldn't meet where the ring closes. Easing both ends to zero joins them.
        values = samples * self.taper
        # Spread the waveform once around the circle. np.interp with period=2*pi wraps
        # around, and blends between neighbouring points instead of picking one.
        wave_angles = np.linspace(-np.pi, np.pi, len(values), endpoint=False)
        return base_radius + np.interp(angles, wave_angles, values, period=2 * np.pi) * amplitude

    def draw(self, audio, dt):
        bass = max(audio.bass, audio.bassMid)
        mid  = max(audio.mid,  audio.midHigh)

        # Fade the trail
        fade(self.trail, half_life=0.08 + 0.05 * bass, dt=dt)

        layer = np.zeros_like(self.trail)

        # Slowly rotate the whole waveform with mids
        self.spin += (0.2 + 1.2 * mid) * dt
        rotated_angle = self.pixel_angle + self.spin  # shift lookup angle

        # --- Outer waveform ring ---
        base_r   = 0.55 + 0.15 * bass + 0.10 * audio.beat_pulse
        amplitude = 0.08 + 0.18 * bass
        thickness = 0.04 + 0.06 * bass

        waveform_r = self._waveform_radius_at_angle(
            audio.waveform, rotated_angle, base_r, amplitude
        )
        dist = np.abs(self.pixel_radius - waveform_r)

        # Soft brush along the ring
        falloff = np.clip(1.0 - dist / thickness, 0.0, 1.0)
        layer += falloff[..., None] * bass_color(bass) * (0.6 + 0.4 * bass)

        # --- Inner waveform ring (mids, spinning opposite direction) ---
        inner_angle = self.pixel_angle - self.spin * 0.7
        inner_r = self._waveform_radius_at_angle(
            audio.waveform, inner_angle,
            base_radius=0.28 + 0.08 * mid,
            amplitude=0.06 + 0.10 * mid
        )
        inner_dist = np.abs(self.pixel_radius - inner_r)
        inner_falloff = np.clip(1.0 - inner_dist / (0.03 + 0.04 * mid), 0.0, 1.0)
        layer += inner_falloff[..., None] * mid_color(mid) * (0.4 + 0.6 * mid)

        # --- Thin midHigh ring between the two, turning faster ---
        middle_angle = self.pixel_angle + self.spin * 1.4
        middle_r = self._waveform_radius_at_angle(
            audio.waveform, middle_angle,
            base_radius=0.42 + 0.06 * audio.midHigh,
            amplitude=0.04 + 0.08 * audio.midHigh
        )
        middle_dist = np.abs(self.pixel_radius - middle_r)
        middle_falloff = np.clip(1.0 - middle_dist / (0.025 + 0.03 * audio.midHigh), 0.0, 1.0)
        layer += middle_falloff[..., None] * mid_high_color(audio.midHigh) * (0.3 + 0.7 * audio.midHigh)

        # --- Center dot, pulses with the beat, in the bassMid colour ---
        center_r = 0.08 + 0.12 * audio.beat_pulse
        center_mask = self.pixel_radius < center_r
        center_falloff = np.clip(
            1.0 - self.pixel_radius / center_r, 0.0, 1.0
        )
        layer += center_falloff[..., None] * bass_mid_color(audio.bassMid) * center_mask[..., None]

        # --- Sparkles scattered on the ring: blue for high, magenta for highTop ---
        for level, color, offset in ((audio.high, high_color(audio.high), 0.0),
                                     (audio.highTop, high_top_color(audio.highTop), 0.5)):
            if level <= 0.3:
                continue
            count = int(level * 15)
            # `offset` puts the highTop sparkles halfway between the high ones
            angles = np.linspace(-np.pi, np.pi, count, endpoint=False) + offset * 2 * np.pi / count
            # + spin: look the radius up the same way the outer ring does, so each
            # sparkle lands on the ring as it's drawn rather than beside it
            wave_r = self._waveform_radius_at_angle(
                audio.waveform, angles + self.spin,
                base_r, amplitude
            )
            # Convert polar to pixel coordinates
            xs = ((wave_r * np.cos(angles) + 1.0) * 0.5 * (self.layout.face - 1)).astype(int)
            ys = ((wave_r * np.sin(angles) + 1.0) * 0.5 * (self.layout.face - 1)).astype(int)
            valid = (xs >= 0) & (xs < self.layout.face) & \
                    (ys >= 0) & (ys < self.layout.face)
            layer[ys[valid], xs[valid]] = np.maximum(layer[ys[valid], xs[valid]], color)

        # Merge into trail
        np.maximum(self.trail, layer * 0.55, out=self.trail)
        np.clip(self.trail, 0.0, 1.0, out=self.trail)

        img = np.maximum(self.trail, layer)
        np.clip(img, 0.0, 1.0, out=img)
        return self.layout.tile(img, mirror_alternate=True)