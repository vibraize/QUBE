"""
service.py - restarting the program, and the systemd watchdog.

Restart
    Turning the LEDs back on with the clicker (also 'r' in the terminal, or the
    browser's Restart button) asks for a restart. The main loop stops, cleans up
    (panels go dark, mic closes) and the program starts again from the top of main.py
    with the same command-line options. If the main loop is frozen and doesn't stop
    within RESTART_FORCE_SECONDS, a safety timer forces the restart anyway.

Remembering the LEDs
    The square button turns the LEDs off, and QUBE can also be set to power up dark
    (START_WITH_LEDS_OFF in config.py).
    But turning them on restarts the program, so the restart has to come back with
    them ON, or the button would never seem to work. The state is therefore kept in a
    file under /run, which systemd clears on every boot: it survives a restart, and
    it doesn't survive unplugging QUBE.

Watchdog
    When QUBE runs as a systemd service (deploy/qube.service), the main
    loop keeps telling systemd "still alive". If those messages stop because the
    program froze, systemd kills it and starts it again. Outside systemd this
    quietly does nothing.
"""
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time

RESTART_EXIT_CODE = 75   # exit code for a forced restart under systemd (Restart=always starts it again)


def led_state_file():
    """Where the LED on/off state lives between restarts. /run is wiped at every boot,
    which is exactly what we want; anywhere else it would survive a power cycle."""
    run = "/run"
    if os.path.isdir(run) and os.access(run, os.W_OK):
        return os.path.join(run, "qube-leds")
    return os.path.join(tempfile.gettempdir(), "qube-leds")


def remember_leds(on):
    """Remember the LED state so a restart comes back the same way."""
    try:
        with open(led_state_file(), "w", encoding="utf-8") as f:
            f.write("on" if on else "off")
    except OSError:
        pass            # not worth failing over: we just lose the state on a restart


def recall_leds(default):
    """The LED state from before a restart, or `default` on a fresh boot."""
    try:
        with open(led_state_file(), encoding="utf-8") as f:
            return f.read().strip() == "on"
    except OSError:
        return default


def running_under_systemd():
    """True when systemd started this program (systemd sets INVOCATION_ID for its services)."""
    return bool(os.environ.get("INVOCATION_ID"))


def notify_systemd(message):
    """Send a notification such as "WATCHDOG=1" to systemd (the sd_notify protocol)."""
    address = os.environ.get("NOTIFY_SOCKET")
    if not address:
        return                                   # not started by systemd
    if address.startswith("@"):
        address = "\0" + address[1:]             # "@" means an abstract socket name
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
            sock.connect(address)
            sock.sendall(message.encode("utf-8"))
    except OSError:
        pass


class Watchdog:
    """Pings the systemd watchdog. Call ping() from the main loop; every frame is fine."""

    def __init__(self):
        usec = os.environ.get("WATCHDOG_USEC")
        pid = os.environ.get("WATCHDOG_PID")
        if usec and pid in (None, str(os.getpid())):
            self.interval = int(usec) / 1_000_000 / 2.0   # ping twice per watchdog timeout
        else:
            self.interval = None                        # no watchdog configured
        self.last = 0.0

    def ping(self):
        if self.interval is None:
            return
        now = time.monotonic()
        if now - self.last >= self.interval:
            notify_systemd("WATCHDOG=1")
            self.last = now


def without_option(options, name):
    """`options` without `name` and its value, written either "--x v" or "--x=v"."""
    kept, skip = [], False
    for option in options:
        if skip:
            skip = False
        elif option == name:
            skip = True                      # the value that follows goes too
        elif not option.startswith(name + "="):
            kept.append(option)
    return kept


def restart_program(script):
    """Run the program again from the top, with the same command-line options - except
    --leds. The button that asks for this restart is the LEDs button, so its choice (kept
    in the file below) has to win, or one --leds off at the start would last forever."""
    args = [sys.executable, os.path.abspath(script)] + without_option(sys.argv[1:], "--leds")
    sys.stdout.flush()
    sys.stderr.flush()
    if os.name == "nt":
        # Windows can't replace a running program, so start a new copy and pass on its exit code
        os._exit(subprocess.call(args))
    os.execv(sys.executable, args)       # Linux: this process becomes a fresh start of the program


class RestartRequest:
    """A restart request that any thread can make, plus a safety timer that forces the
    restart if the main loop doesn't get there (for example because it froze)."""

    def __init__(self, script, force_after_seconds, before_force=None):
        self.script = script
        self.force_after = force_after_seconds
        self.before_force = before_force     # quick emergency cleanup, e.g. restoring the terminal
        self.event = threading.Event()
        self.lock = threading.Lock()
        self.timer = None

    def request(self):
        with self.lock:
            if self.event.is_set():
                return                       # already on its way
            self.event.set()
            self.timer = threading.Timer(self.force_after, self._force)
            self.timer.daemon = True
            self.timer.start()

    def requested(self):
        return self.event.is_set()

    def cancel_timer(self):
        with self.lock:
            if self.timer:
                self.timer.cancel()

    def _force(self):
        print(f"The program didn't stop within {self.force_after} s - forcing a restart.", flush=True)
        if self.before_force:
            try:
                self.before_force()
            except Exception:
                pass
        if running_under_systemd():
            os._exit(RESTART_EXIT_CODE)          # systemd starts it again
        else:
            try:
                restart_program(self.script)
            except Exception:
                os._exit(RESTART_EXIT_CODE)
