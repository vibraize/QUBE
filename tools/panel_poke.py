"""
tools/panel_poke.py - drive one panel directly from the Pi's GPIO pins.

Why this exists: this speaks the panel's protocol by hand, with no extra packages and no
LED library at all. That makes it the fastest way to check wiring on a new panel, and the
way to tell a wiring fault from a library problem. The real visuals use the patched
rpi-rgb-led-matrix instead (PI_SETUP.md step 10).

Before anything lights: **every panel needs pin 28 (SR) held at 3.3 V and its own LAT
(pin 26) wire from the Pi.** Neither travels along the chain. See WIRING.md.

Pin map: see WIRING.md. Run from the project folder:

    sudo python3 tools/panel_poke.py                        # first light: band 1, red, dim
    sudo python3 tools/panel_poke.py --pattern bands        # each band in turn
    sudo python3 tools/panel_poke.py --pattern rows --band all
    sudo python3 tools/panel_poke.py --pattern columns --color white
    sudo python3 tools/panel_poke.py --pattern walk         # a line walking across
    sudo python3 tools/panel_poke.py --static-row 0         # one row, no scanning

What each one tells you:
    solid       does the panel light at all?  (the default)
    bands       which panel pins (RD1..RD5) drive which group of 8 rows
    rows        are A/B/C wired right, and is it really 1/8 scan?
    columns     is the shift clock working, and how wide is a panel?
    walk        which edge does data shift in from?
    static-row  light with the row scanning switched off - rules out A/B/C

If the panel stays dark:
    --oe-active-high    inverts output enable.
    --sr high / --sr low
                        drives panel pin 28 (SR) from GPIO 25 instead of a fixed 3.3 V, if
                        you ever want to test it. Needs one extra jumper: panel pin 28 ->
                        Pi pin 22. Normally SR is just wired to 3.3 V and left alone.
    --dark-shift        the older timing, where the clock stops while a row is lit. The
                        default keeps clocking the whole time, like real controllers do.
                        These panels light either way.

Columns: a panel is 48 shift-register columns wide but only 40 have LEDs (45 driver chips
= 5 bands x 3 colours x 3 chips of 16 channels, 8 spare per chain). A 48-column pattern
lines up on every panel in a chain while a 40-column one scatters.
So use --cols 48 per panel: 48 for one, 96 for two, 144 for three, 192 for four.

CURRENT: a first measurement put a whole panel of full red at about 5 W (1 A at 5 V).
White adds green and blue on top (not measured yet), so it could come close to the 3 A
a USB-C port gives at 5 V on its own. The defaults (one band, brightness 0.2) keep it
low. Be careful combining --band all with white or a high --brightness.
"""
import argparse
import ctypes
import mmap
import os
import sys
import time


def mask(*pins):
    """Bit mask for a set of GPIO numbers: mask(17, 4) == (1 << 17) | (1 << 4)."""
    bits = 0
    for pin in pins:
        bits |= 1 << pin
    return bits


# ---- Pin map (BCM numbers). Must match WIRING.md and the library patch. --------------
# Band n drives 8 of the panel's 40 rows. Each band has its own R, G and B line.
DATA_PINS = [
    (11, 27, 7),    # band 1 - panel pins 1, 2, 3
    (12, 5, 6),     # band 2 - panel pins 5, 6, 7
    (2, 3, 26),     # band 3 - panel pins 9, 10, 11
    (8, 9, 10),     # band 4 - panel pins 13, 14, 15
    (13, 19, 20),   # band 5 - panel pins 17, 18, 19
]
ADDRESS_PINS = (22, 23, 24)   # A, B, C - panel pins 21, 22, 23
CLOCK_PIN = 17                # panel pin 25
LATCH_PIN = 4                 # panel pin 26
OUTPUT_ENABLE_PIN = 18        # panel pin 27
SR_PIN = 25                   # panel pin 28 -> Pi pin 22, only used with --sr

ALL_PINS = [pin for band in DATA_PINS for pin in band] + list(ADDRESS_PINS) + \
           [CLOCK_PIN, LATCH_PIN, OUTPUT_ENABLE_PIN]
DATA = mask(*(pin for band in DATA_PINS for pin in band))
ADDRESS = mask(*ADDRESS_PINS)
CLK = mask(CLOCK_PIN)
LAT = mask(LATCH_PIN)
OE = mask(OUTPUT_ENABLE_PIN)
SR = mask(SR_PIN)

