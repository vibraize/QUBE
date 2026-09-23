"""
visuals/base.py - the base class every visual mode builds on.

To make your own mode: copy visuals/level_meter.py (the simplest, most commented
example) to a new file in this folder and rename the class. That's all - QUBE
finds it by itself and the next / previous buttons include it.
"""
from visuals.effects import RgbDelay, hue_rotate


class VisualMode:
    name = "Unnamed"   # shown in the terminal and the web preview
    cycle = True       # False = keep it off the buttons' rotation (see visuals/qr_code.py)
    order = 100        # lower sorts earlier; modes with the same order go alphabetically
    hue_cycle_seconds = 0   # 0 = off. Set it to turn every colour this mode draws all the
                            # way round the colour wheel once every that-many seconds:
                            # 10 = a full rainbow every 10 s. Negative turns the other way.
    rgb_delay = None        # None = off. (red, green, blue) seconds, e.g. (0.3, 0.2, 0.1):
                            # each colour shows the picture from that long ago, so movement
                            # leaves colour fringes. Applied after the hue cycle.

    def __init__(self, layout):
        self.layout = layout
        self.width = layout.width     # full strip width (160 for 4 faces of 40)
        self.height = layout.height   # strip height (40)
        self.face = layout.face       # one face is face x face pixels
        self.time = 0.0               # seconds this mode has been running
        self._rgb_delay = None        # built on first use, if rgb_delay is set

    def start(self):
        """Called every time this mode becomes active. Override to reset state."""

    def draw(self, audio, dt):
        """Return this frame: a float32 array shaped (height, width, 3), values 0..1.
        audio = AudioFeatures (see audio_analysis.py); dt = seconds since last frame."""
        raise NotImplementedError

    def step(self, audio, dt):
        """Called by the main loop: advances the clock, draws, then applies the post
        effects that are switched on: the hue cycle, then the RGB delay."""
        self.time += dt
        frame = self.draw(audio, dt)
        if self.hue_cycle_seconds:
            frame = hue_rotate(frame, 360.0 * self.time / self.hue_cycle_seconds)
        if self.rgb_delay:
            if getattr(self, "_rgb_delay", None) is None:
                self._rgb_delay = RgbDelay(self.rgb_delay)
            frame = self._rgb_delay.apply(frame, self.time)
        return frame
