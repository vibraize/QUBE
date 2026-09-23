"""
tools/list_audio_devices.py - list the audio inputs PyAudio can see, and which
sample rates each one accepts.

    python3 tools/list_audio_devices.py

Put the number (or part of the name) in AUDIO_DEVICE in config.py, or pass
--audio-device to main.py. On a Raspberry Pi, ALSA often prints a pile of harmless
warnings before the list - scroll past them.
"""
import pyaudio

RATES = [16000, 22050, 32000, 44100, 48000]


def main():
    pa = pyaudio.PyAudio()
    try:
        try:
            default_index = pa.get_default_input_device_info()["index"]
        except OSError:
            default_index = None
        found = False
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            channels = int(info["maxInputChannels"])
            if channels < 1:
                continue                     # output-only device
            found = True
            rates = []
            for rate in RATES:
                try:
                    if pa.is_format_supported(rate, input_device=i, input_channels=1,
                                              input_format=pyaudio.paInt16):
                        rates.append(rate)
                except ValueError:           # PyAudio's way of saying "not supported"
                    pass
            marker = "   <- default" if i == default_index else ""
            print(f"[{i}] {info['name']}{marker}")
            print(f"     channels: {channels}, default rate: {int(info['defaultSampleRate'])} Hz, "
                  f"mono rates that work: {rates if rates else 'none of ' + str(RATES)}")
        if not found:
            print("No input devices found. Is the USB mic plugged in? On the Pi, try: arecord -l")
    finally:
        pa.terminate()


if __name__ == "__main__":
    main()
