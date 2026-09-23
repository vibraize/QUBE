"""
main.py - QUBE, the audio-reactive LED cube. Start here.

    python3 main.py                          # settings from config.py
    python3 main.py --leds on                # light up straight away (normally it boots dark)
    python3 main.py --fake-audio             # no mic needed (synthetic beat)
    python3 main.py --display web            # live preview in a browser
    sudo python3 main.py --display matrix    # the LED panels (see README)
    python3 main.py --display none --seconds 30    # run with no picture output

Every frame the main loop:
    1. grabs the newest microphone samples
    2. analyzes them (bass / mid / high / beats)
    3. asks the current visual mode to draw a frame (skipped while the LEDs are off)
    4. crossfades between modes, applies brightness and the power limit
    5. sends the frame to the display
    6. handles controls (clicker, terminal keys, browser buttons) and auto-cycling
"""
import argparse
import signal
import sys
import time

import config
from audio_analysis import AudioAnalyzer
from controls import KeyReader, key_to_command
from display import PowerLimit, create_display
from layout import CubeLayout
from remote_input import RemoteInput
from service import RestartRequest, Watchdog, recall_leds, remember_leds, restart_program
from visuals import MODES, QrCode, find_mode


def parse_args():
    parser = argparse.ArgumentParser(description="QUBE, the audio-reactive LED cube")
    parser.add_argument("--display", default=config.DISPLAY, choices=["web", "matrix", "none"])
    parser.add_argument("--mode", default=str(config.START_MODE),
                        help="starting mode: a number or part of a name (e.g. 1, river, meter)")
    parser.add_argument("--fake-audio", action="store_true", help="synthetic beat instead of the mic")
    parser.add_argument("--audio-device", help="input device index or part of its name")
    parser.add_argument("--seconds", type=float, default=0.0, help="stop after N seconds (0 = forever)")
    parser.add_argument("--no-cycle", action="store_true", help="don't switch modes automatically")
    parser.add_argument("--leds", choices=["on", "off"],
                        help="start with the LEDs on or off, ignoring START_WITH_LEDS_OFF")
    parser.add_argument("--chain", type=int,
                        help="panels chained right now (overrides MATRIX_OPTIONS['chain_length']). "
                             "With fewer panels than faces, the first faces are shown.")
    parser.add_argument("--matrix", action="append", metavar="KEY=VALUE", default=[],
                        help="change one MATRIX_OPTIONS setting for this run, for trying panel "
                             "timings without editing config.py: --matrix pwm_bits=8 "
                             "--matrix show_refresh_rate=1 (use it as often as you like)")
    return parser.parse_args()


def parse_matrix_options(pairs):
    """["pwm_bits=8", "show_refresh_rate=1"] -> {"pwm_bits": 8, "show_refresh_rate": 1}.
    Numbers become numbers and true / false become True / False; anything else stays text."""
    options = {}
    for pair in pairs:
        key, separator, value = pair.partition("=")
        key, value = key.strip(), value.strip()
        if not separator or not key or not value:
            raise ValueError(f"--matrix wants KEY=VALUE, for example pwm_bits=8, not '{pair}'")
        if value.lower() in ("true", "false"):
            options[key] = value.lower() == "true"
            continue
        for convert in (int, float, str):
            try:
                options[key] = convert(value)
                break
            except ValueError:
                pass
    return options


def open_audio(args):
    history = max(4096, config.FFT_SIZE or 0)     # samples kept: enough for any FFT window
    if args.fake_audio:
        from audio_input import FakeAudioInput
        return FakeAudioInput(48000, history)
    from audio_input import AudioInput
    device = args.audio_device if args.audio_device is not None else config.AUDIO_DEVICE
    if isinstance(device, str) and device.isdigit():
        device = int(device)
    return AudioInput(device=device, sample_rate=config.SAMPLE_RATE, channels=config.AUDIO_CHANNELS,
                      chunk=config.AUDIO_CHUNK, buffer_size=history)


