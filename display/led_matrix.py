"""
display/led_matrix.py - sends frames to the LED panels using rpi-rgb-led-matrix.

Needs the library built with tools/patch_rgbmatrix.py (see PI_SETUP.md), because the
stock library can't drive the 28-pin panels. Settings are MATRIX_OPTIONS in config.py.

Fewer panels than faces is fine while building up: with chain_length 1 the single panel
shows face 0, with 2 it shows faces 0 and 1, and so on.

Run on the Raspberry Pi with sudo (the library needs root for GPIO timing).
"""
import numpy as np

from display import to_uint8
from layout import orient_for_panels


class LedMatrixDisplay:
    wants_brightness = True     # apply MASTER_BRIGHTNESS and the power limit before sending

    def __init__(self, layout, cfg):
        try:
            from rgbmatrix import RGBMatrix, RGBMatrixOptions
        except ImportError as error:
            raise RuntimeError(
                "Can't import rgbmatrix (the rpi-rgb-led-matrix Python bindings). Run this on "
                "the Raspberry Pi where the library is installed, or use --display web.") from error

        self.layout = layout
        self.cfg = cfg
        options = RGBMatrixOptions()
        for key, value in cfg.MATRIX_OPTIONS.items():
            if not hasattr(options, key):
                raise RuntimeError(f"MATRIX_OPTIONS['{key}'] is not an option in this rgbmatrix version.")
            setattr(options, key, value)
        self.matrix = RGBMatrix(options=options)
        self.canvas = self.matrix.CreateFrameCanvas()
        # A panel is `cols` shift-register columns wide but only FACE_SIZE of those have LEDs.
        # The rest are invisible and have to be left black - see PANEL_COLUMN_OFFSET in config.py.
        self.stride = int(cfg.MATRIX_OPTIONS["cols"])
        self.offset = int(getattr(cfg, "PANEL_COLUMN_OFFSET", 0))
        width, height = self.canvas.width, self.canvas.height
        if height != layout.height or not width or width % self.stride:
            raise RuntimeError(
                f"The panel canvas is {width}x{height}, which isn't a whole number of "
                f"{self.stride}-column panels {layout.height} pixels high. Check FACE_SIZE, "
                f"NUM_FACES and MATRIX_OPTIONS.")
        self.panels = width // self.stride
        if self.panels > layout.faces:
            raise RuntimeError(f"{self.panels} panels are chained but there are only "
                               f"{layout.faces} faces to show. Check chain_length and NUM_FACES.")
        if self.offset + layout.face > self.stride:
            raise RuntimeError(f"PANEL_COLUMN_OFFSET ({self.offset}) + FACE_SIZE ({layout.face}) "
                               f"is more than the {self.stride} columns a panel has.")
        if self.panels != layout.faces:
            print(f"{self.panels} panel(s) chained: showing the first {self.panels} of "
                  f"{layout.faces} faces.")
        # Built once and reused. The dead columns stay black for as long as it lives.
        self.buffer = np.zeros((height, width, 3), dtype=np.uint8)

        # How frames get copied to the canvas (see PIXEL_PUSH in config.py)
        self.method = cfg.PIXEL_PUSH
        self.Image = None
        if self.method in ("auto", "pillow"):
            try:
                from PIL import Image
                self.Image = Image
            except ImportError:
                if self.method == "pillow":
                    raise RuntimeError("PIXEL_PUSH is 'pillow' but Pillow isn't installed.")
                print("Pillow not found, using per-pixel drawing (slower).")
                self.method = "setpixel"

    def show(self, frame, info):
        oriented = orient_for_panels(frame, self.layout, self.cfg.FACE_ORDER,
                                     self.cfg.FACE_ROTATION, self.cfg.FACE_MIRROR)
        pixels = to_uint8(oriented)
        face = self.layout.face
        for slot in range(self.panels):      # each face into its panel's visible columns
            x = slot * self.stride + self.offset
            self.buffer[:, x:x + face] = pixels[:, slot * face:(slot + 1) * face]
        if self.method != "setpixel":
            try:
                # Fast path: the library copies a whole Pillow image in C
                self.canvas.SetImage(self.Image.fromarray(self.buffer), 0, 0)
            except Exception as error:     # e.g. a Pillow / library version mismatch
                if self.method == "pillow":
                    raise
                print(f"Fast drawing failed ({error!r}), switching to per-pixel drawing.")
                self.method = "setpixel"
        if self.method == "setpixel":
            self._set_pixels(self.buffer)
        self.canvas = self.matrix.SwapOnVSync(self.canvas)

    def _set_pixels(self, pixels):
        """Slow fallback: clear the canvas, then set only the pixels that are lit."""
        self.canvas.Clear()
        set_pixel = self.canvas.SetPixel
        ys, xs = np.nonzero(pixels.any(axis=2))
        for x, y, (r, g, b) in zip(xs.tolist(), ys.tolist(), pixels[ys, xs].tolist()):
            set_pixel(x, y, r, g, b)

    def poll_commands(self):
        return []

    def close(self):
        self.matrix.Clear()
