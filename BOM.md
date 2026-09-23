# Bill of materials

Everything needed to build the four-sided cube. Part numbers are given where a part has one;
prices are left out because they change too often to be useful.

The LED panels are the unusual part. They are **not HUB75**, so none of the usual HUB75 adapter
boards will drive them, and the LED library needs a small patch. [WIRING.md](WIRING.md) covers how
they're wired and why; this file covers what to buy.

---

## Controller and inputs

| Qty | Part | Part number / ID | Notes |
|---:|---|---|---|
| 1 | Raspberry Pi 3 Model B | — | The pin map, the library patch and `tools/panel_poke.py` all target this board. A 3 Model B+ has the same header and chip family but hasn't been tested. Other models are untested. |
| 1 | microSD card, 8 GB or larger | — | For Raspberry Pi OS Lite (64-bit). |
| 1 | USB microphone | Adafruit Mini USB Microphone, product **3367** (model M-305) | Rated 100 Hz–8 kHz and 100 dB SPL. The analysis bands in `config.py` go up to 8 kHz to match. Any USB mic that shows up as an ALSA capture device works. |
| 1 | Wireless presenter with a USB receiver | GUMENA wireless presenter (2.4 GHz USB receiver) | The default `REMOTE_KEYS` in `config.py` match its buttons. Any presenter that shows up as a USB keyboard works: `tools/remote_keys.py` shows what its buttons send. The receiver is plug-in, not Bluetooth, so there's nothing to pair. |
| 1 | USB extension cable, short | — | Optional. Moves the presenter's receiver outside the panels if the range is poor. |

## LED panels

| Qty | Part | Part number / ID | Notes |
|---:|---|---|---|
| 4 | LED panel, 40 × 40 pixels, 6.4 mm pitch | **DI-P6.4F03M-8CS-2.7** (materiel code 31-06BF3Y8C27) | 256 × 256 mm, 1/8 scan, arranged as 5 bands of 8 rows. 2×14 (28-pin) input J1 and output J2; power on a 5-pin JST VH header (GND, GND, VCC, VDD, VDD). Drivers: 45× Macroblock JXI5020GP, 5× 74HC245, 74HC138D, 74HC123D. No public datasheet exists. **A different panel needs a different pin map**, and probably a different library patch. |

## Power

