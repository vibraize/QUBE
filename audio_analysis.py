"""
audio_analysis.py - turns raw microphone samples into numbers the visuals can use.

Every frame:
  1. FFT: split the sound into frequencies (numpy.fft.rfft).
    2. Measure loudness (in dB) of six bands and SPECTRUM_BANDS narrow bands.
  3. Compare each band with its own "normal" level, a background that follows the sound
     slowly upward and quickly downward. A band's level shows how far above normal it is
     right now, on a fixed dB scale (LEVEL_RANGE_DB), so a small sound gives a small bar.
  4. Contrast: a band that rose much less than the band that rose most is dimmed. This
     keeps a snap in the highs from dragging the bass bar along with it.
  5. Smoothing: quick rise (attack), slower fall (release).
  6. Beat detection: a "beat" is the bass suddenly jumping above its recent average.

Visual modes receive an AudioFeatures object:
    audio.bass, audio.bassMid, audio.mid, audio.midHigh, audio.high, audio.highTop
                                        0..1 smoothed band levels
    audio.volume                        0..1 overall loudness above normal
    audio.beat                          True only on the frame a bass hit happens
    audio.beat_pulse                    1.0 at a beat, then fades toward 0
    audio.spectrum                      SPECTRUM_BANDS levels 0..1, lowest to highest
    audio.brightness                    0..1, where the active sound sits (0 = bassy, 1 = trebly)
    audio.silent                        True when the room is basically quiet
    audio.waveform                      the sound wave itself, ready to draw: WAVEFORM_POINTS
                                        values in -1..1, held still like an oscilloscope and
                                        scaled to fill the space (see _waveform below)
    audio.raw_samples                   the raw samples the FFT just looked at, -1..1, oldest
                                        first. Real music is tiny here - use audio.waveform
                                        to draw it
    audio.sample_rate                   samples per second of raw_samples
"""
from dataclasses import dataclass, field
import math

import numpy as np


@dataclass
class AudioFeatures:
    bass: float = 0.0
    bassMid: float = 0.0
    mid: float = 0.0
    midHigh: float = 0.0
    high: float = 0.0
    highTop: float = 0.0
    volume: float = 0.0
    beat: bool = False
    beat_pulse: float = 0.0
    brightness: float = 0.5
    silent: bool = True
    spectrum: np.ndarray = field(default_factory=lambda: np.zeros(16, dtype=np.float32))
    waveform: np.ndarray = field(default_factory=lambda: np.zeros(128, dtype=np.float32))
    raw_samples: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.float32))
    sample_rate: int = 48000
    # Raw loudness in dB, for tuning (shown by the Level Meter mode)
    volume_db: float = -120.0
    bass_db: float = -120.0
    bassMid_db: float = -120.0
    mid_db: float = -120.0
    midHigh_db: float = -120.0
    high_db: float = -120.0
    highTop_db: float = -120.0


class BandLevels:
    """Turns loudness values (dB) for a group of bands into smoothed 0..1 levels."""

    def __init__(self, count, release_seconds, cfg, contrast=True):
        self.cfg = cfg
        self.contrast = contrast
        self.background = None                             # each band's "normal" loudness (dB)
        self.level = np.zeros(count, dtype=np.float32)     # smoothed output 0..1
        self.release = np.broadcast_to(np.float32(release_seconds), (count,)).astype(np.float32)

    def update(self, db, dt, silent):
        cfg = self.cfg
        db = np.asarray(db, dtype=np.float32)
        if self.background is None:
            self.background = db.copy()

        # How far above normal each band is, as a fraction of LEVEL_RANGE_DB
        rise = db - self.background
        target = np.clip(rise / cfg.LEVEL_RANGE_DB, 0.0, 1.0)

        # Contrast: dim bands that rose much less than the band that rose most
        if self.contrast:
            target *= np.clip(1.0 - (rise.max() - rise) / cfg.CONTRAST_DB, 0.0, 1.0)
        if silent:
            target[:] = 0.0

        # "Normal" follows the sound: slowly when it gets louder, quickly when it gets quieter
        up = 1.0 - math.exp(-dt / cfg.BACKGROUND_RISE_SECONDS)
        down = 1.0 - math.exp(-dt / cfg.BACKGROUND_FALL_SECONDS)
        self.background += rise * np.where(rise > 0.0, up, down).astype(np.float32)

        # Rise with the attack time, fall with each band's release time
        tau = np.where(target > self.level, cfg.ATTACK_SECONDS, self.release)
        self.level += (target - self.level) * (1.0 - np.exp(-dt / np.maximum(tau, 1e-4)))
        return self.level


