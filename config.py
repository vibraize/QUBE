"""
config.py - every setting you are likely to tweak, in one place.

Some of these can also be overridden from the command line, e.g.
    python3 main.py --display web --mode 1 --fake-audio
Run `python3 main.py --help` to see the options.
"""

# =============================================================================
# CANVAS LAYOUT (the cube)
# =============================================================================
FACE_SIZE = 40      # pixels per side of one panel face (the P6.4 panels in BOM.md are 40x40)
NUM_FACES = 4       # four vertical faces, no top or bottom

# Visual modes draw onto one long strip: width = FACE_SIZE * NUM_FACES, height = FACE_SIZE.
# Face 0 is x = 0..39, face 1 is x = 40..79, and so on around the cube.

# Physical mounting fixes. These are applied right before pixels go to the panels,
# so visual modes never have to care how the panels are bolted on.
# FACE_ORDER[i] = canvas face shown in slot i, counting from the LEFT as you look at
# the cube from outside. Left to right is also chain order backwards: the LED library
# clocks canvas column 0 out first, and the first pixel clocked travels furthest along
# the chain, so slot 0 is the panel FURTHEST from the Pi. Since each panel is chained
# to the left of the one before it, that furthest panel is the leftmost one, and plain
# 0, 1, 2, 3 already runs the right way round the cube.
FACE_ORDER = [0, 1, 2, 3]
FACE_ROTATION = [0, 0, 0, 0]                # clockwise degrees per panel: 0, 90, 180 or 270
FACE_MIRROR = [False, False, False, False]  # flip left/right per panel

# =============================================================================
# TIMING AND BRIGHTNESS
# =============================================================================
TARGET_FPS = 40           # frame cap. Animations use real time, so fps doesn't change their speed.
MASTER_BRIGHTNESS = 0.4   # 0..1, multiplies every frame. It works like perceived brightness:
                          # the LED library lights a full pixel at 0.6 for 28% of the time,
                          # at 0.8 for 57% and at 1.0 for all of it, so the current climbs much
                          # faster than this number. The power limit below keeps that in check.

# =============================================================================
# POWER LIMIT (how to measure these: BOM.md, "Power budget")
# =============================================================================
# Every frame, the watts the LEDs on each supply would draw are estimated from the picture.
# If a supply would go over LED_WATTS_PER_SUPPLY, the whole picture is dimmed just enough.
#
# Which faces each USB-C supply powers, by face number 0-3 (the test pattern's "faces"
# shows them as 1-4). Every face goes in exactly one group.
POWER_SUPPLIES = [[0, 1, 2, 3]]          # all four panels on one supply
# POWER_SUPPLIES = [[0, 1], [2, 3]]      # two supplies, two panels each

LED_WATTS_PER_SUPPLY = 8.0     # most the LEDs on ONE supply may draw. A USB-C port gives 15 W
                               # at 5 V: take off the fans on that port, what its panels draw
                               # while dark, and a margin of 1-2 W. It's one number for every
                               # supply, so work it out for the one the fans are on.
                               # Kept low until measured.
PANEL_FULL_WATTS = (5.0, 5.0, 5.0)   # one whole panel lit full red / green / blue, in watts
                                     # above its dark draw. Red: about 5 W, first measurement.
                                     # Green and blue: not measured yet, assumed the same.

# =============================================================================
# VISUAL MODES
# =============================================================================
START_MODE = 0            # position in the mode list (see visuals/__init__.py) or a mode name

# False = QUBE lights up as soon as it boots, starting with the startup colours below.
# True = it powers up dark and waits for the clicker's square button, so it can be plugged
# in and left until you're ready. Either way a restart comes back however the LEDs were,
# so that button keeps working.
START_WITH_LEDS_OFF = False
STARTUP_TEST_SECONDS = 1.0   # when the LEDs start on: every pixel red, then green, then blue,
                             # this long each, before the first visual. It shows from a distance
                             # that booting has finished, and checks every panel and colour.
                             # 0 = straight into the first visual.
