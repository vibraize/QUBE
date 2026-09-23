"""
visuals - every visual mode.

**Drop a new .py file in this folder with a VisualMode subclass in it and QUBE
picks it up by itself.** There's no list to edit. The next / previous buttons step
through the modes in order, which is alphabetical by the mode's `name` unless the class
sets `order` (lower numbers come first).

A class with `cycle = False` stays off the buttons' rotation and can only be reached by
its own button or with `--mode`. The QR code does that, because it has its own button.

A file that fails to import is reported and skipped, so a half-finished experiment in
this folder can't stop QUBE from starting.
"""
import importlib
import pkgutil

from visuals.base import VisualMode
from visuals.qr_code import QrCode      # main.py puts this one on its own button

SKIP = {"base", "effects"}              # helpers, not modes


def discover():
    """Import every module in this folder and collect the modes it defines.
    Returns (modes the buttons cycle through, modes that need asking for by name)."""
    cycling, extra = [], []
    for found in sorted(pkgutil.iter_modules(__path__), key=lambda m: m.name):
        if found.name in SKIP:
            continue
        try:
            module = importlib.import_module(f"{__name__}.{found.name}")
        except Exception as error:
            print(f"visuals: skipping {found.name}.py ({type(error).__name__}: {error})")
            continue
        for value in vars(module).values():
            # Only classes defined in this file, so a mode importing another
            # mode doesn't add it twice.
            if (isinstance(value, type) and issubclass(value, VisualMode)
                    and value is not VisualMode and value.__module__ == module.__name__):
                (cycling if value.cycle else extra).append(value)
    in_order = lambda mode: (mode.order, mode.name)
    return sorted(cycling, key=in_order), sorted(extra, key=in_order)


MODES, EXTRA_MODES = discover()


def find_mode(key):
    """Look up a mode by position in MODES (0, 1, 2...) or by part of its name.
    Returns (mode class, index in MODES or None for the button-only ones)."""
    text = str(key).strip().lower().replace(" ", "")
    if text.isdigit() and int(text) < len(MODES):
        return MODES[int(text)], int(text)
    for i, mode in enumerate(MODES):
        if text and text in mode.name.lower().replace(" ", ""):
            return mode, i
    for mode in EXTRA_MODES:
        if text and text in mode.name.lower().replace(" ", ""):
            return mode, None
    names = [m.name for m in MODES + EXTRA_MODES]
    raise ValueError(f"Unknown mode '{key}'. Choose a number 0-{len(MODES) - 1} or one of: {names}")
