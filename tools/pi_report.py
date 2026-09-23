"""
tools/pi_report.py - a one-page summary of the Raspberry Pi setup, for checking it (or
for pasting into a bug report).

    sudo python3 tools/pi_report.py

It only reads information; it doesn't change anything. Lines starting with
"ALSA lib" come from the audio system while PyAudio starts, and are normal.
"""
import importlib
import os
import platform
import subprocess
import sys


def read_file(path):
    try:
        with open(path, errors="replace") as f:
            return f.read()
    except OSError:
        return None


def run(command):
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=20)
        return (result.stdout + result.stderr).strip() or "(no output)"
    except (OSError, subprocess.TimeoutExpired) as error:
        return f"(couldn't run {command[0]}: {error})"


def heading(title):
    print(f"\n===== {title} =====")


def main():
    heading("System")
    model = read_file("/proc/device-tree/model")
    print("Model:", model.replace("\x00", "").strip() if model else "unknown")
    for line in (read_file("/etc/os-release") or "").splitlines():
        if line.startswith(("PRETTY_NAME=", "VERSION_CODENAME=")):
            print(line)
    print("Kernel:", platform.release(), platform.machine())
    print("Python:", sys.version.split()[0], "at", sys.executable)
    print("Running as root:", hasattr(os, "geteuid") and os.geteuid() == 0)
    meminfo = read_file("/proc/meminfo") or ""
    print(next((l for l in meminfo.splitlines() if l.startswith("MemTotal")), "MemTotal: unknown"))
    print("CPU cores:", os.cpu_count())
    print("Power/throttling:", run(["vcgencmd", "get_throttled"]), "(throttled=0x0 means no problems)")
    print("isolcpus in kernel command line:", "isolcpus" in (read_file("/proc/cmdline") or ""))

    heading("Python packages")
    for module in ("numpy", "pyaudio", "evdev", "PIL", "gpiozero", "rgbmatrix"):
        try:
            imported = importlib.import_module(module)
            print(f"{module}: {getattr(imported, '__version__', 'installed')}")
        except Exception as error:
            print(f"{module}: not available ({type(error).__name__}: {error})")

    heading("Onboard audio (should be off)")
    modules = read_file("/proc/modules") or ""
    loaded = any(line.split(" ")[0] == "snd_bcm2835" for line in modules.splitlines())
    print("snd_bcm2835 loaded:", loaded)
    for path in ("/boot/firmware/config.txt", "/boot/config.txt"):
        text = read_file(path)
        if text is not None:
            lines = [line.strip() for line in text.splitlines() if "audio" in line]
            print(f"{path}:", lines if lines else "no audio lines")
            break
    blacklist = read_file("/etc/modprobe.d/blacklist-rgb-matrix.conf")
    print("Blacklist file:", blacklist.strip() if blacklist else "missing")

    heading("USB devices (lsusb)")
    print(run(["lsusb"]))

    heading("Recording devices (arecord -l)")
    print(run(["arecord", "-l"]))

    heading("PyAudio inputs")
    try:
        import list_audio_devices      # tools/list_audio_devices.py
        list_audio_devices.main()
    except Exception as error:
        print(f"couldn't list them ({type(error).__name__}: {error})")

    heading("Input devices (clicker)")
    try:
        import evdev
        paths = evdev.list_devices()
        if not paths:
            print("none found (plug in the clicker's receiver, and run this with sudo)")
        for path in paths:
            try:
                device = evdev.InputDevice(path)
                key_count = len(device.capabilities().get(evdev.ecodes.EV_KEY, []))
                print(f"{path}: {device.name!r} ({key_count} keys)")
                device.close()
            except OSError as error:
                print(f"{path}: can't open ({error})")
    except ImportError:
        print("python3-evdev not installed")


if __name__ == "__main__":
    main()