| Qty | Part | Part number / ID | Notes |
|---:|---|---|---|
| 1 | USB-C Power Delivery power bank | TALIX 140 W, 20 000 mAh / 73 Wh (Amazon ASIN B0GCDB9KTQ) | USB-A powers the Pi. Two USB-C ports power the panels, two panels each, through a trigger board per port. At 5 V, every port on it is limited to 3 A. See [Power budget](#power-budget). |
| 2 | USB-C PD trigger board, set to 5 V | Adafruit HUSB238 USB-C Power Delivery breakout, switchable, product **5991** — or another HUSB238-based trigger board that can be set to 5 V | One per USB-C port. **On the Adafruit board, set only the 5 V switch on.** With no switch on it asks for the highest voltage the bank offers, up to 20 V, which would destroy the panels. Only change the switches with the cable unplugged. **Other trigger boards pick their voltage in other ways and may come set to something else, so measure the output with a meter, with nothing connected to it, before any panel goes on it.** |
| 1 | USB-A to micro-USB cable, short | — | Powers the Pi. Keep it short and thick: a thin cable drops enough voltage to trip the Pi's undervoltage warning. |
| 2 | USB-C to USB-C cable, 3 A | — | Power bank → trigger boards. |
| 1 | Inline USB-C power meter | — | Strongly recommended. It's the easy way to measure what the panels really draw, and it shows which voltage was negotiated. |

## Wiring and connectors

| Qty | Part | Part number / ID | Notes |
|---:|---|---|---|
| 4 | Panel power leads | JST VH: **VHR-5N** housing + **SVH-21T-P1.1** crimp contacts (22–18 AWG) | One lead per panel, from the output of the trigger board that feeds it. **VCC and VDD each need their own wire to +5 V** — VCC feeds the panel's logic, VDD its LEDs. Use 18 AWG for VDD and GND, which carry the LED current. |
| 1 set | Data link, Pi → first panel | — | 21 signals and 6 grounds, pin by pin in [WIRING.md](WIRING.md). Female–female jumper wires are fine for testing; keep them under about 10 cm. |
| 3 | Data links, panel → panel | 2×14 (28-way) 2.54 mm IDC sockets on 1.27 mm-pitch ribbon cable | J2 of one panel → J1 of the next. Leave conductors **26 (LAT)** and **28 (SR)** unconnected in these: both are fed to every panel directly (next row). |
| 1 set | LAT and SR wires to every panel | — | **Neither signal travels along the chain.** Each panel needs LAT (pin 26) from the Pi's GPIO 4, and SR (pin 28) held at 3.3 V — or 5 V once there's a level-shifter adapter. |

## Level-shifter adapter (recommended — not yet built)

The panels' input buffers run at 5 V and need about 3.3 V to register a logic high, which is exactly
what a Raspberry Pi outputs. It works on short wires, with no margin at all. These parts put a proper
5 V buffer in between. The design isn't finished, so treat this list as a starting point.

| Qty | Part | Part number / ID | Notes |
|---:|---|---|---|
| 3 | 74AHCT245 octal bus transceiver | **SN74AHCT245N** (DIP-20), or any 74AHCT245 | Its TTL-level inputs need only 2.0 V, so a 3.3 V Pi drives it with room to spare. Powered at 5 V. The signal split across the three chips is in [WIRING.md](WIRING.md). |
| 3 | 100 nF ceramic capacitor | — | One across each 74AHCT245's supply pins. |
| 1 | Perfboard or Raspberry Pi prototyping HAT | — | |
| 1 | 2×20 female header, or a 40-way IDC socket | — | To the Pi. |
| 1 | 2×14 shrouded, latching box header | — | To the first panel. Latching connectors survive vibration; jumper wires don't. |
| 3 | Small latching connector, 2-way | — | LAT and SR out to each of the other three panels. |
| 4 | 10 kΩ resistor | — | Pull each panel's SR up to 5 V. |

## Cooling (optional)

| Qty | Part | Part number / ID | Notes |
|---:|---|---|---|
| 4 | 5 V fan | — | Sized to suit the enclosure. The Pi and the panel drivers both warm up inside a closed cube. |
| 1 | SPST toggle switch | — | Fans on and off by hand, independent of the Pi. Wire the fans through it to one of the 5 V supplies, and leave room for their draw in that supply's budget (`LED_WATTS_PER_SUPPLY`, see [Power budget](#power-budget)). |

## Frame

Not part of this repository: something to hold the four 256 × 256 mm panels as the vertical faces of
a cube, with room inside for the Pi, the power bank and the wiring.

## Tools

| Tool | Why |
|---|---|
| Multimeter, with continuity mode | Essential. Every check in [WIRING.md](WIRING.md) uses one: rails, shorts, and whether each signal reaches its panel. |
| Crimping tool for JST VH contacts | For the panel power leads. |
| Soldering iron | For the level-shifter adapter. |
| Logic analyzer | Optional, but the fastest way to see what a panel is actually receiving. |

## Not needed: HUB75 adapters

Boards such as the **Adafruit RGB Matrix Bonnet (product 3211)** can't drive these panels. A HUB75
output carries 6 colour data lines, for the top and bottom halves of one chain; these panels need 15,
for 5 bands of red, green and blue.

---

## Power budget

At 5 V, each USB-C port on the power bank gives at most 3 A: **15 W**. That has to cover the panels on
that port and any fans wired to it.

| Supply | Limit |
|---|---|
| Pi, from the power bank's USB-A port | 5 V at up to 3 A, above the 2.5 A Raspberry Pi recommends for a Pi 3B |
| Two panels, from one USB-C port through a trigger board at 5 V | 15 W, including any fans on that port |
| The other two panels, from a second USB-C port and trigger board | 15 W, including any fans on that port |
| Runtime | roughly 73 Wh ÷ total watts drawn, as an upper bound; conversion losses make it shorter |

**Measured so far:** three panels showing full red drew 15 W from one port, and two panels drew 10 W,
so about **5 W per panel for full red**. 15 W is also the port's ceiling, so the three-panel figure may
have been capped. Green, blue and the panels' draw while dark haven't been measured yet. White lights all
three colours at once: if green and blue draw about what red does, one panel at full white needs about
15 W, and four need 60 W. So even split over two ports, the panels rely on the power limit.

### The power limit

For every frame, `main.py` estimates what the LEDs on each supply will draw. If any supply would go over
its budget, it dims the whole picture, every face alike, just enough. The settings are in `config.py`:

| Setting | What it is |
|---|---|
| `POWER_SUPPLIES` | which faces each supply powers, e.g. `[[0, 1], [2, 3]]` for two supplies. Faces are numbered 0–3; the test pattern's "faces" shows them as 1–4. |
| `LED_WATTS_PER_SUPPLY` | the most the LEDs on one supply may draw: 15 W minus that port's fans, its panels' dark draw, and a margin of 1–2 W |
| `PANEL_FULL_WATTS` | what one whole panel draws at full red, full green and full blue, above its dark draw |

The limit works per supply because a picture isn't spread evenly: two bright faces on one port can
overload it while the cube as a whole looks moderate.

The estimate follows how the LED library really drives the LEDs. It doesn't light a pixel at 0.5 for
half the time: it treats pixel values as perceived brightness (the CIE 1931 curve), so 0.5 is lit 18% of
the time, 0.6 28%, 0.8 57% and 1.0 all of it. The current climbs much faster than `MASTER_BRIGHTNESS`,
and the dimming works on the same curve, so a dimmed frame lands at its budget rather than well under it.

### Measuring

`tools/power_test.py` lights one panel, one colour at a time, bypassing the brightness setting and the
limit. Read the watts for each step on an inline USB-C meter, or the power bank's display if it shows
each port:

1. Stop the boot service (`sudo systemctl stop qube`) and switch the fans off.
2. Run `sudo python3 tools/power_test.py` and note the reading for each step: dark, red, green, blue.
3. In `config.py`, set `PANEL_FULL_WATTS = (red − dark, green − dark, blue − dark)`, and set
   `LED_WATTS_PER_SUPPLY` to 15 − dark − fans − 1 to 2 W of margin. Use the dark reading and the fans'
   draw for one port.
4. Run it again. Its last step, white at 0.7, prints what `config.py` now expects. The reading minus
   dark should come out close; if it doesn't, measure again before relying on the limit.
5. With QUBE running, `main.py`'s report every 5 seconds shows `LEDs want up to … W on a supply`,
   the estimate for the busiest supply before any dimming.

Measure with all the panels chained as QUBE runs, and again after changing `gpio_slowdown`,
`pwm_bits` or the number of panels. The library clocks in the next data while the LEDs are lit, so those
settings change how long the LEDs are lit at full.

With both USB-C ports and the USB-A port in use, check that each port still delivers what it needs.
Some power banks lower their per-port limits when several ports are busy. If the panels ever need more
than 5 V ports can give, the power bank has far more available at 20 V: set a trigger board to 20 V and
add a 20 V → 5 V buck converter rated for the current. **Never connect anything above 5 V to the panels
directly.**
