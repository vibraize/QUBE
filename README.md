# QUBE

An audio-reactive LED cube: four 40×40 LED panels form the vertical faces of a cube, driven by a
Raspberry Pi 3B listening through a USB microphone. The sound is split into frequency bands, and
each band drives colour, size and movement in fluid, feedback-style visuals.

  -- All electronics work done by myself. Software code written with help from Claude Opus 5; and edited, toyed with, and verified by myself.

  -- All 3D design and model work for the housing was done by my lovely fiance, so I did not include those files, but they are available on request if you are building the same one.

The six bands are bass, mid and high, each split in two for finer control (bass/bassMid, mid/midHigh,
high/highTop). Together they cover 40 Hz to 8 kHz, the top of the microphone's rated range. Their
ranges are set in `config.py` and their colours in `colors.py`.

**The panels are not HUB75.** They're 28-pin, 5-band panels with no public datasheet, driven here by a
patched build of [rpi-rgb-led-matrix](https://github.com/hzeller/rpi-rgb-led-matrix). If you have
similar odd panels, [WIRING.md](WIRING.md) documents how they were worked out from scratch.

### Features

- Six visuals, plus any you add: every mode file dropped into `visuals/` is picked up automatically
- Optional post effects for any visual, each switched on with one line: a rainbow hue cycle and an RGB
  colour delay
- Six frequency bands for colour and movement, plus the sound wave itself, held still like an
  oscilloscope
- Real-time FFT band analysis and beat detection, tuned for a Raspberry Pi 3B
- Runs headless: starts at power-up, recovers from crashes and freezes on its own
- Lights up at boot with a red, green and blue check, so you can see it's ready from a distance
  (or boots dark and waits for a button, if you'd rather)
- Controlled by an ordinary wireless presenter (clicker): modes, LEDs on/off, and a QR code
- A browser preview that runs on any computer, no hardware needed

### Documentation

| File | What's in it |
|---|---|
| [BOM.md](BOM.md) | every part, with part numbers, and the power budget |
| [WIRING.md](WIRING.md) | the Pi → panel pin map, how the panels behave, the library patch, and troubleshooting |
| [PI_SETUP.md](PI_SETUP.md) | step-by-step Raspberry Pi setup, from a blank card to running at boot |

---

## Status

| Area | Status |
|---|---|
| Audio analysis and beat detection | ✅ Working with a USB mic on the Pi. The tuning values in `config.py` are a starting point for your own space. |
| Visuals, QR code, presenter control | ✅ Working on the panels |
| Driving the 28-pin panels | ✅ Working with the patched LED library. Tested with three panels chained; configured for four. |
| Starting at boot, crash and freeze recovery | ✅ Working as a systemd service |
| Level-shifter adapter | ⏳ Not built yet. The panels currently run straight off the Pi's 3.3 V GPIO over short wires (see [WIRING.md](WIRING.md)). |
| Power | ⏳ Full red measured at about 5 W per panel; green, blue and white still to measure. A per-supply power limit keeps each USB-C port within its budget. Two ports with two panels each is the plan, not yet tested. |
| Wired buttons | ⏳ Written but untested |

---

## Quick start: preview on a computer

No microphone or panels needed. From the project folder:

```bash
python3 -m pip install -r requirements.txt
```

```bash
python3 main.py --fake-audio
```

On Windows, use `py` instead of `python3`. Then open **http://localhost:8080** in a browser: all four
faces, the band levels, and buttons for Prev / Next / LEDs on/off / QR code / Restart. The
**Panel 40x40** tab shows one face as an LED grid. After editing a visual, restart `main.py` to load
the changes. Stop with `Ctrl+C`.

`--fake-audio` plays a built-in synthetic beat. To use a real microphone on the computer, also install
`pyaudio`.

---

## On the Raspberry Pi

Set it up with **[PI_SETUP.md](PI_SETUP.md)**. After that, from the project folder on the Pi:

| Command | What it does |
|---|---|
| `sudo python3 main.py --display matrix` | the LED panels |
| `sudo python3 main.py --display web` | a browser preview at http://qube.local:8080 instead |
| `sudo python3 tools/test_pattern.py` | panel test patterns: face order, orientation, colours, dead pixels |
| `sudo python3 tools/panel_poke.py` | talk to a panel directly, without the LED library — for checking wiring |
| `sudo python3 tools/power_test.py` | what a panel draws in each colour, for the power limit ([BOM.md](BOM.md#measuring)) |
| `python3 tools/benchmark.py` | how fast each visual runs |
| `sudo python3 tools/remote_keys.py` | which keys a presenter's buttons send |
| `sudo python3 tools/pi_report.py` | a summary of the Pi's setup |

`sudo` is needed for the LED panels and to read the presenter.

### Command-line options

| Option | What it does |
|---|---|
| `--display web / matrix / none` | browser preview / LED panels / no picture |
| `--mode 1` or `--mode river` | start in a mode (number or part of the name). `--mode qr` = the QR code |
| `--leds on / off` | start with the LEDs on or off, overriding `START_WITH_LEDS_OFF`. It only applies to this start: after a restart from the square button, the remembered state decides |
| `--chain 3` | how many panels are chained right now, overriding `config.py` for one run |
| `--matrix pwm_bits=8` | change one `MATRIX_OPTIONS` setting for one run, for trying panel timings without editing `config.py`. Use it again for more: `--matrix pwm_bits=8 --matrix show_refresh_rate=1` |
| `--fake-audio` | synthetic beat instead of the mic |
| `--audio-device 2` | pick a mic by number or name |
| `--seconds 60` | stop after 60 seconds |
| `--no-cycle` | never switch modes automatically, even if `AUTO_CYCLE_SECONDS` is set |

### Controls

| Presenter button | Action |
|---|---|
| Up arrow | previous mode |
| Down arrow | next mode |
| Black screen (square) | **LEDs off**, with the Pi and the program still running. Press again and the LEDs come back on **and the program restarts from the top**: one button for both. |
| Full screen (double square) | **QR code on/off.** Shows a scannable link on every face; press again to return to the visual you were on. |

- **Terminal keys** (also over SSH): `n`/space = next, `p` = previous, `0`–`9` = pick a mode,
  `l` = LEDs off (on again restarts), `c` = QR code, `r` = restart, `+`/`-` = brightness, `q` = quit
- **Browser preview:** Prev, Next, LEDs on/off, QR code and Restart buttons
- **At power-up** every pixel shows **red, then green, then blue** for a second each, so you can
  see across a field that booting has finished, and then the first visual starts. Change the
  second with `STARTUP_TEST_SECONDS` in `config.py`, or set it to 0 to skip it. Set
  `START_WITH_LEDS_OFF = True` to boot dark instead and wait for the square button.
- **Modes only change when you press a button.** Set `AUTO_CYCLE_SECONDS` in `config.py` to a number
  of seconds for automatic switching.

**Recovering from problems without touching the Pi:**

- **Turning the LEDs off and back on restarts the program — even if the visuals have frozen**, because
  the presenter is read on its own thread. If a restart doesn't happen cleanly within
  `RESTART_FORCE_SECONDS`, it's forced.
- The LEDs come back **on** after that restart, not dark. The on/off state is kept in a file under
  `/run`, which is wiped at every boot: it survives a restart, but unplugging always starts dark.
- If the mic sends nothing for `AUDIO_STALL_RESTART_SECONDS` (for example it was unplugged and plugged
  back in), the program restarts itself to reconnect it.
- As a boot service, systemd also restarts the program if it crashes, or if it freezes for 30 seconds.

---

## How it works

```
USB mic ──► audio_input.py ──► audio_analysis.py ──► visuals/<mode>.py ──► main.py ──► display/
            (ring buffer,       (FFT, band levels,     (draws one 160×40     (crossfade,   (LED panels,
             background thread)  beats)                 frame)                brightness)   browser, none)

Presenter ──► remote_input.py (background thread) ──► main.py: modes, LEDs off/on + restart, QR code
```

The whole cube is one long **160 × 40** canvas. Face 0 is x = 0–39, face 1 is x = 40–79, and so on,
left to right around the cube as seen from outside. Anything that runs off the right edge of face 3
continues on face 0, so patterns can flow around the cube. Modes that want four identical faces draw
one 40×40 face and tile it.

On the way to the panels, `display/led_matrix.py` fits each 40-pixel face into its panel's 48
shift-register columns (8 per panel have no LEDs attached; see [WIRING.md](WIRING.md)), and applies
`FACE_ORDER`, `FACE_ROTATION` and `FACE_MIRROR` to match how the panels are mounted.

## Project layout

```
├── main.py               start here: the main loop
├── config.py             every setting in one place
├── BOM.md                parts list
├── WIRING.md             pin map, panel behaviour, library patch, troubleshooting
├── PI_SETUP.md           Raspberry Pi setup, step by step
├── LICENSE               MIT license
├── audio_input.py        reads the mic in the background (+ a fake beat for testing)
├── audio_analysis.py     FFT → band levels, beats, spectrum, and the waveform
├── colors.py             the synesthesia palette (edit colours here)
├── layout.py             the cube canvas and per-face helpers
├── controls.py           terminal keyboard controls
├── remote_input.py       the presenter and wired buttons
├── service.py            restarts, the LED state across restarts, the systemd watchdog
├── requirements.txt      packages for running the preview on a computer
├── deploy/
│   ├── install_service.sh   run QUBE automatically at boot
│   └── qube.service         systemd service template
├── display/
│   ├── __init__.py       picks the display, and the per-supply power limit
│   ├── web_preview.py    live browser preview
│   └── led_matrix.py     the LED panels, via the patched rpi-rgb-led-matrix
├── visuals/
│   ├── __init__.py       finds every mode in this folder automatically
│   ├── base.py           base class for modes
│   ├── effects.py        toolbox: fade, hue rotation, colour delay, blur, feedback, rings, polygons, dots, glows
│   ├── ember_bloom.py
│   ├── level_meter.py    the simplest mode, and a template for your own
│   ├── mirror_scope.py   the simplest mode that draws the waveform
│   ├── pulse_tunnel.py
│   ├── radial_waveform.py  draws audio.waveform, the sound wave itself
│   ├── spectrum_river.py
│   └── qr_code.py        the QR code, on its own button
└── tools/
    ├── patch_rgbmatrix.py      patches rpi-rgb-led-matrix for these panels
    ├── panel_poke.py           drives a panel directly, no library needed
    ├── test_pattern.py         panel bring-up patterns
    ├── power_test.py           measures a panel's draw per colour, for the power limit
    ├── make_qr.py              rebuilds the QR code for a different link
    ├── pi_report.py            summary of the Pi's setup
    ├── benchmark.py            times every visual
    ├── remote_keys.py          shows which keys a presenter sends
    ├── list_audio_devices.py   shows mics and the sample rates they support
    └── render_frames.py        renders modes to PNG images using the fake beat
```

---

## Visual modes

**Every `.py` file in `visuals/` with a mode in it is picked up automatically** — nothing to register.
The up/down buttons step through them in this order, which is alphabetical by name:

| # | Mode | What you see |
|---|---|---|
| 0 | **Ember Bloom** | Particles with smoky trails. Beats burst blooms on alternating face pairs (0+2, then 1+3): red when the bass is louder, yellow when the bassMid is. Mids drift as green (mid) and cyan (midHigh) orbs, highs flicker as blue (high) and magenta (highTop) sparks. |
| 1 | **Level Meter** | Six bars per face in the band colours, bass at the bottom up to highTop on top. They grow sideways out of two opposite edges of the cube (faces 1 and 3 are mirrored), and a white border flashes on beats. Also the mode to use when tuning the mic. |
| 2 | **Mirror Scope** | A basic oscilloscope, mirrored top to bottom: the sound wave and its reflection open and close symmetrically around the middle, with short phosphor-like trails. Colour follows where the sound sits in the spectrum; bass thickens the line and beats brighten it. The simplest example of drawing `audio.waveform`. |
| 3 | **Pulse Tunnel** | Square outlines pulse out of the centre of each face with video-feedback trails. Bass = size, a red outline and shockwave rings on beats; bassMid = a yellow outline inside it, turning the other way. Mids = swirl and a green star, with a cyan ring (midHigh) at its centre. Highs = blue (high) and magenta (highTop) sparkles. Faces 1 and 3 are mirrored. |
| 4 | **Radial Waveform** | The sound wave itself, wrapped into rings. An outer red ring pushed out by bass and beats, an inner green ring spinning the other way with the mids, a thin cyan ring between them for the midHigh, blue (high) and magenta (highTop) sparkles riding the outer ring, and a yellow centre dot (bassMid) that pulses on beats. |
| 5 | **Spectrum River** | Six glowing ribbons flow around the whole cube, one per band: a thick, slow red bass ribbon at the bottom, then yellow, green, cyan and blue, up to a thin, fast magenta highTop ribbon on top. Beats send a red pulse racing around the cube. |
| – | **QR Code** | A still QR code on every face, on its own button and out of the rotation. It's baked into `visuals/qr_code.py` so the Pi needs no QR library; point it at a different link with `tools/make_qr.py`. |

All six also run the hue cycle: every 10 seconds, all their colours turn once round the colour wheel
together, starting from the colours above. To keep a mode in those colours, delete the
`hue_cycle_seconds = 10` line under its `name`.

See what a mode looks like without running it live (writes PNGs into `renders/`):

```bash
python3 tools/render_frames.py --mode river --seconds 8 --every 1
```

---

## Make your own visual mode

1. Copy `visuals/level_meter.py` to `visuals/my_mode.py`.
2. Rename the class and `name`.
3. Write `draw(self, audio, dt)`. It returns a float32 numpy array shaped
   `(self.height, self.width, 3)` with values from 0 to 1.

**That's it** — QUBE finds the file on its own and the buttons include it. Four optional class
settings, each one line under `name`:

| Setting | What it does |
|---|---|
| `hue_cycle_seconds = 10` | turns every colour the mode draws all the way round the colour wheel once every 10 seconds, keeping brightness and saturation. Any number of seconds works; negative turns the other way. Off (`0`) by default; the built-in visuals set it to 10. |
| `rgb_delay = (0.3, 0.2, 0.1)` | colour delay: red shows the picture from 0.3 s ago, green from 0.2 s, blue from 0.1 s, so anything moving leaves coloured fringes — even a grey picture turns colourful. Still parts don't change. Off (`None`) by default; applied after the hue cycle. |
| `order = <number>` | moves the mode earlier in the rotation (lower comes first) |
| `cycle = False` | keeps it out of the rotation, so only `--mode` or its own button reaches it |

```python
class MyMode(VisualMode):
    name = "My Mode"
    hue_cycle_seconds = 10        # a full rainbow every 10 seconds
```

The hue cycle turns *everything* the mode draws, so a mode built on the synesthesia palette stops
keeping bass red while it's on. To turn only part of a picture, call the effect directly on one layer
in `draw()`: `layer = hue_rotate(layer, self.time * 36)` (36 degrees a second = once every 10 s).
It adds roughly 2 ms a frame on a Pi 3B (estimated from timings on a PC).

A file in `visuals/` that fails to import (a typo, say) is reported and skipped, so an unfinished
experiment can't stop the cube from starting.

A complete tiny mode, where the whole cube flashes in the bass colour on every beat:

```python
import numpy as np
from colors import bass_color
from visuals.base import VisualMode

class BassFlash(VisualMode):
    name = "Bass Flash"

    def draw(self, audio, dt):
        frame = np.zeros((self.height, self.width, 3), dtype=np.float32)
        frame[:] = bass_color(audio.bass) * audio.beat_pulse
        return frame
```

**What `audio` gives you** (smoothed; each band is compared with its own normal level):

| Field | Range | Meaning |
|---|---|---|
| `audio.bass`, `audio.bassMid`, `audio.mid`, `audio.midHigh`, `audio.high`, `audio.highTop` | 0–1 | six band levels |
| `audio.volume` | 0–1 | overall loudness |
| `audio.beat` | True/False | True only on the frame a bass hit is detected |
| `audio.beat_pulse` | 0–1 | jumps to 1 on a beat, then fades (great for pulses) |
| `audio.spectrum` | array of 16, 0–1 | narrow bands from lowest to highest |
| `audio.brightness` | 0–1 | where the active sound sits (0 = bassy, 1 = trebly) |
| `audio.silent` | True/False | the room is basically quiet |
| `audio.waveform` | array of 128, −1–1 | **the sound wave itself, ready to draw**: held still like an oscilloscope, smoothed, and scaled to fill the space. Flat when silent. |
| `audio.raw_samples` | array, −1–1 | the raw samples the FFT just analysed, oldest first. Music at a microphone is tiny here (peaks of a few thousandths), so draw `audio.waveform` instead |

**Drawing the waveform.** `audio.waveform` is made in three steps, in `_waveform()` in
`audio_analysis.py`:

1. **Trigger.** It starts at the most recent upward zero crossing, the way an oscilloscope does, so a
   steady note holds still instead of jittering. On a test tone that makes it about 50× steadier.
2. **Smooth.** `WAVEFORM_SECONDS` of sound are averaged down to `WAVEFORM_POINTS` values, removing hiss
   a 40-pixel face couldn't show anyway.
3. **Auto-gain.** It's divided by a slowly tracked peak, so quiet music still fills the space while
   loud and quiet passages look different for a moment as the peak catches up. Sound just above the
   silence gate draws small rather than full size.

To wrap it into a ring, as Radial Waveform does, interpolate around the circle with
`np.interp(..., period=2 * np.pi)` and ease both ends to zero so the ring closes without a notch —
see `visuals/radial_waveform.py`.

**Helpers:**
- `colors.py`: `bass_color(level)`, `bass_mid_color(level)`, `mid_color(level)`,
  `mid_high_color(level)`, `high_color(level)`, `high_top_color(level)`,
  `spectrum_color(position)`, `sound_color(audio)`
- `visuals/effects.py`: `fade`, `hue_rotate`, `RgbDelay`, `blur`, `ZoomFeedback`, `ring`, `polygon_distance`, `add_dots`, `add_glow`, `add_ring`, `sample_bilinear`
- `layout` (available as `self.layout`): `face_grid()`, `strip_grid()`, `tile(face_image, mirror_alternate)`, `face_view(canvas, i)`

Tips for the Pi 3B: always work on whole numpy arrays (never loop over pixels in Python), and use `dt`
for movement and fades so speed doesn't depend on the frame rate. Check with `python3 tools/benchmark.py`.

---

## Tuning the audio (config.py)

Run `sudo python3 main.py --display web --mode meter` near your sound source and watch the bars and the
`mic __ dB` readout.

| Setting | Change it when... |
|---|---|
| `SILENCE_DB` | visuals react to room noise (raise it) or ignore quiet music (lower it). Set it between your quiet-room and quiet-music `mic dB` readings. |
| `INPUT_GAIN_DB` | the mic is very quiet or clipping. Also check the mic's capture level in `alsamixer` (`F6` = pick the mic, `F4` = capture). |
| `LEVEL_RANGE_DB` | bars barely move (smaller = more sensitive) or sit at full too often (bigger) |
| `CONTRAST_DB` | bars still move together (smaller) or one band disappears in busy music (bigger) |
| `BACKGROUND_RISE_SECONDS` | long, steady notes fade from the bars too quickly (bigger) or stay lit too long (smaller) |
| `BEAT_THRESHOLD_DB` | beats are missed (lower) or trigger too often (higher) |
| `BEAT_MIN_BASS_SHARE_DB` | non-bass sounds trigger beats (raise toward -6) |
| `RELEASE_SECONDS` | levels drop too fast or too slowly after a hit |
| `BASS_RANGE` through `HIGH_TOP_RANGE`, `SPECTRUM_RANGE` | you want different band splits |
| `WAVEFORM_SECONDS` | the waveform shows too few wiggles (longer) or looks like noise (shorter) |
| `WAVEFORM_POINTS` | the waveform looks too blocky (more) or too jagged (fewer) |

The microphone in the parts list is rated for up to 100 dB SPL. Right next to big speakers it may be
pushed past that; if the visuals stop following the music, move the mic further from the speakers.
The colours for each band live at the top of `colors.py`.

---

## Remote control

**A wireless presenter (clicker).** One with a plug-in USB receiver, rather than Bluetooth, shows up
on the Pi as a small keyboard, so there's nothing to pair. `remote_input.py` reads it on a background
thread (needs `python3-evdev`, and `sudo`). The default `REMOTE_KEYS` match the presenter in
[BOM.md](BOM.md). For a different one:

1. Run `sudo python3 tools/remote_keys.py`, press each button, then `Ctrl+C`.
2. Put the key names it shows into `REMOTE_KEYS` in `config.py`.
3. Optionally, set `REMOTE_DEVICE_NAME` to part of the receiver's name (the tool shows it). Then only
   that receiver is listened to, and its presses stop also typing into the Pi's console.

If the range is poor with the receiver inside the cube, a short USB extension cable lets you put it
outside the panels.

**Wired buttons (optional, untested).** A momentary button between a free GPIO pin and GND, for example
on QUBE's pole: set its pin in `GPIO_BUTTONS` in `config.py`. Pick from the pins
[WIRING.md](WIRING.md) lists as free. Needs gpiozero (`sudo apt install python3-gpiozero`).

---

## Running at boot

```bash
sudo bash deploy/install_service.sh matrix
```

This installs a systemd service called `qube` that runs as root, starts at boot with the LEDs off,
and:

- starts the program again whenever it exits or crashes (`Restart=always`, and it never gives up),
- restarts it if it freezes: the main loop pings systemd, and if the pings stop for 30 seconds, systemd
  restarts it (`WatchdogSec=30`).

| Command | What it does |
|---|---|
| `journalctl -u qube -f` | watch its output |
| `sudo systemctl restart qube` | restart it |
| `sudo systemctl stop qube` | stop it until the next boot |
| `sudo systemctl disable --now qube` | stop it and don't start it at boot |

Stop the service before running `main.py` by hand, or the two copies fight over the panels and the mic.
Use `web` instead of `matrix` to run the browser preview as the service. If the LED library is
installed in a Python virtual environment, install the service with
`sudo PYTHON=/path/to/venv/bin/python3 bash deploy/install_service.sh matrix`.

---

## Hardware

Full parts list with part numbers: **[BOM.md](BOM.md)**. Wiring and everything known about the panels:
**[WIRING.md](WIRING.md)**. In brief:

- **Four DI-P6.4F03M-8CS-2.7 panels**: 40×40 pixels at 6.4 mm pitch, 256 mm square, 1/8 scan, arranged
  internally as 5 bands of 8 rows with separate red, green and blue data lines per band. A 2×14
  (28-pin) input and output instead of HUB75.
- **Both power rails want 5 V**: VCC feeds the panel's logic and VDD its LEDs, each on its own wire.
- **Pin 28 (SR) must be held high** on every panel, or it stays dark. It's a fixed level, not a signal.
- **LAT and SR go from the Pi to every panel.** Neither travels along the chain; only the data does.
- **Each panel is 48 shift-register columns wide but only 40 have LEDs**, so the library runs with
  `cols: 48` and `PANEL_COLUMN_OFFSET` says where the 40 visible columns sit.
- **Canvas column 0 lands on the panel furthest from the Pi**, because the first pixel clocked out
  travels furthest down the chain. `FACE_ORDER` maps faces to panels from there.
- **Power** comes from a USB-C Power Delivery power bank through two trigger boards set to 5 V: two
  panels on each USB-C port, which gives 15 W at 5 V. A panel at full red measured about 5 W, and full
  white could be around three times that, so a power limit estimates what every frame will draw from
  each supply and dims the picture if one would go over. Settings and how to measure:
  [BOM.md](BOM.md#power-budget).

### Why a standard HUB75 adapter can't drive them

A HUB75 output carries 6 colour data lines, for the top and bottom halves of one chain. These panels
need 15. The LED library's "parallel chains" share clock, latch, output enable and row address while
keeping separate colour lines per chain — which matches the 5 bands exactly — but it allows only 3
chains and assumes two halves per chain. `tools/patch_rgbmatrix.py` lifts both limits for this panel's
pin map only.

### To do

1. **Test all four panels chained.** Three have run together; the settings are for four.
2. **Check the picture geometry** with `sudo python3 tools/test_pattern.py`, and set `FACE_ORDER`,
   `FACE_ROTATION`, `FACE_MIRROR` and `PANEL_COLUMN_OFFSET` from what you see.
3. **Build the level-shifter adapter** — 3× 74AHCT245 at 5 V between the Pi and the panels, with
   latching connectors, feeding LAT and SR to every panel. Jumper wires won't survive a festival.
4. **Measure the power** with `sudo python3 tools/power_test.py`, fill in `PANEL_FULL_WATTS` and
   `LED_WATTS_PER_SUPPLY`, and set `POWER_SUPPLIES` for two ports. Then raise `MASTER_BRIGHTNESS`
   ([BOM.md](BOM.md#measuring)).
5. **Test the wired buttons.**

---

## Troubleshooting

| Problem | Try |
|---|---|
| `Couldn't open the microphone` | `python3 tools/list_audio_devices.py`, `arecord -l`, set `AUDIO_DEVICE` or `--audio-device` |
| Sample rate errors | set `SAMPLE_RATE` to a rate the device-list tool shows |
| Lots of `ALSA lib ...` messages | harmless, printed when PyAudio starts on the Pi |
| Presenter does nothing | run with `sudo`; check `sudo python3 tools/remote_keys.py`; update `REMOTE_KEYS`; `sudo apt install python3-evdev` |
| QUBE doesn't respond at power-up | with `START_WITH_LEDS_OFF = True` it's dark on purpose: press the square button. Otherwise the panels show red, green and blue while it starts |
| `Web preview can't use port 8080` | another copy is already running (for example the boot service): stop it, or change `WEB_PREVIEW_PORT` |
| Browser preview won't load | same network? If a firewall asks, allow Python |
| Low fps on the Pi | `python3 tools/benchmark.py`, lower `TARGET_FPS`. Level Meter and Mirror Scope are the lightest modes, and deleting a mode's `hue_cycle_seconds` line makes it lighter |
| `Fast drawing failed` (panels) | a Pillow / LED library version mismatch. It falls back automatically, or set `PIXEL_PUSH = "setpixel"` |
| `Parallel outside usable range`, or `There is no hardware mapping named 'qube-28pin'` | the LED library on the Pi wasn't built with this project's current patch: redo [PI_SETUP.md](PI_SETUP.md) step 10 |
| Visuals too flat or too jumpy | see [Tuning the audio](#tuning-the-audio-configpy) |
| A panel stays completely dark | its pin 28 (SR) needs 3.3 V of its own — SR is not carried along the chain |
| A chained panel smears single-column patterns but looks fine on solid ones | its LAT (pin 26) isn't arriving, so its latch never closes. Wire LAT from the Pi to every panel |
| An 8-pixel black stripe down one edge of each panel | switch `PANEL_COLUMN_OFFSET` in `config.py` between 8 and 0 |
| Picture glitches, tears or smears on the panels | raise `gpio_slowdown` in `MATRIX_OPTIONS` (4 is the safest on jumper wires) |
| The whole picture flickers or pulses | the panels are being refreshed too slowly, or their supply is sagging. `--matrix show_refresh_rate=1` prints the rate the library reaches; `--matrix pwm_bits=8` trades colour steps for a faster refresh, and a lower `gpio_slowdown` helps too. For the supply, check what the panels draw against their port's budget ([BOM.md](BOM.md#power-budget)) and lower `MASTER_BRIGHTNESS` |
| The Pi won't boot, or clicks, with the panels wired | a short between a Pi power rail and ground in the wiring — see [WIRING.md](WIRING.md) |
| A USB-C port cuts out on bright scenes | the LEDs drew more than the port gives: check `PANEL_FULL_WATTS` with `tools/power_test.py` and lower `LED_WATTS_PER_SUPPLY` |
| The picture looks dimmer than `MASTER_BRIGHTNESS` should give | the power limit is holding a supply at its budget; `main.py`'s report says how often (`held to … W`) |

---

## Credits and sources

Built on **[rpi-rgb-led-matrix](https://github.com/hzeller/rpi-rgb-led-matrix)** by Henner Zeller
(GPL-2.0), which does the real work of driving the panels. This repository doesn't include its code:
`tools/patch_rgbmatrix.py` patches a fresh clone of it at build time.

- rpi-rgb-led-matrix: [options-initialize.cc](https://github.com/hzeller/rpi-rgb-led-matrix/blob/master/lib/options-initialize.cc) (the parallel-chain limit the patch lifts), [framebuffer.cc](https://github.com/hzeller/rpi-rgb-led-matrix/blob/master/lib/framebuffer.cc) (sub-panels, and the loop that clocks canvas column 0 out first), [hardware-mapping.c](https://github.com/hzeller/rpi-rgb-led-matrix/blob/master/lib/hardware-mapping.c) (where the pin map goes), [Python bindings](https://github.com/hzeller/rpi-rgb-led-matrix/tree/master/bindings/python), [the `Imaging.h` build issue](https://rpi-rgb-led-matrix.discourse.group/t/can-not-find-imaging-h-when-doing-pip3-install-of-bindings-python/1139)
- Debian: [`python3-pil` ships `Imaging.h`](https://packages.debian.org/search?searchon=contents&keywords=Imaging.h&mode=filename&suite=trixie&arch=arm64)
- Adafruit: [HUSB238 #5991 pinouts](https://learn.adafruit.com/adafruit-usb-type-c-power-delivery-switchable-breakout/pinouts), [product 5991](https://www.adafruit.com/product/5991), [Mini USB Microphone, product 3367](https://www.adafruit.com/product/3367), [RGB Matrix Bonnet guide](https://learn.adafruit.com/adafruit-rgb-matrix-bonnet-for-raspberry-pi)
- [TALIX 140W 20000mAh power bank listing](https://www.amazon.com/TALIX-20000mAh-Charging-Portable-Approved/dp/B0GCDB9KTQ)
- Chips: [Macroblock JXI5020](https://www.mblock.com.tw/upload/Datasheet/LED%20Driver%20IC/JXI5020/JXI5020%20Preliminary%20Datasheet%20V2_EN.pdf), [Nexperia 74HC245](https://assets.nexperia.com/documents/data-sheet/74HC_HCT245.pdf), [Nexperia 74AHCT245](https://assets.nexperia.com/documents/data-sheet/74AHC_AHCT245.pdf)
- Connectors: [JST VH series datasheet](https://www.jst-mfg.com/product/pdf/eng/eVH.pdf)
- Raspberry Pi: [getting started / Imager](https://www.raspberrypi.com/documentation/computers/getting-started.html), [power supplies](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html), [pinout.xyz](https://pinout.xyz/)
- systemd: [systemd.service](https://man7.org/linux/man-pages/man5/systemd.service.5.html), [systemd.unit](https://man7.org/linux/man-pages/man5/systemd.unit.5.html), [sd_notify](https://man7.org/linux/man-pages/man3/sd_notify.3.html)
- [python-evdev API](https://python-evdev.readthedocs.io/en/latest/apidoc.html), [PyAudio documentation](https://people.csail.mit.edu/hubert/pyaudio/docs/)

---

## License

QUBE's code and documentation are released under the [MIT License](LICENSE). rpi-rgb-led-matrix,
which QUBE is built with, keeps its own GPL-2.0 license (see above).