AUTO_CYCLE_SECONDS = 0    # move to the next mode every N seconds (0 = never, buttons only)
CROSSFADE_SECONDS = 1.5   # blend time when switching modes or turning the LEDs back on

# =============================================================================
# AUDIO INPUT
# =============================================================================
# Mic: Adafruit Mini USB Mic (#3367, model M-305). Its packaging rates it for
# 100 Hz - 8 kHz and a maximum sound level of 100 dB SPL.
AUDIO_DEVICE = None   # None = auto: first input with "USB" in its name, else the system default.
                      # Or a device index (int) or part of its name (str).
                      # List devices with: python3 tools/list_audio_devices.py
SAMPLE_RATE = None    # None = the device's default rate
AUDIO_CHANNELS = 1    # stereo mics are mixed down to mono
AUDIO_CHUNK = 512     # samples per block delivered by the sound card
FFT_SIZE = None       # samples per FFT window. None = automatic: 2048 at 32 kHz and above,
                      # 1024 below that. Or set a power of 2 (1024, 2048, 4096).
AUDIO_STALL_RESTART_SECONDS = 10   # restart if the mic sends nothing for this long, e.g. after
                                   # it was unplugged and plugged back in (0 = never)

# =============================================================================
# AUDIO ANALYSIS
# =============================================================================
# Six frequency bands in Hz: bass, mid and high, each split in two at its midpoint.
BASS_RANGE = (40, 145)
BASS_MID_RANGE = (145, 250)
MID_RANGE = (250, 1125)
MID_HIGH_RANGE = (1125, 2000)
HIGH_RANGE = (2000, 5000)
HIGH_TOP_RANGE = (5000, 8000)
SPECTRUM_BANDS = 16          # extra log-spaced bands for spectrum-style visuals...
SPECTRUM_RANGE = (40, 8000)  # ...spread across this range

# How a band's loudness becomes its 0..1 level. Each band has a "normal" level that
# follows the sound; the level shows how far above normal the band is right now.
LEVEL_RANGE_DB = 10.0           # dB above normal that fills a bar (smaller = more sensitive)
CONTRAST_DB = 24.0              # a band that rose this many dB less than the band that rose most
                                # is dimmed to zero (smaller = bands react more separately)
BACKGROUND_RISE_SECONDS = 6.0   # how slowly "normal" follows the sound when it gets louder
BACKGROUND_FALL_SECONDS = 1.0   # how quickly "normal" follows the sound when it gets quieter

# Smoothing. Attack = how fast a level rises, release = how fast it falls back.
ATTACK_SECONDS = 0.02
RELEASE_SECONDS = {"bass": 0.20, "bassMid": 0.20, "mid": 0.15, "midHigh": 0.15,
                   "high": 0.08, "highTop": 0.08}   # highs fall fastest = sharper

SILENCE_DB = -65.0                # overall loudness (dB below full scale) under this = silence.
                                  # Your mic measured: quiet room about -70, quiet music about -60.
                                  # Tune it with the "Level Meter" mode (--mode meter).
INPUT_GAIN_DB = 0.0               # boost (+) or cut (-) the mic signal before analysis

# Beat detection (bass hits)
BEAT_THRESHOLD_DB = 5.0           # bass must jump this far above its recent average
BEAT_MIN_BASS_SHARE_DB = -12.0    # bass must be at least this loud compared with the whole sound,
                                  # so hi-hats or crowd noise can't fake a bass hit
BEAT_COOLDOWN_SECONDS = 0.25      # minimum time between beats (0.25 s allows up to 240 BPM)

# The sound wave itself (audio.waveform), for visuals that draw it, like Radial Waveform
WAVEFORM_SECONDS = 0.025          # how much sound one frame shows: 25 ms is a few cycles of
                                  # a bass note. Longer = more wiggles, shorter = smoother
WAVEFORM_POINTS = 128             # averaged down to this many values, smoothing away hiss

