"""
audio_input.py - reads the microphone continuously in the background.

PyAudio calls AudioInput._callback from its own thread each time the sound card
delivers a block of samples. We keep the most recent samples in a ring buffer, and
the main loop grabs a copy whenever it wants to analyze. The main loop never waits
on the microphone.

FakeAudioInput synthesizes a beat (kick, bassline, chord stabs, hi-hats) so the
visuals can be developed without a mic, or on a computer without PyAudio.
"""
import threading
import time

import numpy as np


class SampleBuffer:
    """Fixed-size ring buffer holding the newest audio samples."""

    def __init__(self, size):
        self.data = np.zeros(size, dtype=np.float32)
        self.pos = 0                      # where the next sample will be written
        self.lock = threading.Lock()

    def write(self, samples):
        size = len(self.data)
        with self.lock:
            if len(samples) >= size:
                self.data[:] = samples[-size:]
                self.pos = 0
                return
            end = self.pos + len(samples)
            if end <= size:
                self.data[self.pos:end] = samples
            else:
                first = size - self.pos
                self.data[self.pos:] = samples[:first]
                self.data[:end - size] = samples[first:]
            self.pos = end % size

    def read(self):
        """Copy of the buffer, oldest sample first."""
        with self.lock:
            return np.roll(self.data, -self.pos)


class AudioInput:
    def __init__(self, device=None, sample_rate=None, channels=1, chunk=512, buffer_size=2048):
        import pyaudio   # imported here so --fake-audio works without PyAudio installed

        self._pyaudio = pyaudio
        self.pa = pyaudio.PyAudio()
        self.overflows = 0
        self.last_data_time = time.monotonic()    # updated whenever the mic delivers samples
        try:
            self.device_index = find_input_device(self.pa, device)
            info = self.pa.get_device_info_by_index(self.device_index)
            self.device_name = info["name"]
            self.channels = max(1, min(int(channels), int(info["maxInputChannels"])))
            self.sample_rate = pick_sample_rate(self.pa, self.device_index, self.channels,
                                                sample_rate, info)
            self.buffer = SampleBuffer(buffer_size)
            self.stream = self.pa.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=self.device_index,
                frames_per_buffer=chunk,
                stream_callback=self._callback,
            )
            self.stream.start_stream()
        except Exception:
            self.pa.terminate()
            raise

    def _callback(self, in_data, frame_count, time_info, status_flags):
        # Runs on PyAudio's thread: convert 16-bit integers to floats in -1..1.
        samples = np.frombuffer(in_data, dtype=np.int16).astype(np.float32) / 32768.0
        if self.channels > 1:
            samples = samples.reshape(-1, self.channels).mean(axis=1)
        if status_flags:
            self.overflows += 1      # the sound card had to drop samples
        self.buffer.write(samples)
        self.last_data_time = time.monotonic()
        return (None, self._pyaudio.paContinue)

    def get_samples(self):
        """The newest samples (oldest first) as float32 values in -1..1."""
        return self.buffer.read()

    def seconds_since_data(self):
        """How long ago the mic last delivered samples (grows if it's unplugged)."""
        return time.monotonic() - self.last_data_time

    def close(self):
        try:
            self.stream.stop_stream()
            self.stream.close()
        finally:
            self.pa.terminate()


def find_input_device(pa, wanted=None):
    """Choose an input device. wanted = None (auto), a device index, or part of its name."""
    inputs = []
    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        if int(info.get("maxInputChannels", 0)) > 0:
            inputs.append((i, info["name"]))
    if not inputs:
        raise RuntimeError("No audio input devices found. Is the USB mic plugged in?")

    if isinstance(wanted, int):
        if wanted in [i for i, _ in inputs]:
            return wanted
        raise RuntimeError(f"Audio device {wanted} is not an input. Inputs: {inputs}")
    if isinstance(wanted, str):
        for i, name in inputs:
            if wanted.lower() in name.lower():
                return i
        raise RuntimeError(f"No input device name contains '{wanted}'. Inputs: {inputs}")

    for i, name in inputs:            # auto: prefer anything that looks like a USB mic
        if "usb" in name.lower():
            return i
    try:
        return int(pa.get_default_input_device_info()["index"])
    except OSError:
        return inputs[0][0]


def pick_sample_rate(pa, device_index, channels, wanted, info):
    """Return the first sample rate the device accepts, trying the requested one first."""
    import pyaudio

    candidates = []
    if wanted:
        candidates.append(int(wanted))
    candidates.append(int(info.get("defaultSampleRate", 48000)))
    candidates += [48000, 44100, 32000, 22050, 16000]
    for rate in candidates:
        try:
            if pa.is_format_supported(rate, input_device=device_index,
                                      input_channels=channels, input_format=pyaudio.paInt16):
                return rate
        except ValueError:            # PyAudio raises ValueError for unsupported formats
            continue
    raise RuntimeError("The audio device doesn't accept any common sample rate.")


class FakeAudioInput:
    """Synthetic music for testing visuals without a microphone.
    124 BPM: kick drum, offbeat bassline, chord stabs and 16th-note hi-hats. Every
    third 8-bar section is a breakdown (no kick or bass) so quiet moments show up too."""

    def __init__(self, sample_rate=48000, buffer_size=2048):
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self.device_name = "fake audio (synthetic beat)"
        self.overflows = 0
        self.rng = np.random.default_rng(1)
        self.start = time.perf_counter()
        self.clock = None     # tools can set a function returning the current time in seconds

    def get_samples(self):
        now = self.clock() if self.clock else time.perf_counter() - self.start
        t = now - np.arange(self.buffer_size)[::-1] / self.sample_rate   # oldest first
        return synthesize_beat(t, self.rng)

    def seconds_since_data(self):
        return 0.0            # fake audio never stalls

    def close(self):
        pass


def synthesize_beat(t, rng):
    """Build a drum-and-synth loop for the time values in t (seconds). Returns float32."""
    two_pi = 2.0 * np.pi
    beat = 60.0 / 124.0
    bar = 4 * beat
    section = np.floor(t / (8 * bar)) % 3             # 0, 1 = full groove, 2 = breakdown
    groove = np.where(section == 2, 0.0, 1.0)

    # Kick: pitch drops from ~110 Hz to 45 Hz with a fast decay
    pb = t % beat
    kick_phase = two_pi * (45.0 * pb + 65.0 * (1.0 - np.exp(-35.0 * pb)) / 35.0)
    kick = np.sin(kick_phase) * np.exp(-pb * 16.0) * groove

    # Bassline on the offbeats, cycling through four notes per bar
    notes = np.array([55.0, 55.0, 65.41, 49.0])
    note = notes[(np.floor(t / bar) % 4).astype(int)]
    po = (t + beat / 2) % beat
    bass = np.tanh(3.0 * np.sin(two_pi * note * t)) * np.exp(-po * 7.0) * groove

    # Chord stabs (A major) on every third 8th note
    p8 = t % (beat / 2)
    stab_on = (np.floor(t / (beat / 2)) % 3) == 2
    chord = (np.sin(two_pi * 440.0 * t) + np.sin(two_pi * 554.37 * t)
             + np.sin(two_pi * 659.25 * t)) * np.exp(-p8 * 9.0) * stab_on

    # Hi-hats: high-passed noise on 16th notes
    p16 = t % (beat / 4)
    noise = rng.standard_normal(len(t))
    hats = np.diff(noise, prepend=0.0) * np.exp(-p16 * 55.0)

    mix = 0.8 * kick + 0.3 * bass + 0.12 * chord + 0.25 * hats
    return np.clip(mix, -1.0, 1.0).astype(np.float32)
