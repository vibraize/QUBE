"""
controls.py - keyboard control from the terminal (for example over SSH).

    n or space   next mode          p   previous mode
    0-9          jump to a mode     l   LEDs off; on again also restarts
    + / -        brightness         r   restart the program
    c            QR code on/off     q   quit

Works in Linux terminals and Windows consoles. When there's no terminal (for
example when started as a background service) it quietly does nothing.
"""
import os
import sys


class KeyReader:
    def __init__(self):
        self.enabled = sys.stdin is not None and sys.stdin.isatty()
        self._restore = None
        self._msvcrt = None
        if not self.enabled:
            return
        try:
            import msvcrt                     # only exists on Windows
            self._msvcrt = msvcrt
        except ImportError:
            try:
                import termios
                import tty
                fd = sys.stdin.fileno()
                saved = termios.tcgetattr(fd)
                tty.setcbreak(fd)             # deliver keys immediately, without Enter
                self._restore = lambda: termios.tcsetattr(fd, termios.TCSADRAIN, saved)
            except Exception:
                self.enabled = False

    def read_keys(self):
        """Every key pressed since the last call, as a list of characters."""
        if not self.enabled:
            return []
        keys = []
        if self._msvcrt:
            while self._msvcrt.kbhit():
                keys.append(self._msvcrt.getwch())
        else:
            import select
            fd = sys.stdin.fileno()
            while select.select([fd], [], [], 0)[0]:
                data = os.read(fd, 32)
                if not data:
                    break
                keys.extend(data.decode(errors="ignore"))
        return keys

    def close(self):
        """Put the terminal back to normal."""
        if self._restore:
            self._restore()
            self._restore = None


def key_to_command(key):
    """Translate a key press into a command name (or None)."""
    if key in ("n", "N", " "):
        return "next"
    if key in ("p", "P"):
        return "prev"
    if key in ("l", "L"):
        return "leds"
    if key in ("r", "R"):
        return "restart"
    if key in ("c", "C"):
        return "qr"
    if key in ("+", "="):
        return "brighter"
    if key in ("-", "_"):
        return "dimmer"
    if key in ("q", "Q"):
        return "quit"
    if key.isdigit():
        return "mode:" + key
    return None
