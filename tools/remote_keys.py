"""
tools/remote_keys.py - see which keys the clicker (or any keyboard) sends.

    sudo python3 tools/remote_keys.py

Lists the input devices, then prints every key event. Press each clicker button a
couple of times, then Ctrl+C. Put the key names into REMOTE_KEYS in config.py, and
part of the receiver's name into REMOTE_DEVICE_NAME.
Raspberry Pi / Linux only. Needs python3-evdev.
"""
import select
import sys

try:
    import evdev
    from evdev import ecodes
except ImportError:
    sys.exit("python3-evdev is missing:  sudo apt install python3-evdev")

STATES = {0: "released", 1: "PRESSED", 2: "held"}


def key_name(code):
    name = ecodes.KEY.get(code, f"code {code}")
    if isinstance(name, (list, tuple)):          # some key codes have more than one name
        name = " / ".join(name)
    return name


def main():
    paths = evdev.list_devices()
    if not paths:
        sys.exit("No input devices found. Plug in the clicker's USB receiver and run this with sudo.")

    print("Input devices:")
    watched = {}                                 # file descriptor -> device
    for path in paths:
        try:
            device = evdev.InputDevice(path)
            keys = device.capabilities().get(ecodes.EV_KEY, [])
        except OSError as error:
            print(f"  {path}: can't open ({error})")
            continue
        print(f"  {path}: {device.name!r} ({len(keys)} keys)")
        if keys:
            watched[device.fd] = device
        else:
            device.close()
    if not watched:
        sys.exit("None of these devices have keys.")

    print("\nPress the clicker buttons now. Ctrl+C to stop.\n")
    try:
        while watched:
            ready, _, _ = select.select(list(watched), [], [])
            for fd in ready:
                device = watched[fd]
                try:
                    for event in device.read():
                        if event.type == ecodes.EV_KEY:
                            state = STATES.get(event.value, str(event.value))
                            print(f"{device.name[:32]:32}  {key_name(event.code):28}  {state}")
                except BlockingIOError:
                    pass
                except OSError:
                    print(f"{device.name}: disconnected")
                    del watched[fd]
    except KeyboardInterrupt:
        print()
    finally:
        for device in watched.values():
            device.close()


if __name__ == "__main__":
    main()