def pick_fft_size(sample_rate, wanted):
    """FFT window size in samples: `wanted` if set, else about 40-65 ms of sound."""
    if wanted:
        return int(wanted)
    return 2048 if sample_rate >= 32000 else 1024


class AudioAnalyzer:
    def __init__(self, sample_rate, cfg):
        self.cfg = cfg
        self.sample_rate = int(sample_rate)
        n = self.fft_size = pick_fft_size(sample_rate, cfg.FFT_SIZE)
        self.window = np.hanning(n).astype(np.float32)
        self.scale = 2.0 / self.window.sum()     # a full-scale sine wave reads about 0 dB
        self.gain = 10.0 ** (cfg.INPUT_GAIN_DB / 20.0)
        freqs = np.fft.rfftfreq(n, d=1.0 / sample_rate)

        def bins(f_lo, f_hi):
            lo = min(max(int(np.searchsorted(freqs, f_lo)), 1), len(freqs) - 1)   # skip the DC bin
            hi = min(max(int(np.searchsorted(freqs, f_hi)), lo + 1), len(freqs))
            return lo, hi

        low, high = cfg.SPECTRUM_RANGE
        top = min(float(high), sample_rate / 2.0 * 0.95)     # stay below the Nyquist frequency
        edges = np.geomspace(float(low), top, cfg.SPECTRUM_BANDS + 1)
        ranges = [cfg.BASS_RANGE, cfg.BASS_MID_RANGE, cfg.MID_RANGE, cfg.MID_HIGH_RANGE,
              cfg.HIGH_RANGE, cfg.HIGH_TOP_RANGE] + list(zip(edges[:-1], edges[1:]))
        index = [bins(lo, hi) for lo, hi in ranges]
        self.lo = np.array([i[0] for i in index])
        self.hi = np.array([i[1] for i in index])

        releases = [cfg.RELEASE_SECONDS[name] for name in
                ("bass", "bassMid", "mid", "midHigh", "high", "highTop")]
        self.bands = BandLevels(6, releases, cfg)
        self.spectrum_levels = BandLevels(cfg.SPECTRUM_BANDS,
                                          np.linspace(releases[0], releases[2], cfg.SPECTRUM_BANDS), cfg)
        self.volume = BandLevels(1, cfg.RELEASE_SECONDS["mid"], cfg, contrast=False)
        self.band_positions = np.linspace(0.0, 1.0, cfg.SPECTRUM_BANDS, dtype=np.float32)

        self.bass_average_db = -120.0
        self.previous_bass_db = -120.0
        self.since_beat = 1.0
        self.beat_pulse = 0.0
        self.brightness = 0.5

        # Waveform (see _waveform): how much sound to show, how far back to look for
        # a zero crossing to start on, and the smoothing used to find it
        self.wave_points = int(cfg.WAVEFORM_POINTS)
        self.wave_span = max(self.wave_points, int(cfg.WAVEFORM_SECONDS * sample_rate))
        self.wave_search = self.wave_span
        self.wave_kernel = np.ones(max(1, sample_rate // 2000), dtype=np.float32)
        self.wave_kernel /= self.wave_kernel.sum()
        # Quietest peak we'll scale up to full size: 12 dB above the silence level,
        # so hiss just above it draws a small wobble rather than a full-size wave
        self.wave_floor = 1.41 * 10.0 ** ((cfg.SILENCE_DB + 12.0) / 20.0)
        self.wave_peak = self.wave_floor

    def process(self, samples, dt):
        cfg = self.cfg
        dt = max(dt, 1e-3)
        x = samples[-self.fft_size:] * self.gain
        if len(x) < self.fft_size:
            x = np.pad(x, (self.fft_size - len(x), 0))

        # Overall loudness (RMS, in dB relative to full scale)
        volume_db = 20.0 * math.log10(float(np.sqrt(np.mean(x * x))) + 1e-9)
        silent = volume_db < cfg.SILENCE_DB

        # Frequency analysis: energy per band via a running sum over FFT bins
        magnitude = np.abs(np.fft.rfft(x * self.window)) * self.scale
        cumulative = np.concatenate(([0.0], np.cumsum(magnitude * magnitude)))
        band_db = 10.0 * np.log10(cumulative[self.hi] - cumulative[self.lo] + 1e-12)

        levels = self.bands.update(band_db[:6], dt, silent)
        spectrum = self.spectrum_levels.update(band_db[6:], dt, silent).copy()
        volume = float(self.volume.update(np.array([volume_db], dtype=np.float32), dt, silent)[0])

        # Beat: bass jumps above its recent average, is still rising, and is a real
        # share of the whole sound (so hi-hats or noise can't fake a bass hit)
        bass_db = float(band_db[0])
        total_db = 10.0 * math.log10(float(cumulative[-1]) + 1e-12)
        self.since_beat += dt
        beat = (not silent
                and bass_db - self.bass_average_db > cfg.BEAT_THRESHOLD_DB
                and bass_db > self.previous_bass_db
                and bass_db - total_db > cfg.BEAT_MIN_BASS_SHARE_DB
                and self.since_beat >= cfg.BEAT_COOLDOWN_SECONDS)
        if beat:
            self.since_beat = 0.0
            self.beat_pulse = 1.0
        else:
            self.beat_pulse *= math.exp(-dt / 0.15)
        self.bass_average_db += (bass_db - self.bass_average_db) * (1.0 - math.exp(-dt / 0.5))
        self.previous_bass_db = bass_db

        # Brightness: the level-weighted average position of the active spectrum bands
        total = float(spectrum.sum())
        if total > 1e-3:
            target = float((spectrum * self.band_positions).sum() / total)
            self.brightness += (target - self.brightness) * (1.0 - math.exp(-dt / 0.3))

        return AudioFeatures(
            bass=float(levels[0]), bassMid=float(levels[1]), mid=float(levels[2]),
            midHigh=float(levels[3]), high=float(levels[4]), highTop=float(levels[5]),
            volume=volume, beat=beat, beat_pulse=self.beat_pulse,
            brightness=self.brightness, silent=silent, spectrum=spectrum,
            waveform=self._waveform(samples, dt, silent), raw_samples=x,
            sample_rate=self.sample_rate,
            volume_db=volume_db, bass_db=bass_db, bassMid_db=float(band_db[1]),
            mid_db=float(band_db[2]), midHigh_db=float(band_db[3]),
            high_db=float(band_db[4]), highTop_db=float(band_db[5]),
        )

    def _waveform(self, samples, dt, silent):
        """The sound wave itself, ready to draw: WAVEFORM_POINTS values in -1..1.

        Three steps turn a raw buffer into something worth looking at:
          1. Trigger: start at the most recent upward zero crossing, the way an
             oscilloscope does, so a steady note holds still instead of jittering.
          2. Smooth: average WAVEFORM_SECONDS of sound down to WAVEFORM_POINTS values.
             That removes hiss a 40-pixel face couldn't show anyway.
          3. Auto-gain: divide by a slowly tracked peak. Music at a microphone peaks at
             a few thousandths of full scale, so the raw values would draw a flat line;
             this scales the wave up to fill the space, while loud and quiet passages
             still look different for a moment as the peak catches up.
        """
        span, points = self.wave_span, self.wave_points
        search = max(0, min(self.wave_search, len(samples) - span))
        region = samples[-(span + search):] * self.gain
        if len(region) < span:                         # not enough history yet
            region = np.pad(region, (span - len(region), 0))

        # 1. Trigger on a lightly smoothed copy, so noise can't fake a crossing
        start = search                                 # no crossing found: newest sound
        if search:
            smooth = np.convolve(region[:search + 1], self.wave_kernel, mode="same")
            rising = np.flatnonzero((smooth[:-1] < 0.0) & (smooth[1:] >= 0.0)) + 1
            if len(rising):
                start = int(rising[-1])                # the most recent one
        wave = region[start:start + span]

        # 2. Average down to `points` values
        wave = wave[:points * (span // points)].reshape(points, -1).mean(axis=1)

        # 3. Auto-gain: the peak rises instantly with the sound, then falls slowly
        peak = float(np.abs(wave).max())
        tau = 0.01 if peak > self.wave_peak else 0.8
        self.wave_peak += (peak - self.wave_peak) * (1.0 - math.exp(-dt / tau))
        if silent:
            return np.zeros(points, dtype=np.float32)
        return np.clip(wave / max(self.wave_peak, self.wave_floor), -1.0, 1.0).astype(np.float32)