ROWS_PER_BAND = 8             # the 74HC138 decoder gives 8 row addresses
COLORS = {
    "red": (1, 0, 0), "green": (0, 1, 0), "blue": (0, 0, 1),
    "yellow": (1, 1, 0), "cyan": (0, 1, 1), "magenta": (1, 0, 1),
    "white": (1, 1, 1),
}
MAX_STATIC_SECONDS = 10.0     # --static-row never runs longer than this
MAX_BRIGHTNESS = 0.9


# ---- Talking to the pins -------------------------------------------------------------
# Both ways of driving the pins offer the same call: write(high_mask, low_mask) sets
# every pin in high_mask high and every pin in low_mask low.

class RegisterPins:
    """Fast: writes the Pi's GPIO registers directly, so all 15 data lines change in a
    single step. This is the same trick the LED library uses. Register layout from the
    BCM2835 peripherals datasheet; the Pi 2 and 3 use the same layout."""

    GPFSEL0 = 0x00                 # function select: 3 bits per pin, 10 pins per register
    GPSET0 = 0x1C                  # writing a 1 bit drives that pin high
    GPCLR0 = 0x28                  # writing a 1 bit drives that pin low
    GPIO_PHYSICAL = 0x3F200000     # where the GPIO block sits on a Pi 2/3 (for /dev/mem)

    def __init__(self, pins, initial_high):
        self.mem = self._open()
        self._set = ctypes.c_uint32.from_buffer(self.mem, self.GPSET0)
        self._clr = ctypes.c_uint32.from_buffer(self.mem, self.GPCLR0)
        # Set the levels first, then switch the pins to outputs, so no pin glitches
        # (in particular OE never lights the panel for an instant on start-up).
        self.write(initial_high, mask(*pins) & ~initial_high)
        for pin in pins:
            self._make_output(pin)

    def _open(self):
        # /dev/gpiomem maps just the GPIO block; /dev/mem needs root and the address.
        for path, offset in (("/dev/gpiomem", 0), ("/dev/gpiomem0", 0),
                             ("/dev/mem", self.GPIO_PHYSICAL)):
            try:
                fd = os.open(path, os.O_RDWR | os.O_SYNC)
            except OSError:
                continue
            try:
                return mmap.mmap(fd, 4096, flags=mmap.MAP_SHARED,
                                 prot=mmap.PROT_READ | mmap.PROT_WRITE, offset=offset)
            except OSError:
                continue
            finally:
                os.close(fd)
        raise OSError("couldn't open /dev/gpiomem or /dev/mem")

    def _make_output(self, pin):
        register = ctypes.c_uint32.from_buffer(self.mem, self.GPFSEL0 + 4 * (pin // 10))
        shift = (pin % 10) * 3
        register.value = (register.value & ~(0b111 << shift)) | (0b001 << shift)

    def write(self, high_mask, low_mask):
        if low_mask:
            self._clr.value = low_mask
        if high_mask:
            self._set.value = high_mask

    def close(self):
        # The pins stay outputs at their last (safe) levels until reboot or until
        # another program takes them. Letting them float would leave OE to a tug of
        # war between the panel's pull-up and the Pi's pull-down.
        del self._set, self._clr       # release the views so the mapping can close
        self.mem.close()


class GpiozeroPins:
    """Slow fallback through gpiozero, one pin at a time. Works on any Pi, but each
    refresh takes long enough that scanning patterns will flicker."""

    def __init__(self, pins, initial_high):
        try:
            from gpiozero import OutputDevice
            self.devices = {pin: OutputDevice(pin, initial_value=bool(initial_high >> pin & 1))
                            for pin in pins}
        except Exception as error:
            raise SystemExit(f"Couldn't open the GPIO pins through gpiozero either: {error}")

    def write(self, high_mask, low_mask):
        for pin, device in self.devices.items():
            if low_mask >> pin & 1:
                device.off()
            elif high_mask >> pin & 1:
                device.on()

    def close(self):
        for device in self.devices.values():
            device.close()


def board_model():
    try:
        with open("/proc/device-tree/model", "rb") as f:
            return f.read().rstrip(b"\x00").decode(errors="replace")
    except OSError:
        return ""


def open_pins(pins, initial_high):
    """Direct registers on a Pi 2/3 (the layout above is only right for those), else gpiozero."""
    model = board_model()
    if "Raspberry Pi 3" in model or "Raspberry Pi 2" in model:
        try:
            return RegisterPins(pins, initial_high), "direct registers (fast)"
        except OSError as error:
            print(f"Direct GPIO access failed ({error}), falling back to gpiozero.")
    return GpiozeroPins(pins, initial_high), "gpiozero (slow - scanning will flicker)"


# ---- The panel protocol ----------------------------------------------------------------

class Panel:
    """Shift a row of columns in, latch it, choose which row lights, show it."""

    def __init__(self, oe_active_high=False, pins=None, sr=None):
        # "Blanked" means OE inactive: high for an active-low OE (the usual kind).
        self.blank_is_high = not oe_active_high
        start_high = OE if self.blank_is_high else 0      # start blanked, all else low
        pin_list = list(ALL_PINS)
        if sr is not None:                                # SR is only touched if asked
            pin_list.append(SR_PIN)
            if sr == "high":
                start_high |= SR
        if pins is None:
            pins, self.backend = open_pins(pin_list, start_high)
        else:
            self.backend = "test"
        self.pins = pins

    def blank(self):
        if self.blank_is_high:
            self.pins.write(OE, 0)
        else:
            self.pins.write(0, OE)

    def unblank(self):
        if self.blank_is_high:
            self.pins.write(0, OE)
        else:
            self.pins.write(OE, 0)

    def shift_column(self, bits):
        """Clock one column in. `bits` is a mask of the data pins that are on."""
        self.pins.write(bits, DATA & ~bits)
        self.pins.write(CLK, 0)              # rising edge: the panel takes the data
        self.pins.write(0, CLK)

    def shift_row(self, columns):
        for bits in columns:
            self.shift_column(bits)

    def show_row(self, row):
        """Move the shifted data to the LEDs, select the row address, light it."""
        self.blank()
        self.pins.write(LAT, 0)
        self.pins.write(0, LAT)
        on = mask(*(pin for i, pin in enumerate(ADDRESS_PINS) if row >> i & 1))
        self.pins.write(on, ADDRESS & ~on)
        self.unblank()

    def close(self, cols):
        """Blank and clear the panel's registers, so nothing can light after we exit."""
        self.blank()
        self.shift_row([0] * cols)
        self.pins.write(LAT, 0)
        self.pins.write(0, LAT)
        self.pins.close()


def hold(seconds):
    """Wait precisely. time.sleep() is far too coarse for the microseconds a row is lit."""
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        pass


def scan_overlap(panel, frame, duty):
    """The default timing, the way real controllers do it: each row is lit while the
    NEXT row's data clocks in, for the first `duty` of that shift, then blanked. The
    clock never stops. Needs row 0 already shifted in; run() does that."""
    lit_columns = max(1, round(duty * len(frame[0])))
    for row in range(len(frame)):
        panel.show_row(row)
        for i, bits in enumerate(frame[(row + 1) % len(frame)]):
            if i == lit_columns:
                panel.blank()
            panel.shift_column(bits)
        panel.blank()


def scan_dark(panel, frame, duty):
    """The older timing (--dark-shift): each row shifts in with the panel dark, then is
    lit for `duty` of the total time with the clock stopped."""
    for row, columns in enumerate(frame):
        started = time.perf_counter()
        panel.shift_row(columns)
        shifting = time.perf_counter() - started
        panel.show_row(row)
        hold(shifting * duty / (1.0 - duty))
        panel.blank()


# ---- Patterns -------------------------------------------------------------------------

def band_bits(band, color):
    """Mask of the data pins that are on for one band in one color."""
    return mask(*(pin for pin, on in zip(DATA_PINS[band], color) if on))


def pattern_state(pattern, t, cols):
    """Where a moving pattern is at t seconds. Still patterns return None."""
    if pattern == "bands":
        return int(t / 1.5) % len(DATA_PINS)
    if pattern == "rows":
        return int(t / 1.0) % ROWS_PER_BAND
    if pattern == "walk":
        return int(t / 0.15) % cols
    return None


def build_frame(pattern, state, color, cols, bands):
    """The picture, as frame[row][column] = mask of the data pins that are on."""
    if pattern == "bands":
        bands = [state]                        # this pattern chooses its own band
    lit = 0
    for band in bands:
        lit |= band_bits(band, color)
    frame = []
    for row in range(ROWS_PER_BAND):
        line = []
        for column in range(cols):
            if pattern == "columns":
                on = (column // 4) % 2 == 0
            elif pattern == "rows":
                on = row == state
            elif pattern == "walk":
                on = column == state
            else:                              # solid, bands
                on = True
            line.append(lit if on else 0)
        frame.append(line)
    return frame


def describe(pattern, state):
    """Say what's lit now, so you can match it to what you see."""
    if pattern == "bands":
        first = 4 * state + 1
        print(f"  band {state + 1}  (panel pins {first}, {first + 1}, {first + 2})")
    elif pattern == "rows":
        print(f"  row address {state}  (A={state & 1} B={state >> 1 & 1} C={state >> 2 & 1})")
    elif pattern == "walk" and state == 0:
        print("  walk: back at column 0, the first column clocked in")


def run(panel, args, color, bands, duty):
    scan = scan_dark if args.dark_shift else scan_overlap
    started = time.monotonic()
    state = frame = None
    first = True
    while True:
        t = time.monotonic() - started
        if args.seconds and t >= args.seconds:
            return
        now = pattern_state(args.pattern, t, args.cols)
        if first or now != state:
            first = False
            state = now
            frame = build_frame(args.pattern, state, color, args.cols, bands)
            describe(args.pattern, state)
            if not args.dark_shift:
                panel.shift_row(frame[0])      # the overlap timing needs row 0 ready
        scan(panel, frame, duty)


def run_static(panel, args, color, bands, duty):
    """One row with scanning switched off: the simplest possible 'is it alive?' check.
    Unless --dark-shift, the clock keeps running (re-sending the same data without
    latching it), so a panel that blanks itself when the clock stops still lights."""
    seconds = min(args.seconds or 3.0, MAX_STATIC_SECONDS)
    lit = 0
    for band in bands:
        lit |= band_bits(band, color)
    columns = [lit] * args.cols
    lit_columns = max(1, round(duty * args.cols))
    print(f"Row {args.static_row} for {seconds:g} s (capped at {MAX_STATIC_SECONDS:g} s).")
    panel.shift_row(columns)
    panel.show_row(args.static_row)
    panel.blank()
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        panel.unblank()
        if args.dark_shift:
            hold(0.001 * duty)                 # 1 kHz: far too fast to see flicker
            panel.blank()
            hold(0.001 * (1.0 - duty))
        else:
            for i, bits in enumerate(columns):
                if i == lit_columns:
                    panel.blank()
                panel.shift_column(bits)
            panel.blank()


def main():
    parser = argparse.ArgumentParser(
        description="Drive a 28-pin LED panel directly from the Pi's GPIO pins.")
    parser.add_argument("--pattern", default="solid",
                        choices=["solid", "bands", "rows", "columns", "walk"])
    parser.add_argument("--color", default="red", choices=sorted(COLORS))
    parser.add_argument("--band", default="1", choices=["1", "2", "3", "4", "5", "all"],
                        help="band(s) to light; default 1 keeps the current low")
    parser.add_argument("--brightness", type=float, default=0.2,
                        help=f"0.02-{MAX_BRIGHTNESS}: share of the time a row is lit")
    parser.add_argument("--cols", type=int, default=40,
                        help="columns to clock out: 40 for one panel (try 48, see above)")
    parser.add_argument("--seconds", type=float, default=0.0,
                        help="stop after N seconds (0 = until Ctrl-C)")
    parser.add_argument("--static-row", type=int, default=None, metavar="ROW",
                        help=f"light one row (0-{ROWS_PER_BAND - 1}) without scanning")
    parser.add_argument("--oe-active-high", action="store_true",
                        help="try this if the panel stays dark: inverts output enable")
    parser.add_argument("--sr", choices=["high", "low"],
                        help="drive panel pin 28 (SR) from GPIO 25 - needs that jumper")
    parser.add_argument("--dark-shift", action="store_true",
                        help="older timing: stop the clock while a row is lit")
    args = parser.parse_args()

    if args.static_row is not None and not 0 <= args.static_row < ROWS_PER_BAND:
        parser.error(f"--static-row must be 0..{ROWS_PER_BAND - 1}")
    color = COLORS[args.color]
    bands = list(range(len(DATA_PINS))) if args.band == "all" else [int(args.band) - 1]
    duty = min(max(args.brightness, 0.02), MAX_BRIGHTNESS)
    most = (1 if args.pattern == "bands" else len(bands)) * args.cols * sum(color)

    panel = Panel(oe_active_high=args.oe_active_high, sr=args.sr)
    print(f"Pins: {panel.backend}. OE active {'high' if args.oe_active_high else 'low'}. "
          f"SR: {'driven ' + args.sr if args.sr else 'not driven'}. Timing: "
          f"{'clock stops while lit' if args.dark_shift else 'clock runs while lit'}.")
    print(f"Brightness {duty:.2f}, at most {most} LEDs lit at once. Ctrl-C to stop.")
    try:
        if args.static_row is not None:
            run_static(panel, args, color, bands, duty)
        else:
            run(panel, args, color, bands, duty)
    except KeyboardInterrupt:
        pass
    finally:
        panel.close(args.cols)
        print("\nBlanked and cleared the panel.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
