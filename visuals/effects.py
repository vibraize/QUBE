"""
visuals/effects.py - a toolbox of image effects for building visual modes.

Images are float32 numpy arrays shaped (height, width, 3) with values 0..1.
Pixel coordinates: x grows to the right, y grows downward, and pixel (x, y) has its
center exactly at (x, y). Everything is vectorized (no per-pixel Python loops) so
it stays fast on a Raspberry Pi 3B. Most functions change the image in place and
also return it.
"""
import collections
import time

import numpy as np


def fade(img, half_life, dt):
    """Darken img so it loses half its brightness every `half_life` seconds.
    Frame-rate independent: looks the same at 30 or 60 fps."""
    img *= 0.5 ** (dt / max(half_life, 1e-4))
    return img


def hue_rotate(img, degrees):
    """Turn every colour's hue `degrees` around the colour wheel, keeping its brightness
    and saturation: red becomes yellow at 60, green at 120, blue at 240, and red again
    at 360. Negative degrees turn the other way. Greys, white and black stay as they are.

    Returns a NEW image, unlike most effects here, so it can never feed back into a
    trail and spin faster and faster. To cycle a whole mode through the rainbow, set
    `hue_cycle_seconds` on its class (see visuals/base.py). To cycle just one layer,
    call this with an angle that grows with time: hue_rotate(layer, self.time * 36)
    goes round once every 10 seconds."""
    # (Written for speed on a Pi 3B: np.maximum of the channels is ~18x faster than
    # img.max(axis=-1), and float % is ~100x slower than a multiply, so it's avoided.)
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    brightest = np.maximum(np.maximum(r, g), b)
    dimmest = np.minimum(np.minimum(r, g), b)
    chroma = brightest - dimmest                     # 0 for greys, which have no hue
    # Treat anything below a millionth as grey. Fading trails decay toward zero without
    # ever reaching it, and dividing by a leftover 1e-39 would overflow to infinity.
    inverse = 1.0 / np.where(chroma > 1e-6, chroma, 1.0)
    # Hue on a 0..6 scale (1 = 60 degrees), from whichever channel leads, then turned
    hue = np.where(brightest == r, (g - b) * inverse,
                   np.where(brightest == g, (b - r) * inverse + 2.0, (r - g) * inverse + 4.0))
    hue += (degrees / 60.0) % 6.0
    hue -= 6.0 * np.floor(hue / 6.0)                 # wrap back into 0..6
    # Rebuild each channel. A channel is fully on within 60 degrees of its own hue (red
    # at 0, green 120, blue 240), fully off from 120 degrees away, and fades in between.
    # Keeping the brightest and dimmest values the same means only the hue moves.
    out = np.empty_like(img)
    for channel, centre in enumerate((0.0, 2.0, 4.0)):
        away = np.abs(hue - centre)
        away = np.minimum(away, 6.0 - away)          # the short way round the wheel
        off = np.minimum(np.maximum(away - 1.0, 0.0), 1.0)
        out[..., channel] = brightest - chroma * off
    return out


class RgbDelay:
    """Colour delay: red shows the picture from `delays[0]` seconds ago, green from
    `delays[1]`, blue from `delays[2]`. Anything that moves leaves red, green and blue
    fringes behind it, so even a grey picture turns colourful; still parts stay as they
    are. Timed in seconds rather than frames, so it looks the same at any frame rate.
    To use it on a mode, set `rgb_delay` on its class (see visuals/base.py)."""

    def __init__(self, delays):
        self.delays = tuple(float(d) for d in delays)
        self.history = collections.deque()      # (time, frame) pairs, oldest first
        self.last_used = None

    def apply(self, frame, now):
        """Store this frame (taken at `now` seconds) and return the colour-delayed one."""
        wall = time.monotonic()
        if self.last_used is not None and wall - self.last_used > 0.5:
            self.history.clear()                 # the mode was off for a while: start fresh
        self.last_used = wall
        self.history.append((now, frame.copy()))
        oldest_needed = now - max(self.delays)
        while len(self.history) > 1 and self.history[1][0] <= oldest_needed:
            self.history.popleft()               # drop frames no channel can reach any more
        out = np.empty_like(frame)
        for channel, delay in enumerate(self.delays):
            wanted = now - delay                 # the stored frame nearest that moment
            _, past = min(self.history, key=lambda entry: abs(entry[0] - wanted))
            out[..., channel] = past[..., channel]
        return out


def blur(img, amount=0.5, wrap_x=True):
    """Soft glow: blend each pixel toward the average of its 4 neighbors.
    wrap_x=True lets the left and right edges touch (use it for the full cube strip)."""
    near = np.empty_like(img)
    near[1:-1] = img[:-2] + img[2:]              # pixel above + pixel below
    near[0] = img[0] + img[1]                    # edge rows count themselves twice
    near[-1] = img[-2] + img[-1]
    near[:, 1:-1] += img[:, :-2] + img[:, 2:]    # pixel left + pixel right
    if wrap_x:
        near[:, 0] += img[:, -1] + img[:, 1]
        near[:, -1] += img[:, -2] + img[:, 0]
    else:
        near[:, 0] += img[:, 0] + img[:, 1]
        near[:, -1] += img[:, -2] + img[:, -1]
    near *= 0.25                                 # average of the 4 neighbors
    near -= img
    near *= amount
    img += near
    return img