class ModeSwitcher:
    """Keeps one instance of each visual mode and crossfades when switching."""

    def __init__(self, layout, start):
        self.layout = layout
        self.instances = {}
        mode_class, index = find_mode(start)
        self.index = index if index is not None else 0
        self.current = self._instance(mode_class)
        self.current.start()
        self.previous_frame = None
        self.fade_left = 0.0
        self.last_switch = time.monotonic()
        print(f"Mode: {self.current.name}")

    def _instance(self, mode_class):
        if mode_class not in self.instances:
            self.instances[mode_class] = mode_class(self.layout)
        return self.instances[mode_class]

    def switch_to(self, mode_class, index, last_frame):
        self.fade_in(last_frame)
        if index is not None:
            self.index = index
        self.current = self._instance(mode_class)
        self.current.start()
        print(f"Mode: {self.current.name}")

    def step_mode(self, step, last_frame):
        if type(self.current) in MODES:
            self.index = (self.index + step) % len(MODES)
        else:
            self.index = 0 if step > 0 else len(MODES) - 1   # leaving a tool mode like Level Meter
        self.switch_to(MODES[self.index], self.index, last_frame)

    def toggle_mode(self, mode_class, last_frame):
        """Show mode_class, or go back to the last cycling mode if it's already showing.
        Used for the QR code, which sits on its own button rather than in the cycle."""
        if isinstance(self.current, mode_class):
            self.switch_to(MODES[self.index], self.index, last_frame)
        else:
            self.switch_to(mode_class, None, last_frame)     # index stays, so we can come back

    def fade_in(self, from_frame):
        """Crossfade from from_frame (the old mode's last frame, or black) to the current mode."""
        self.previous_frame = from_frame
        self.fade_left = config.CROSSFADE_SECONDS
        self.last_switch = time.monotonic()

    def draw(self, audio, dt):
        frame = self.current.step(audio, dt)
        if self.fade_left > 0.0 and self.previous_frame is not None:
            mix = 1.0 - self.fade_left / max(config.CROSSFADE_SECONDS, 1e-3)
            frame = self.previous_frame * (1.0 - mix) + frame * mix
            self.fade_left -= dt
        return frame


def close_quietly(thing):
    """Close something during shutdown without letting one failure skip the rest."""
    try:
        thing.close()
    except Exception as error:
        print(f"While closing {type(thing).__name__}: {error}")


def startup_colors(display, layout, power, brightness, seconds):
    """Fill every pixel with red, then green, then blue, for `seconds` each, before the first
    visual. It shows from a distance that booting has finished, and checks every panel,
    every colour and every pixel on the way. These frames go through the power limit and
    MASTER_BRIGHTNESS like any other, so they may come out dimmer than full."""
    frame = layout.new_canvas()
    info = {"mode": "starting", "bass": 0, "bassMid": 0, "mid": 0, "midHigh": 0, "high": 0,
            "highTop": 0, "beat": 0, "fps": 0, "volume_db": -120, "silent": True, "leds": True}
    for color in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)):
        frame[:] = color
        display.show(power.apply(frame, brightness) if display.wants_brightness else frame, info)
        time.sleep(seconds)


