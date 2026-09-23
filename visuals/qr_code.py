"""
QR Code - a still picture rather than a visual: a scannable link to your page.

It lives on its own button instead of in the mode cycle. It's listed in EXTRA_MODES
(visuals/__init__.py), so auto-cycling never lands on it. The same code goes on every
face, so it can be scanned from any side of the cube.

The code is baked in below, so nothing is generated on the Pi and there's no extra
library to install. To point it somewhere else:

    python3 tools/make_qr.py "https://example.com"

and paste what it prints over QR_URL and QR_ROWS.

How it fits: 25x25 modules centred in a 40x40 face leaves a 7-pixel light border, well
over the 4-module quiet zone scanners need. Dark modules are unlit and light ones are
white, which is the polarity scanners expect. Checked by decoding the finished face
back to the URL, including dimmed right down, since the power limit in config.py dims
a mostly-white frame a long way. Contrast is what a scanner needs, not brightness.
"""
import numpy as np

from visuals.base import VisualMode

QR_URL = "https://linktr.ee/vibraize"
QR_ROWS = (
    "#######.###.#.#.#.#######",
    "#.....#..##..##.#.#.....#",
    "#.###.#.#..###.#..#.###.#",
    "#.###.#..##.###...#.###.#",
    "#.###.#..##..#....#.###.#",
    "#.....#.##.####.#.#.....#",
    "#######.#.#.#.#.#.#######",
    "..........#.#...#........",
    "#.#...##...##..##..#..#.#",
    "#.###....##.##.##.##.#.##",
    "####..###.##.#####.####.#",
    "#.#.#..#.#.##.####.###...",
    ".#..####.##.#...#.##....#",
    ".#.##....##....#..##...##",
    "##.#..###.##..###....##.#",
    "..#.........#..#..####...",
    "##.#.###.#.##..######..#.",
    "........##.##.###...#...#",
    "#######.#..##.#.#.#.#...#",
    "#.....#..###...##...#...#",
    "#.###.#........######..#.",
    "#.###.#..#.##....#..#.##.",
    "#.###.#.#.##.##.##.###.##",
    "#.....#..##...###.###....",
    "#######.##..#...#....#..#",
)


class QrCode(VisualMode):
    name = "QR Code"
    cycle = False      # its own button, never in the next / previous rotation

    def start(self):
        """Build the picture once. It never changes, so draw() just hands it back."""
        size = len(QR_ROWS)
        if size > self.face:
            raise ValueError(f"The QR code is {size} modules but a face is only "
                             f"{self.face} pixels. Use a shorter URL, or larger panels.")
        face = np.ones((self.face, self.face, 3), dtype=np.float32)   # light background
        top = (self.face - size) // 2                                 # centred, so the
        for y, row in enumerate(QR_ROWS):                             # border is the quiet zone
            dark = np.array([character == "#" for character in row])
            face[top + y, top:top + size][dark] = 0.0
        self.image = self.layout.tile(face)

    def draw(self, audio, dt):
        return self.image            # deliberately still: a moving QR code can't be scanned
