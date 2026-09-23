"""
display - where finished frames go.

Every display has the same methods:
    show(frame, info)   frame = float32 array (height, width, 3), values 0..1
                        info  = dict with mode name, fps, audio levels and LED state (for previews)
    poll_commands()     list of commands sent from the display (e.g. browser buttons)
    close()
and a flag `wants_brightness`: True if MASTER_BRIGHTNESS and the power limit (PowerLimit,
below) should be applied before a frame is shown.
"""
import numpy as np


def create_display(kind, layout, cfg):
    kind = kind.lower()
    if kind == "web":
        from display.web_preview import WebPreview
        return WebPreview(layout, cfg)
    if kind == "matrix":
        from display.led_matrix import LedMatrixDisplay
        return LedMatrixDisplay(layout, cfg)
    if kind == "none":
        return NullDisplay()
    raise ValueError(f"Unknown display '{kind}'. Use web, matrix or none.")


class NullDisplay:
    """Shows nothing. Use it to measure how fast the visuals run (--display none)."""
    wants_brightness = True

    def show(self, frame, info):
        pass

    def poll_commands(self):
        return []

    def close(self):
        pass


def to_uint8(frame):
    """Convert a 0..1 float frame into 0..255 bytes."""
    return (np.clip(frame, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)


def led_on_time(values, library_brightness=100.0):
    """The share of the time an LED is lit, for pixel values 0..1 (one value or a frame).

    The LED library doesn't light a pixel at 0.5 for half the time. It treats the value as
    perceived lightness and puts it through the CIE 1931 curve (rpi-rgb-led-matrix does this
    by default: luminance_cie1931 in lib/framebuffer.cc, copied here). So 0.5 is lit 18% of
    the time, 0.6 28%, 0.8 57% and 1.0 all of it. The panels' current follows the on-time,
    not the value. library_brightness is MATRIX_OPTIONS["brightness"], normally 100."""
    lightness = values * library_brightness              # 0..100, as the library sees it
    base = (lightness + 16.0) / 116.0
    return np.where(lightness > 8.0, base * base * base, lightness / 902.3)


class PowerLimit:
    """Keeps every power supply within its budget: POWER_SUPPLIES, LED_WATTS_PER_SUPPLY and
    PANEL_FULL_WATTS in config.py.

    For each frame it estimates the watts the LEDs on each supply will draw: a whole panel
    fully lit in one colour draws PANEL_FULL_WATTS for that colour, and anything less draws
    that times its average on-time (led_on_time above). If any supply would go over, the
    whole picture is dimmed, all faces alike, until the busiest supply is at its budget.
    The dimming shortens every LED's on-time by the same share, so the picture keeps its
    look and just gets darker."""

    def __init__(self, cfg, layout):
        self.face = layout.face
        self.faces = layout.faces
        self.budget = float(cfg.LED_WATTS_PER_SUPPLY)
        self.full_watts = np.asarray(cfg.PANEL_FULL_WATTS, dtype=np.float32)   # red, green, blue
        self.library_brightness = float(cfg.MATRIX_OPTIONS.get("brightness", 100))
        self.supplies = [list(faces) for faces in cfg.POWER_SUPPLIES]
        listed = sorted(face for faces in self.supplies for face in faces)
        if listed != list(range(layout.faces)):
            raise ValueError(f"POWER_SUPPLIES in config.py has to name every face from 0 to "
                             f"{layout.faces - 1} exactly once, but it's {cfg.POWER_SUPPLIES}.")
        if self.budget <= 0 or self.full_watts.shape != (3,) or (self.full_watts < 0).any():
            raise ValueError("LED_WATTS_PER_SUPPLY has to be above 0, and PANEL_FULL_WATTS "
                             "three numbers (red, green, blue), none below 0.")
        self.watts = [0.0] * len(self.supplies)   # the last frame's estimate, before any dimming
        self.dimmed = False                        # whether the last frame had to be dimmed

    def supply_watts(self, frame):
        """Estimated watts for the LEDs on each supply, for a frame of 0..1 values."""
        on_time = led_on_time(frame, self.library_brightness)
        # Add up each face's red, green and blue on-times: shape (faces, 3). (Two one-axis
        # sums, because numpy is about 10x slower summing over two axes in one go.)
        per_face = on_time.reshape(self.face, self.faces, self.face, 3).sum(axis=0).sum(axis=1)
        face_watts = per_face @ self.full_watts / (self.face * self.face)
        return [float(face_watts[faces].sum()) for faces in self.supplies]

    def apply(self, frame, brightness):
        """Returns a new frame: frame * brightness, dimmed further if needed."""
        out = frame * brightness
        np.clip(out, 0.0, 1.0, out=out)            # the most the panels can show anyway
        self.watts = self.supply_watts(out)
        if np.isnan(self.watts).any():             # a NaN from a buggy visual: make it black,
            np.nan_to_num(out, copy=False)         # so the rest can't hide from the estimate
            self.watts = self.supply_watts(out)
        busiest = max(self.watts)
        self.dimmed = busiest > self.budget
        if self.dimmed:
            # Multiply every on-time by share. On the library's curve that is a simple step
            # in lightness, new = share^(1/3) * (old + 16) - 16, which in values is:
            share = self.budget / busiest
            offset = 16.0 / self.library_brightness
            out += offset
            out *= share ** (1.0 / 3.0)
            out -= offset
            np.maximum(out, 0.0, out=out)          # the faintest pixels go to black
        return out