def main():
    args = parse_args()
    layout = CubeLayout(config.FACE_SIZE, config.NUM_FACES)
    try:
        power = PowerLimit(config, layout)       # checks the power settings before anything lights
    except ValueError as error:
        print(error)
        return 1

    # Open the mic BEFORE the LED library starts: the library can drop root privileges
    # when it starts (see drop_privileges in config.py), which may block the USB mic.
    try:
        audio_in = open_audio(args)
    except Exception as error:
        print(f"Couldn't open the microphone: {error}")
        print("Try:  python3 tools/list_audio_devices.py   or run with --fake-audio")
        return 1
    analyzer = AudioAnalyzer(audio_in.sample_rate, config)
    print(f"Audio: {audio_in.device_name} at {audio_in.sample_rate} Hz "
          f"(FFT window {analyzer.fft_size} samples)")

    if args.chain:      # e.g. --chain 3 while only three panels are wired up
        config.MATRIX_OPTIONS = dict(config.MATRIX_OPTIONS, chain_length=args.chain)
    if args.matrix:     # e.g. --matrix pwm_bits=8, while trying panel timings
        try:
            changes = parse_matrix_options(args.matrix)
        except ValueError as error:
            print(error)
            return 1
        config.MATRIX_OPTIONS = dict(config.MATRIX_OPTIONS, **changes)
        print("Panel options for this run: "
              + ", ".join(f"{key} = {value}" for key, value in changes.items()))
    try:
        display = create_display(args.display, layout, config)
    except Exception as error:
        audio_in.close()
        print(f"Couldn't start the '{args.display}' display: {error}")
        return 1

    modes = ModeSwitcher(layout, args.mode)
    keys = KeyReader()
    restart = RestartRequest(__file__, config.RESTART_FORCE_SECONDS, before_force=keys.close)
    remote = RemoteInput(config, on_restart=restart.request)
    watchdog = Watchdog()
    running = [True]
    signal.signal(signal.SIGTERM, lambda *_: running.__setitem__(0, False))   # e.g. systemctl stop

    brightness = config.MASTER_BRIGHTNESS
    # Fresh boot: whatever config.py says, normally lit, starting with the startup colours.
    # After a restart: however the LEDs were, so the button that restarts still works.
    leds_on = args.leds == "on" if args.leds else recall_leds(not config.START_WITH_LEDS_OFF)
    remote.set_leds(leds_on)
    if not leds_on:
        print("Starting with the LEDs off - press the clicker's square button for light.")
    elif config.STARTUP_TEST_SECONDS > 0:
        print(f"Startup colours: red, green, blue, {config.STARTUP_TEST_SECONDS} s each")
        startup_colors(display, layout, power, brightness, config.STARTUP_TEST_SECONDS)
    black = layout.new_canvas()
    frame = black
    frame_seconds = 1.0 / config.TARGET_FPS
    auto_cycle = 0.0 if args.no_cycle else config.AUTO_CYCLE_SECONDS
    started = last = report_start = time.monotonic()
    timing = {"frames": 0, "analysis": 0.0, "draw": 0.0, "output": 0.0, "watts": 0.0, "dimmed": 0}
    fps = 0.0
    if keys.enabled:
        print("Keys: n / p = next / previous mode, 0-9 = pick mode, l = LEDs on/off, "
              "r = restart, + / - = brightness, q = quit")

    try:
        while running[0] and not restart.requested():
            now = time.monotonic()
            dt = min(now - last, 0.1)      # clamp, so a hiccup doesn't make animations jump
            last = now

            t0 = time.perf_counter()
            audio = analyzer.process(audio_in.get_samples(), dt)
            t1 = time.perf_counter()
            frame = modes.draw(audio, dt) if leds_on else black     # LEDs off: skip drawing
            t2 = time.perf_counter()
            output = frame
            if leds_on and display.wants_brightness:
                output = power.apply(frame, brightness)
                timing["watts"] = max(timing["watts"], max(power.watts))   # for the report
                timing["dimmed"] += power.dimmed
            display.show(output, {
                "mode": modes.current.name, "bass": audio.bass, "bassMid": audio.bassMid,
                "mid": audio.mid, "midHigh": audio.midHigh, "high": audio.high,
                "highTop": audio.highTop,
                "beat": audio.beat_pulse, "fps": fps, "volume_db": audio.volume_db,
                "silent": audio.silent, "leds": leds_on,
            })
            t3 = time.perf_counter()
            watchdog.ping()                # tells systemd the loop is alive (if running as a service)

            # Controls: terminal keys, browser buttons, clicker / wired buttons
            commands = [key_to_command(k) for k in keys.read_keys()]
            commands += display.poll_commands() + remote.poll()
            for command in commands:
                if command == "quit":
                    running[0] = False
                elif command == "restart":
                    print("Restart requested")
                    restart.request()
                elif command == "leds":
                    # Off, then on again restarts the program: one button for both jobs.
                    if leds_on:
                        leds_on = False
                        remember_leds(False)
                        print("LEDs off (the Pi keeps running)")
                    else:
                        remember_leds(True)       # so the restart comes back lit
                        print("LEDs back on - restarting")
                        restart.request()
                    remote.set_leds(leds_on)      # keep the clicker's idea of it in step
                elif command == "qr":
                    modes.toggle_mode(QrCode, frame)
                elif command == "next":
                    modes.step_mode(+1, frame)
                elif command == "prev":
                    modes.step_mode(-1, frame)
                elif command in ("brighter", "dimmer"):
                    change = 0.1 if command == "brighter" else -0.1
                    brightness = min(1.0, max(0.05, brightness + change))
                    print(f"Brightness: {brightness:.1f}")
                elif command and command.startswith("mode:"):
                    try:
                        mode_class, index = find_mode(command[len("mode:"):])
                        modes.switch_to(mode_class, index, frame)
                    except ValueError as error:
                        print(error)

            # Auto-cycle (only through MODES, so a picked tool like Level Meter stays put)
            if (leds_on and auto_cycle and type(modes.current) in MODES
                    and now - modes.last_switch >= auto_cycle):
                modes.step_mode(+1, frame)

            # If the mic stops delivering sound (e.g. unplugged), restart to reconnect it
            silent_for = audio_in.seconds_since_data()
            if (config.AUDIO_STALL_RESTART_SECONDS and silent_for > config.AUDIO_STALL_RESTART_SECONDS
                    and not restart.requested()):
                print(f"No data from the mic for {silent_for:.0f} s - restarting to reconnect it.")
                restart.request()

            # Performance report every 5 seconds
            timing["frames"] += 1
            timing["analysis"] += t1 - t0
            timing["draw"] += t2 - t1
            timing["output"] += t3 - t2
            if now - report_start >= 5.0:
                n = timing["frames"]
                fps = n / (now - report_start)
                # The most the LEDs on any one supply wanted (an estimate; a meter also shows
                # the panels' dark draw and any fans), and how often the power limit dimmed.
                power_note = ""
                if timing["watts"]:
                    power_note = f" | LEDs want up to {timing['watts']:.1f} W on a supply"
                    if timing["dimmed"]:
                        power_note += (f" (held to {power.budget:g} W on "
                                       f"{timing['dimmed'] / n:.0%} of frames)")
                print(f"{fps:5.1f} fps | ms per frame: analysis {timing['analysis'] / n * 1000:.1f}, "
                      f"draw {timing['draw'] / n * 1000:.1f}, output {timing['output'] / n * 1000:.1f} | "
                      f"bass {audio.bass:.2f} bassMid {audio.bassMid:.2f} mid {audio.mid:.2f} "
                      f"midHigh {audio.midHigh:.2f} high {audio.high:.2f} highTop {audio.highTop:.2f} | "
                      f"mic {audio.volume_db:.0f} dB{' (silent)' if audio.silent else ''}"
                      f"{'' if leds_on else ' | LEDs off'}{power_note}")
                timing = {"frames": 0, "analysis": 0.0, "draw": 0.0, "output": 0.0, "watts": 0.0,
                          "dimmed": 0}
                report_start = now

            if args.seconds and now - started >= args.seconds:
                break
            spare = frame_seconds - (time.monotonic() - now)
            if spare > 0:
                time.sleep(spare)
    except KeyboardInterrupt:
        pass
    finally:
        for thing in (keys, remote, display, audio_in):
            close_quietly(thing)

    if restart.requested():
        restart.cancel_timer()
        print("Restarting...", flush=True)
        restart_program(__file__)       # starts again from the top (doesn't return on the Pi)
    print("Stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
