"""
Mirror Scope - a basic oscilloscope, mirrored top to bottom.

The sound wave (audio.waveform) runs left to right across each face, drawn together
with its own reflection, so it opens and closes symmetrically around the middle.
Short trails give it the glow of an old phosphor screen. The colour follows where
the sound sits in the spectrum - red when it's bassy, through yellow, green, cyan,
blue and magenta, to white when it's bright - bass thickens the line, and beats
brighten it.

Also the simplest example of drawing audio.waveform, if you want to write your own.
"""
import numpy as np

from colors import spectrum_color
from visuals.base import VisualMode
from visuals.effects import fade


class MirrorScope(VisualMode):
    name = "Mirror Scope"
    hue_cycle_seconds = 10    # every colour goes round the rainbow once every 10 s

    def __init__(self, layout):
        super().__init__(layout)
        size = layout.face
        self.trail = layout.new_face()
        self.rows = np.arange(size, dtype=np.float32)[:, None]     # each row's number, as a column
        self.across = np.linspace(0.0, 1.0, size)                   # 0 at the left edge, 1 at the right
        self.middle = (size - 1) / 2.0                              # the row the wave swings around

    def start(self):
        self.trail[:] = 0.0

    def line(self, y, thickness):
        """A soft line through height y[x] in every column x. Each column also reaches
        halfway to its neighbours, so steep parts of the wave stay joined up instead of
        breaking into separate dots."""
        before = np.concatenate([y[:1], y[:-1]])
        after = np.concatenate([y[1:], y[-1:]])
        top = np.minimum(y, np.minimum((y + before) / 2, (y + after) / 2))
        bottom = np.maximum(y, np.maximum((y + before) / 2, (y + after) / 2))
        # How far each pixel is outside its column's stretch of line (0 = on it)
        outside = np.maximum(np.maximum(top - self.rows, self.rows - bottom), 0.0)
        return np.clip(1.0 - outside / thickness, 0.0, 1.0)

    def draw(self, audio, dt):
        # The wave, one value per column (-1..1)
        wave = np.interp(self.across, np.linspace(0.0, 1.0, len(audio.waveform)),
                         audio.waveform).astype(np.float32)
        height = self.middle - 1.0                  # leave a pixel free at the top and bottom
        wave_y = self.middle - wave * height        # the wave...
        mirror_y = self.middle + wave * height      # ...and its reflection

        bass = max(audio.bass, audio.bassMid)
        thickness = 0.8 + 1.6 * bass                # bass makes the line fatter
        glow = np.maximum(self.line(wave_y, thickness), self.line(mirror_y, thickness))

        brightness = 0.35 + 0.65 * max(audio.volume, audio.beat_pulse)
        layer = glow[..., None] * spectrum_color(audio.brightness) * brightness

        fade(self.trail, half_life=0.07, dt=dt)    # short, phosphor-like trails
        np.maximum(self.trail, layer, out=self.trail)
        # Faces 1 and 3 are flipped left-right, so neighbouring faces meet in a mirror line
        return self.layout.tile(self.trail, mirror_alternate=True)