def sample_bilinear(img, sx, sy):
    """Read img at fractional pixel positions (arrays sx, sy), blending the 4 nearest
    pixels. Positions outside the image are clamped to the edge."""
    h, w = img.shape[:2]
    sx = np.clip(sx, 0.0, w - 1.001)
    sy = np.clip(sy, 0.0, h - 1.001)
    x0 = sx.astype(np.int32)
    y0 = sy.astype(np.int32)
    fx = (sx - x0)[..., None]
    fy = (sy - y0)[..., None]
    top = img[y0, x0] * (1.0 - fx) + img[y0, x0 + 1] * fx
    bottom = img[y0 + 1, x0] * (1.0 - fx) + img[y0 + 1, x0 + 1] * fx
    return top * (1.0 - fy) + bottom * fy


class ZoomFeedback:
    """Classic video feedback for a square image: each frame the previous picture is
    scaled and rotated around the center. zoom > 1 makes trails fly outward,
    zoom < 1 pulls them inward; angle (radians per frame) makes them swirl."""

    def __init__(self, size):
        c = np.arange(size, dtype=np.float32) - (size - 1) / 2.0
        self.x, self.y = np.meshgrid(c, c)
        self.center = (size - 1) / 2.0

    def apply(self, img, zoom, angle):
        cos_a = np.cos(angle) / zoom
        sin_a = np.sin(angle) / zoom
        sx = self.x * cos_a + self.y * sin_a + self.center
        sy = -self.x * sin_a + self.y * cos_a + self.center
        return sample_bilinear(img, sx, sy)


def ring(distance_map, radius, thickness):
    """1.0 where distance_map equals radius, fading to 0 over `thickness`.
    Gives anti-aliased outlines; use with a radius map for circles or with
    polygon_distance() for polygons."""
    return np.clip(1.0 - np.abs(distance_map - radius) / max(thickness, 1e-4), 0.0, 1.0)


def polygon_distance(radius_map, angle_map, sides, rotation=0.0):
    """Turn polar coordinates into a 'polygon radius': the regular polygon with
    `sides` corners and corner radius R is exactly where this map equals R."""
    sector = 2.0 * np.pi / sides
    a = (angle_map - rotation) % sector - sector / 2.0
    return radius_map * np.cos(a) / np.cos(sector / 2.0)


def add_dots(img, xs, ys, colors, wrap_x=True):
    """Add tiny anti-aliased dots at fractional positions (each spreads over its 4
    nearest pixels). colors is one (r, g, b) or an array shaped (N, 3)."""
    h, w = img.shape[:2]
    xs = np.asarray(xs, dtype=np.float32)
    ys = np.asarray(ys, dtype=np.float32)
    if xs.size == 0:
        return img
    colors = np.broadcast_to(np.asarray(colors, dtype=np.float32), (xs.size, 3))
    x0 = np.floor(xs).astype(np.int64)
    y0 = np.floor(ys).astype(np.int64)
    fx, fy = xs - x0, ys - y0
    # The 4 pixels around every dot, and how much of the dot each one receives
    px = np.concatenate([x0, x0 + 1, x0, x0 + 1])
    py = np.concatenate([y0, y0, y0 + 1, y0 + 1])
    weight = np.concatenate([(1 - fx) * (1 - fy), fx * (1 - fy), (1 - fx) * fy, fx * fy])
    rgb = np.tile(colors, (4, 1))
    if wrap_x:
        px %= w
    ok = (py >= 0) & (py < h) & (px >= 0) & (px < w)
    flat = (py * w + px)[ok]
    weight, rgb = weight[ok], rgb[ok]
    for channel in range(3):     # bincount adds up all dots landing on the same pixel (fast)
        total = np.bincount(flat, weights=weight * rgb[:, channel], minlength=h * w)
        img[..., channel] += total.reshape(h, w).astype(np.float32)
    return img


def _radial_patch(img, cx, cy, reach, wrap_x):
    """Pixel rows, columns and distances for the square of pixels within `reach` of (cx, cy)."""
    h, w = img.shape[:2]
    x_idx = np.arange(int(np.floor(cx - reach)), int(np.ceil(cx + reach)) + 1)
    y_idx = np.arange(max(int(np.floor(cy - reach)), 0), min(int(np.ceil(cy + reach)) + 1, h))
    if wrap_x:
        columns = x_idx % w
    else:
        keep = (x_idx >= 0) & (x_idx < w)
        x_idx = x_idx[keep]
        columns = x_idx
    dx = (x_idx - cx)[None, :]
    dy = (y_idx - cy)[:, None]
    return y_idx, columns, np.sqrt(dx * dx + dy * dy)


def add_glow(img, cx, cy, radius, color, falloff=2.0, wrap_x=True):
    """Add a soft round glow centered at (cx, cy). Only touches nearby pixels (fast).
    falloff > 1 gives a tighter, hotter center."""
    rows, columns, dist = _radial_patch(img, cx, cy, radius, wrap_x)
    if rows.size == 0 or columns.size == 0:
        return img
    weight = np.clip(1.0 - dist / max(radius, 1e-3), 0.0, 1.0) ** falloff
    img[np.ix_(rows, columns)] += weight[..., None] * np.asarray(color, dtype=np.float32)
    return img


def add_ring(img, cx, cy, radius, thickness, color, wrap_x=True):
    """Add a soft circle outline centered at (cx, cy)."""
    rows, columns, dist = _radial_patch(img, cx, cy, radius + thickness, wrap_x)
    if rows.size == 0 or columns.size == 0:
        return img
    weight = ring(dist, radius, thickness)
    img[np.ix_(rows, columns)] += weight[..., None] * np.asarray(color, dtype=np.float32)
    return img
