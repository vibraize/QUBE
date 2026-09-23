"""
remote_input.py - control QUBE from outside: the USB presentation clicker,
or wired push buttons.

Actions:
    prev      previous mode               clicker: up arrow
    next      next mode                   clicker: down arrow
    leds      LEDs off (the Pi stays on). clicker: "black screen" (square)
              Pressing it again turns them back on AND restarts the program.
    qr        show / hide the QR code     clicker: "full screen" (double square)

1. USB clicker (REMOTE_ENABLED = True in config.py)
   The clicker's USB receiver shows up on the Pi as a small keyboard, so there's
   nothing to pair. Each button sends a key; REMOTE_KEYS in config.py says which key
   does what. See what your buttons really send with:
       sudo python3 tools/remote_keys.py
   Keys are read on a background thread and the restart is fired from that thread,
   so turning the LEDs off and then on again restarts the program even if the visuals
   have frozen solid. Needs python3-evdev, and root (sudo) to read the receiver.

2. Wired buttons (GPIO_BUTTONS in config.py)
   A momentary button between a GPIO pin and GND, e.g. on QUBE's pole.
   Needs gpiozero. Not tested yet.
"""
import select
import sys
import threading
import time

SCAN_SECONDS = 3.0     # how often to look for a newly plugged-in receiver
REMOTE_BUSES = (0x03, 0x05)   # only USB (0x03) and Bluetooth (0x05) devices count as remotes,
                              # so built-in inputs like the Pi's HDMI port ("vc4-hdmi") are ignored


class RemoteInput:
    def __init__(self, cfg, on_restart=None):
        self.cfg = cfg
        self.on_restart = on_restart   # called right away, on the reader thread
        self.leds_on = True            # our copy of the LED state (see set_leds)
        self.lock = threading.Lock()
        self.pending = []              # actions waiting for the main loop
        self.stop = threading.Event()
        self.thread = None
        self.evdev = None
        self.devices = {}              # device path -> open evdev.InputDevice
        self.key_actions = {}          # key code -> action name
        self.warned = False
        self.buttons = []

        if cfg.REMOTE_ENABLED:
            self._start_clicker()
        self._start_gpio_buttons()

    # ---- USB clicker ------------------------------------------------------------
    def _start_clicker(self):
        if not sys.platform.startswith("linux"):
            print("Remote: the USB clicker is only read on the Raspberry Pi (Linux).")
            return
        try:
            import evdev
        except ImportError:
            print("Remote: python3-evdev isn't installed (sudo apt install python3-evdev), "
                  "so the clicker is ignored.")
            return
        self.evdev = evdev
        codes = evdev.ecodes.ecodes                  # key name -> key code
        for action, key_names in self.cfg.REMOTE_KEYS.items():
            for name in key_names:
                if name in codes:
                    self.key_actions[codes[name]] = action
                else:
                    print(f"Remote: unknown key name '{name}' in REMOTE_KEYS['{action}']")
        self.thread = threading.Thread(target=self._read_loop, name="remote", daemon=True)
        self.thread.start()

    def _read_loop(self):
        next_scan = 0.0
        while not self.stop.is_set():
            if time.monotonic() >= next_scan:
                self._scan()
                next_scan = time.monotonic() + SCAN_SECONDS
            by_fd = {device.fd: path for path, device in self.devices.items()}
            if not by_fd:
                self.stop.wait(0.5)
                continue
            try:
                ready, _, _ = select.select(list(by_fd), [], [], 0.5)
            except (OSError, ValueError):
                ready = list(by_fd)              # let the read below find the broken device
            for fd in ready:
                self._read_device(by_fd[fd])

    def _read_device(self, path):
        device = self.devices.get(path)
        if device is None:
            return
        try:
            for event in device.read():
                # value 1 = pressed (0 = released, 2 = held down and repeating)
                if event.type == self.evdev.ecodes.EV_KEY and event.value == 1:
                    action = self.key_actions.get(event.code)
                    if action:
                        self._emit(action)
        except BlockingIOError:
            pass                                 # nothing new to read
        except OSError:
            print(f"Remote disconnected: {device.name}")
            self.devices.pop(path, None)
            try:
                device.close()
            except OSError:
                pass

    def _scan(self):
        """Open every input device that sends at least one key from REMOTE_KEYS."""
        evdev = self.evdev
        try:
            paths = evdev.list_devices()
        except OSError:
            return
        if not paths and not self.warned:
            self.warned = True
            print("Remote: no input devices found. Is the clicker's USB receiver plugged in? "
                  "(Reading it needs sudo.)")
        wanted_name = (self.cfg.REMOTE_DEVICE_NAME or "").lower()
        for path in paths:
            if path in self.devices:
                continue
            try:
                device = evdev.InputDevice(path)
                keys = set(device.capabilities().get(evdev.ecodes.EV_KEY, []))
            except OSError:
                continue
            if (device.info.bustype in REMOTE_BUSES and wanted_name in device.name.lower()
                    and keys & self.key_actions.keys()):
                if wanted_name:
                    try:
                        device.grab()            # only this program gets its presses
                    except OSError:
                        pass
                self.devices[path] = device
                print(f"Remote connected: {device.name}")
            else:
                device.close()

    def set_leds(self, on):
        """The main loop tells us the real LED state, so the button stays in step with
        the terminal keys and the browser buttons."""
        self.leds_on = bool(on)

    def _emit(self, action):
        with self.lock:
            self.pending.append(action)
        if action == "restart" and self.on_restart:
            self.on_restart()
        elif action == "leds":
            # Turning them back on restarts the program as well. Firing it from this
            # thread means off-then-on recovers QUBE even if the visuals froze.
            self.leds_on = not self.leds_on
            if self.leds_on and self.on_restart:
                self.on_restart()

    # ---- wired buttons ----------------------------------------------------------
    def _start_gpio_buttons(self):
        for action, pin in self.cfg.GPIO_BUTTONS.items():
            if pin is None:
                continue
            try:
                from gpiozero import Button
                button = Button(pin, pull_up=True, bounce_time=0.05)
                button.when_pressed = lambda action=action: self._emit(action)
                self.buttons.append(button)
                print(f"Remote: wired '{action}' button on GPIO {pin}")
            except Exception as error:
                print(f"Remote: can't use GPIO {pin} for '{action}' ({error})")

    def poll(self):
        """Actions received since the last call, oldest first."""
        with self.lock:
            actions, self.pending = self.pending, []
        return actions

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=2.0)
        for device in list(self.devices.values()):
            try:
                device.close()
            except OSError:
                pass
        self.devices.clear()
        for button in self.buttons:
            button.close()
