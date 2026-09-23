# Raspberry Pi setup

From a blank microSD card to a QUBE that starts on its own when it's plugged in. Do the steps in
order. **Don't connect the LED panels until step 10**; how to wire and power them is in
[WIRING.md](WIRING.md).

**You'll need:** a Raspberry Pi 3B, a microSD card and a card reader, a computer, the USB microphone,
the presenter's USB receiver, and a network with internet for the setup (Wi-Fi or Ethernet). The
finished QUBE doesn't need a network. Power the Pi from 5 V at 2.5 A or more — the power bank's USB-A
port works. The parts are listed in [BOM.md](BOM.md).

In the commands below, replace **`YOUR_USER`** with the username you choose in step 1.

---

## 1. Install Raspberry Pi OS Lite

1. Download and open **Raspberry Pi Imager** from [raspberrypi.com/software](https://www.raspberrypi.com/software/).
2. **Device:** Raspberry Pi 3.
3. **OS:** Raspberry Pi OS (other) → **Raspberry Pi OS Lite (64-bit)**.
4. **Storage:** the microSD card.
5. **Customisation:**
   - Hostname: `qube`
   - Localisation: your time zone and keyboard layout
   - Username and password: your choice — write them down
   - Wi-Fi: your network (or leave it off and use Ethernet)
   - Remote access: turn on **Enable SSH**, with password authentication
6. Write the card, put it in the Pi, plug in the **microphone** and the **presenter's USB receiver**,
   then power the Pi. Give the first boot a few minutes.

## 2. Log in

From a terminal on your computer (PowerShell on Windows):

```bash
ssh YOUR_USER@qube.local
```

Type `yes` the first time, then your password. Every command below runs on the Pi unless it says
otherwise.

- `qube.local` not found? Look up the Pi's IP address in your router's device list and use that.
- "Host key verification failed" after re-imaging the card? Run `ssh-keygen -R qube.local` on your
  computer, then try again.

## 3. Update and install packages

```bash
sudo apt update
```

```bash
sudo apt full-upgrade -y
```

```bash
sudo apt install -y git python3-numpy python3-pyaudio python3-evdev python3-pil alsa-utils
```

## 4. Turn off the Pi's onboard audio

The LED library needs the hardware the Pi's built-in audio uses. The USB microphone isn't affected.

```bash
sudo sed -i 's/^dtparam=audio=on/dtparam=audio=off/' /boot/firmware/config.txt
```

```bash
echo "blacklist snd_bcm2835" | sudo tee /etc/modprobe.d/blacklist-rgb-matrix.conf
```

```bash
sudo update-initramfs -u
```

```bash
sudo reboot
```

Wait a minute, then log in again (step 2). Step 6 shows whether the audio is really off.

## 5. Get the project onto the Pi

**With git** (simplest):

```bash
git clone https://github.com/vibraize/QUBE.git ~/qube
```

To update later: `cd ~/qube && git pull`.

**Or copy it from your computer.** On your computer, go to the folder that *contains* the project
folder, then (with the project folder's name in place of `PROJECT_FOLDER`):

```bash
scp -r "PROJECT_FOLDER" YOUR_USER@qube.local:/home/YOUR_USER/qube
```

Two details that both cause confusing errors: give `scp` a **relative** local path, as above — on
Windows a path like `C:\...` is read as a remote computer called `c` — and give it the **full**
remote path rather than `~/qube`, because recent OpenSSH copies over SFTP, which doesn't expand
`~`. To copy a newer version later, first delete the old one as root, since running the program with
`sudo` leaves root-owned files behind:

```bash
sudo rm -rf /home/YOUR_USER/qube
```

**Or from a USB stick**, with no network at all. Copy the project folder onto the stick, plug it into
the Pi, then:

```bash
sudo mount /dev/sda1 /mnt
```

```bash
sudo cp -r "/mnt/PROJECT_FOLDER/." ~/qube/
```

```bash
sudo chown -R "$USER" ~/qube && chmod -R u+rwX ~/qube
```

```bash
cd ~/qube && sudo umount /mnt
```

The `/.` at the end copies the folder's *contents* into `~/qube`; without it you get a second
copy of the folder inside the first. (Filling in the name with Tab stops at the final `/`, so type
the `.` yourself.) The copy runs as root so that nothing already on the Pi can refuse it, and the
third command hands everything back to you and makes it all writable. If `sda1` isn't right, `lsblk`
lists the drives — Pi OS Lite doesn't mount USB sticks by itself.

From here on, every command runs inside the project folder. If your prompt shows just `~ $`, run
`cd ~/qube` first.

## 6. Check the setup

```bash
sudo python3 tools/pi_report.py
```

It only reads information: the Pi model, OS, package versions, whether the onboard audio is off, and
how the Pi sees the microphone and the presenter. Lines starting with `ALSA lib` are normal. Check that
it reports the onboard audio as off and finds a USB microphone.

## 7. Speed test

```bash
python3 tools/benchmark.py
```

Runs each visual for 10 seconds and prints a table. Each has to fit in the 25 ms that 40 frames per
second allows. On a Pi 3B the lightest take a few ms a frame and the heaviest over 10 ms.

## 8. Presenter buttons

The default keys in `config.py` match the presenter in [BOM.md](BOM.md), so skip this step if that's
the one you have. For a different one:

```bash
sudo python3 tools/remote_keys.py
```

Press each button twice, slowly: up arrow, down arrow, black screen (square), full screen (double
square). `Ctrl+C` stops it. Put the key names it shows into `REMOTE_KEYS` in `config.py`.

## 9. Microphone, preview and presenter test

```bash
sudo python3 main.py --display web --mode meter --leds on
```

Open **http://qube.local:8080** on a phone or computer on the same network, and check:

1. **Microphone:** talk, clap and play music near it. The six bars should move separately — a snap
   lights the top ones far more than the bottom ones — and the border flashes on beats. Note the
   `mic __ dB` number at the top of the page in a quiet room, and again with quiet music playing:
   `SILENCE_DB` in `config.py` belongs between the two.
2. **Up / down arrows:** switch between the visuals.
3. **Black screen (square):** the preview goes black and shows "LEDs OFF". Press it again and the LEDs
   come back on **and the program restarts** (the page shows "waiting for QUBE..." for a few
   seconds).
4. **Full screen (double square):** the QR code appears on every face. Press again to go back.

Stop with `Ctrl+C`. If the bars barely move, the mic's input level may be low: run `alsamixer`, press
`F6` to pick the USB mic, `F4` for capture, and raise the level with the arrow keys (`Esc` to exit).

## 10. Build the LED library, and light the panels

The stock rpi-rgb-led-matrix can't drive the 28-pin panels. `tools/patch_rgbmatrix.py` adds what's
missing: the pin map, the 5 bands driven as parallel chains, and one sub-panel per band
([WIRING.md](WIRING.md) explains each change). **This needs internet on the Pi**, because the build
downloads its tools. Check:

```bash
ping -c 2 github.com
```

Install the build tools. `python3-pil` provides the Pillow header (`Imaging.h`) that the library's fast
image path is compiled against, so it always matches the Pillow the program runs with:

```bash
sudo apt install -y build-essential cmake python3-dev python3-pip python3-pil
```

Download the library, patch it, then build and install it. The last command compiles the whole
library twice, which takes several minutes on a Pi 3. Let it finish.

```bash
cd ~ && git clone https://github.com/hzeller/rpi-rgb-led-matrix.git
```

```bash
python3 ~/qube/tools/patch_rgbmatrix.py ~/rpi-rgb-led-matrix
```

```bash
cd ~/rpi-rgb-led-matrix && sudo pip install . --break-system-packages
```

`--break-system-packages` is how Debian 13 allows installing a Python package system-wide. It only
adds `rgbmatrix`, and system-wide is where `sudo python3` looks. Check it worked:

```bash
sudo python3 -c "from rgbmatrix import RGBMatrix; print('rgbmatrix OK')"
```

Now wire and power the panels as described in [WIRING.md](WIRING.md) — including **SR held high and
LAT wired on every panel** — and plug in the panels' supply before the Pi. Then:

```bash
cd ~/qube && sudo python3 main.py --display matrix --fake-audio --leds on
```

`--fake-audio` plays a built-in test beat so the picture moves without music, and `--leds on` skips the
dark start. With fewer than four panels connected, add `--chain` and the number (`--chain 3`). Drop
`--fake-audio` to use the microphone.

If the picture glitches, `gpio_slowdown` in `config.py` is already 4, the safest; once it looks clean,
try 3, then 2, for a faster refresh. Then run `sudo python3 tools/test_pattern.py` to check the faces
are in order and the right way up, and adjust `FACE_ORDER`, `FACE_ROTATION`, `FACE_MIRROR` and
`PANEL_COLUMN_OFFSET` in `config.py` to match.

Once `gpio_slowdown` is settled and all the panels are chained, measure what they draw with
`sudo python3 tools/power_test.py` and set up the power limit, before turning `MASTER_BRIGHTNESS` up.
[BOM.md](BOM.md#measuring) walks through it.

Retrying? Skip the `git clone` if the folder already exists. The patch script is safe to run twice. If
you ever `git pull` a newer version of the library, run the patch and `pip` steps again. If the patch
script stops with "The library has probably changed" on a folder that was patched before, undo the
old patch with `git -C ~/rpi-rgb-led-matrix checkout -- lib`, then patch and build again.

## 11. Run on its own at boot

This makes QUBE self-contained: plug it in and it runs, with no keyboard or computer.

```bash
sudo bash deploy/install_service.sh matrix
```

Reboot with `sudo reboot`. A minute later the program is running: every pixel shows **red, then
green, then blue** for a second each, and then the first visual starts. That's the sign booting has
finished. The presenter works from then on, and its square button turns the LEDs off and on. To have
it boot dark and wait for that button instead, set `START_WITH_LEDS_OFF = True` in `config.py`.

Check on it any time:

```bash
journalctl -u qube -f
```

systemd restarts it if it crashes, and if the program freezes for 30 seconds, systemd kills it and
starts it again. Turning the LEDs off and on with the presenter restarts it too.

**While you're still working on it**, stop the service first, or two copies will fight over the panels:

```bash
sudo systemctl stop qube
```

`sudo systemctl start qube` puts it back, and `sudo systemctl disable --now qube` turns off
starting at boot altogether.
