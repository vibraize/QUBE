"""
colors.py - the synesthesia palette. All sound-to-color decisions live here.

    bass through highTop each have independent quiet and loud colors.

Colors are (red, green, blue) with values from 0 to 1 (not 0 to 255), because
float math makes blending and fading easy. The display code converts to 0-255.
"""
import numpy as np

# ---- Edit these to change how each band looks ----------------------------------
# Each band blends from its "quiet" color to its "loud" color as its level rises.
BASS_QUIET = (0.50, 0.00, 0.00)
BASS_LOUD = (1.00, 0.00, 0.00)
BASS_MID_QUIET = (0.50, 0.50, 0.00)
BASS_MID_LOUD = (1.00, 1.00, 0.00)
MID_QUIET = (0.00, 0.50, 0.00)
MID_LOUD = (0.00, 1.00, 0.00)
MID_HIGH_QUIET = (0.00, 0.50, 0.50)
MID_HIGH_LOUD = (0.00, 1.00, 1.00)
HIGH_QUIET = (0.00, 0.00, 0.50)
HIGH_LOUD = (0.00, 0.00, 1.00)
HIGH_TOP_QUIET = (0.50, 0.00, 0.50)
HIGH_TOP_LOUD = (1.00, 0.00, 1.00)

# Lowest frequency (0.0) to highest frequency (1.0), as (position, color) stops.
SPECTRUM_STOPS = [
    (0.00, (1.00, 0.00, 0.00)),   # sub bass: red
    (0.18, (1.00, 1.00, 0.00)),   # bass: yellow
    (0.32, (0.00, 1.00, 0.00)),   # upper bass: green
    (0.48, (0.00, 1.00, 1.00)),   # low mids: cyan
    (0.64, (0.00, 0.00, 1.00)),   # mids: blue
    (0.80, (1.00, 0.00, 1.00)),   # highs: magenta
    (1.00, (1.00, 1.00, 1.00)),   # air: white
]


def lerp_color(a, b, t):
    """Blend color a toward color b. t=0 gives a, t=1 gives b."""
    t = min(max(float(t), 0.0), 1.0)
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    return a + (b - a) * t


def bass_color(level):
    return lerp_color(BASS_QUIET, BASS_LOUD, level)


def bass_mid_color(level):
    return lerp_color(BASS_MID_QUIET, BASS_MID_LOUD, level)


def mid_color(level):
    return lerp_color(MID_QUIET, MID_LOUD, level)


def mid_high_color(level):
    return lerp_color(MID_HIGH_QUIET, MID_HIGH_LOUD, level)


def high_color(level):
    return lerp_color(HIGH_QUIET, HIGH_LOUD, level)


def high_top_color(level):
    return lerp_color(HIGH_TOP_QUIET, HIGH_TOP_LOUD, level)


def make_gradient(stops, size=256):
    """Turn (position, color) stops into a lookup table of shape (size, 3)."""
    positions = np.array([p for p, _ in stops], dtype=np.float32)
    colors = np.array([c for _, c in stops], dtype=np.float32)
    x = np.linspace(0.0, 1.0, size, dtype=np.float32)
    lut = np.empty((size, 3), dtype=np.float32)
    for channel in range(3):
        lut[:, channel] = np.interp(x, positions, colors[:, channel])
    return lut


SPECTRUM_LUT = make_gradient(SPECTRUM_STOPS)


def spectrum_color(position):
    """Color for a spot on the spectrum (0 = lowest bass, 1 = highest treble).
    Accepts one number or a whole numpy array of positions."""
    last = len(SPECTRUM_LUT) - 1
    idx = np.clip(np.asarray(position, dtype=np.float32) * last, 0, last)
    return SPECTRUM_LUT[idx.astype(np.int32)]


def sound_color(audio):
    """Mix the six bands into one color, weighted by their loudness."""
    levels = np.array([audio.bass, audio.bassMid, audio.mid, audio.midHigh,
                       audio.high, audio.highTop], dtype=np.float32)
    colors = np.array([bass_color(audio.bass), bass_mid_color(audio.bassMid),
                       mid_color(audio.mid), mid_high_color(audio.midHigh),
                       high_color(audio.high), high_top_color(audio.highTop)])
    weights = levels + 1e-3
    return (colors * weights[:, None]).sum(axis=0) / weights.sum()