# =============================================================================
# REMOTE CONTROL (see remote_input.py)
# =============================================================================
# GUMENA presentation clicker. Its USB receiver acts like a USB keyboard, so there's
# nothing to pair. Needs python3-evdev, and the program must run with sudo to read it.
REMOTE_ENABLED = True
REMOTE_DEVICE_NAME = None   # None = listen to any keyboard-like device.
                            # Set it to part of the receiver's name (tools/remote_keys.py
                            # shows it) to listen ONLY to the clicker. That also stops its
                            # key presses from being typed into the Pi's console.

# Which keys trigger which action. These match the presenter in BOM.md. For a different
# one, see what its buttons send with `sudo python3 tools/remote_keys.py` and put those
# key names here.
REMOTE_KEYS = {
    "prev": ["KEY_PAGEUP", "KEY_UP", "KEY_LEFT"],         # up arrow button: previous mode
    "next": ["KEY_PAGEDOWN", "KEY_DOWN", "KEY_RIGHT"],    # down arrow button: next mode
    "leds": ["KEY_B", "KEY_DOT"],                         # black screen (square): LEDs off,
                                                          # then on again + restart
    "qr": ["KEY_F5", "KEY_ESC"],                          # full screen (double square): QR code
}
RESTART_FORCE_SECONDS = 4   # if a restart doesn't happen cleanly within this time (frozen), force it

# Wired buttons between a GPIO pin and GND (BCM pin numbers), e.g. on QUBE's pole.
# None = not used. Choose pins after the panel adapter's pin map is decided.
GPIO_BUTTONS = {"prev": None, "next": None, "leds": None, "qr": None}

# =============================================================================
# DISPLAY OUTPUT
# =============================================================================
DISPLAY = "web"    # "web"    = live preview in a web browser (run on the Pi or a PC)
                   # "matrix" = the LED panels (needs the patched library: PI_SETUP.md step 10)
                   # "none"   = no picture, just prints fps

WEB_PREVIEW_PORT = 8080   # open http://<computer-ip>:8080 in a browser
WEB_PREVIEW_FPS = 20      # frames per second sent to the browser

# How frames are copied onto the panel canvas:
#   "auto"     = try the fast Pillow path, fall back to per-pixel if it raises an error
#   "pillow"   = always the fast path (needs Pillow)
#   "setpixel" = always per-pixel (slow but works with any Pillow version)
PIXEL_PUSH = "auto"

# Where a panel's 40 visible columns sit inside its 48 shift-register columns (see "cols"
# in MATRIX_OPTIONS). 8 means the 8 dead positions come first, 0 means they come last.
# If this is wrong you get an 8-pixel black stripe down one edge of every panel and
# 8 columns of the picture missing from the other edge - swap 8 for 0 and try again.
PANEL_COLUMN_OFFSET = 8

# rpi-rgb-led-matrix options, passed straight to RGBMatrixOptions.
# The 28-pin panels need the library patched by tools/patch_rgbmatrix.py (see PI_SETUP.md):
# each panel's 5 bands of 8 rows are driven as 5 "parallel chains".
MATRIX_OPTIONS = {
    "rows": 8,               # rows per band (74HC138 decoder = 8 row addresses)
    "cols": 48,              # SHIFT-REGISTER columns per panel, not LEDs. Each panel has 3
                             # driver chips per colour per band (3 x 16 = 48 channels) but only
                             # 40 columns of LEDs, so 8 positions per panel are invisible.
                             # A walking line pauses for 8 steps between panels, and a
                             # 48-column pattern lines up on all of them (see WIRING.md).
    "chain_length": 4,       # panels in the chain. Override for one session with --chain N;
                             # with fewer than 4 the panels show the first faces, so
                             # --chain 3 shows faces 0, 1 and 2.
    "parallel": 5,           # 5 data bands per panel
    "hardware_mapping": "qube-28pin",    # added by tools/patch_rgbmatrix.py
    "gpio_slowdown": 4,      # 4 = safest on jumper wires with 3.3 V signals. Once the image is
                             # clean, try 3, then 2 (faster refresh); go back if it glitches
    "brightness": 100,       # keep at 100; use MASTER_BRIGHTNESS above instead
    "pwm_bits": 11,
    "drop_privileges": False,  # keep root so the USB mic and clicker stay readable
}
