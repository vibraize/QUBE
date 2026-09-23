# Wiring the Pi to the panels

For **DI-P6.4F03M-8CS-2.7** panels (40×40, 28-pin interface) on a Raspberry Pi 3B. Part details are in
[BOM.md](BOM.md).

These panels have no public datasheet, so everything below was worked out by measurement. Every GPIO
and physical pin number was cross-checked against the LED library's own
[hardware-mapping.c](https://github.com/hzeller/rpi-rgb-led-matrix/blob/master/lib/hardware-mapping.c)
and [wiring.md](https://github.com/hzeller/rpi-rgb-led-matrix/blob/master/wiring.md), so the wiring and
the library patch can't drift apart.

**Check against your own board before wiring anything.** On the Pi:

```bash
pinout
```

That prints the header of the Pi you're holding (it comes with `python3-gpiozero`).

---

## The pin map

Pi 40-pin header → the first panel's **J1** (input) header. The panel needs 21 signals: 15 data
(5 bands × red, green, blue), 3 row address (A, B, C), and CLK, LAT and OE.

| Panel pin | Signal | Pi GPIO | Pi pin | Notes |
|---:|---|---|---:|---|
| 1 | RD1 | GPIO 11 | 23 | band 1 red |
| 2 | GD1 | GPIO 27 | 13 | band 1 green |
| 3 | BD1 | GPIO 7 | 26 | band 1 blue |
| 4 | GND | — | 25 | |
| 5 | RD2 | GPIO 12 | 32 | band 2 red |
| 6 | GD2 | GPIO 5 | 29 | band 2 green |
| 7 | BD2 | GPIO 6 | 31 | band 2 blue |
| 8 | GND | — | 30 | |
| 9 | RD3 | GPIO 2 | 3 | band 3 red (has a fixed 1.8 kΩ pull-up to 3.3 V on the Pi) |
| 10 | GD3 | GPIO 3 | 5 | band 3 green (same pull-up) |
| 11 | BD3 | GPIO 26 | 37 | band 3 blue |
| 12 | GND | — | 34 | |
| 13 | RD4 | GPIO 8 | 24 | band 4 red |
| 14 | GD4 | GPIO 9 | 21 | band 4 green |
| 15 | BD4 | GPIO 10 | 19 | band 4 blue |
| 16 | GND | — | 39 | |
| 17 | RD5 | GPIO 13 | 33 | band 5 red |
| 18 | GD5 | GPIO 19 | 35 | band 5 green |
| 19 | BD5 | GPIO 20 | 38 | band 5 blue |
| 20 | GND | — | 20 | |
| 21 | A | GPIO 22 | 15 | row address bit 0 |
| 22 | B | GPIO 23 | 16 | row address bit 1 |
| 23 | C | GPIO 24 | 18 | row address bit 2 |
| 24 | GND | — | 14 | |
| 25 | CLK | GPIO 17 | 11 | shift clock |
| 26 | LAT | GPIO 4 | 7 | latch (the library calls it "strobe"). **Wire it to every panel** — see [Chaining panels](#chaining-panels) |
| 27 | OE | GPIO 18 | 12 | output enable, **active low**; a hardware-PWM pin |
| 28 | SR | 3.3 V | 17 | **must be held high** on every panel, or it stays dark |

**Connect all six grounds.** They're the return path for 21 fast-switching signals, and skipping them
is the classic cause of "it works until it doesn't". Pi pins 6 and 9 are spare grounds.

**The wiring uses no power pins.** Pi pins 2 and 4 (5 V) stay unconnected, and pins 1 and 17 (3.3 V)
feed only the SR lines. The panels are powered from their own supply, never from the Pi.

**Left free:** GPIO 14 and 15 (the serial console, handy for debugging a headless Pi), GPIO 16, 21 and 25
(spare — the obvious choice for wired buttons), and GPIO 0 and 1 (reserved for HAT ID EEPROMs).

### Why these pins

- **OE is on GPIO 18**, the hardware-PWM pin, which gives a much steadier image than software-timed
  output enable. The library won't use it while the Pi's onboard audio (`snd_bcm2835`) is loaded, which
  is why [PI_SETUP.md](PI_SETUP.md) turns the onboard audio off. `--led-no-hardware-pulse` falls back to
  software timing if it ever complains.
- **Bands 1 and 2 match the library's stock `regular` mapping**, so anything written for the standard
  wiring still lines up.
- **GPIO 26 replaces the stock mapping's GPIO 14** for band 3, to keep the serial console free.

---

## How the panels behave

**The 28-pin connector** (2×14): pins 1–20 are the colour data, with every fourth pin a ground; 21–24 are
A, B, C and GND; 25–28 are CLK, LAT, OE and SR. All the pins labelled GND connect to the panel's power
ground, which confirms the pin-1 marking printed on the board.

**Five bands of eight rows.** The 40 rows are 5 bands of 8, each band with its own red, green and blue
data lines, all sharing CLK, LAT, OE and the A/B/C row address. The 74HC138 decodes A/B/C into one of 8
rows, so it's 1/8 scan. Band 1 (pins 1–3) is the first 8 rows.

**Power: both rails want 5 V, on separate wires.** The 5-pin power connector is GND, GND, VCC, VDD, VDD.
VCC and VDD aren't connected to each other. VCC feeds the panel's logic (it runs straight to the
74HC245 buffers' supply pins) and VDD feeds the LEDs. With both on 5 V, a panel measures about
4.8 V on VDD and 4.7 V on VCC, and runs correctly. The JXI5020 drivers want 4.5–5.5 V and the 74HC
chips run on 2–6 V, so both are comfortable there.

> **A phantom voltage to be aware of:** power only VDD and leave VCC unconnected, and VCC still reads
> several volts on a meter — around 3.7 V. That's leakage through the chips' internal protection diodes,
> with no current behind it, not a supply. Wire VCC properly. To tell a real rail from a phantom one,
> hang a resistor (220 Ω – 10 kΩ) from it to ground while powered: a real rail barely moves, a phantom
> one collapses toward 0 V.

**The panel holds CLK, LAT and OE high by itself.** Powered, with nothing connected, pins 25, 26 and 27
sit at about 4.7 V while the data and address lines float. A high OE means "display off", so a panel
powers up blanked and can never light garbage on its own. Don't add your own OE pull-up.

**SR (pin 28) must be held high, or the panel stays dark.** Unconnected it reads 0 V: it's the one
control line the panel gives no safe default. Nothing drives it, and it isn't a signal — tie it to
3.3 V and forget it. That's safe because SR is an input: a panel with a loose wire on pin 28, connected
to nothing, lights intermittently (the loose wire picks up the neighbouring signals like an antenna), and
only an input would care. On a level-shifter adapter, tie it to 5 V through a 10 kΩ resistor.

**A panel is 48 shift-register columns wide, but only 40 have LEDs.** Each colour of each band is driven
by three JXI5020 chips of 16 channels — 48 in a row, 40 used. A 48-column test pattern lines up
identically on every panel in a chain while a 40-column one scatters, and a single walking line pauses
for 8 steps between panels. So the LED library runs with `cols: 48`, and `PANEL_COLUMN_OFFSET` in
`config.py` says where each panel's 40 visible columns sit inside its 48.

**The first pixel clocked out travels furthest.** The library clocks canvas column 0 out first, and
whatever goes in first ends up at the far end of the chain. So canvas column 0 lands on the panel
**furthest from the Pi**. `FACE_ORDER` in `config.py` maps faces to panels from there.

**U7, the 74HC123 dual one-shot, has no known job.** Nothing seems to depend on it.

---

## Chaining panels

The data chains as you'd expect, from one panel's J2 (output) to the next panel's J1 (input). **Two
signals don't**, and have to come from the Pi to every panel directly:

| Signal | Panel pin | What happens otherwise |
|---|---|---|
| SR | 28 | it isn't carried along the chain; the panel stays dark |
| LAT | 26 | in testing it didn't reach the second panel through the chain; wired direct, every panel latches correctly |

Leave pins 26 and 28 **unconnected in the panel-to-panel links**, so no pin is driven from two places.

A missing LAT is sneaky. That panel's latch never closes, so its LEDs follow the shift register live.
**Solid patterns look perfect**, because every column in them carries the same value. Only a single lit
column reveals it — as a wide, dim smear instead of a sharp line. That's what `panel_poke.py --pattern
walk` is for.

---

## Powering up safely

Wire everything with **both the Pi and the panels switched off**. Don't push jumpers onto a live header:
one slip onto a neighbouring pin costs more than the time saved.

**1. Check with a meter before any power goes on.** From each connected wire, confirm there's no DC path
to Pi pins 2 or 4 (5 V). What a healthy, unpowered Pi looks like on a meter:

| Measure | Reads | Why |
|---|---|---|
| any GND → 3.3 V | ~160 Ω | the Pi's own unpowered 3.3 V rail — not a short |
| RD3 (panel pin 9) and GD3 (pin 10) → 3.3 V | ~1.8 kΩ | the Pi's fixed I²C pull-ups on GPIO 2 and 3, which also confirms those two wires |
| 5 V → almost anything | ~200 Ω for a moment, then open | the meter charging the 5 V rail's capacitors: no DC path |

A real short reads a few ohms, holds steady, and reads the same with the probes swapped. Silicon is
directional, so swapping the probes changes a diode path's reading but not a wire's.

**2. Power up: panel supply first, Pi last.** The Pi boots fine with the panels powered or not, but
**don't plug the panels' supply into a power bank while the Pi is running from the same bank**. It can
cause a brief undervoltage on the Pi (`vcgencmd get_throttled` reports `0x50000`), either because the
bank drops its outputs for a moment while it negotiates with the new device, or because of the panels'
inrush current. Connect everything, then switch on.

**Teardown:** `sudo poweroff`, wait for the green ACT LED to stop, then unplug.

Two back-feeding paths exist in principle, and neither causes trouble in practice:

- A powered panel's CLK, LAT and OE pull-ups (4.7 V) trickle into an unpowered Pi through its GPIO
  protection diodes. The Pi boots fine regardless.
- A Pi driving its GPIOs high into an unpowered panel trickles into the panel's VCC through the 74HC245
  input diodes. Each GPIO sources only a few milliamps, so it's harmless over a start-up; just don't
  leave a program driving a dark panel for hours.

A level-shifter adapter removes both paths, but the real reason to build one is signal levels.

---

## Signal levels, and the level-shifter adapter

The panel's inputs are 74HC245 buffers running from VCC. A 74HC input is only guaranteed to read a
high at **0.7 × VCC** — at a VCC of 4.7 V that's 3.3 V, exactly what the Pi outputs. **There's no
margin.** In practice it works over short jumper wires (keep them under about 10 cm), since real CMOS
inputs switch well below the guaranteed threshold, and the library's own docs note many 5 V panels
accept 3.3 V this way. Nothing can be damaged either way: 3.3 V is well within the 74HC245's input limits.

The robust fix is **3× 74AHCT245** powered at 5 V between the Pi and the panels. Its TTL-level inputs
need only 2.0 V, so 3.3 V drives it with room to spare. The pin map doesn't change; the buffers sit in
the middle. A sensible split:

| Chip | Signals |
|---|---|
| A | CLK, LAT, OE, A, B, C (2 channels spare) |
| B | RD1 GD1 BD1, RD2 GD2 BD2, RD3 GD3 |
| C | BD3, RD4 GD4 BD4, RD5 GD5 BD5 |

Each 74AHCT245 needs VCC = 5 V, GND, `DIR` tied **high** (A → B) and `/OE` tied **low** (always on),
plus a 100 nF capacitor across its supply pins. LAT has to fan out to every panel (see
[Chaining panels](#chaining-panels)), and each panel's SR needs a pull-up to 5 V. Use latching
connectors: jumper wires shake loose, and a festival is a lot of vibration.

The library's wiring notes also warn that some panels get erratic below 4.5 V. A panel supply measuring
well under that at the connector usually means a bad crimp — a poor crimp can be ohms, while a short run
of 18 AWG wire drops next to nothing.

---

## The library patch

Stock rpi-rgb-led-matrix can't drive these panels: it allows 3 parallel chains, and it assumes every
chain has two sub-panels (a top and bottom half). These panels need 5 chains — one per band — of one
sub-panel each. `tools/patch_rgbmatrix.py` makes three changes, and [PI_SETUP.md](PI_SETUP.md) step 10
builds the result.

1. **A pin map**, added to `lib/hardware-mapping.c` as `qube-28pin`:

   ```c
     {
       .name                = "qube-28pin",
       .max_parallel_chains = 5,

       .output_enable = GPIO_BIT(18),  /* panel pin 27 */
       .clock         = GPIO_BIT(17),  /* panel pin 25 */
       .strobe        = GPIO_BIT(4),   /* panel pin 26 (LAT) */

       .a             = GPIO_BIT(22),  /* panel pin 21 */
       .b             = GPIO_BIT(23),  /* panel pin 22 */
       .c             = GPIO_BIT(24),  /* panel pin 23 */

       .p0_r1 = GPIO_BIT(11), .p0_g1 = GPIO_BIT(27), .p0_b1 = GPIO_BIT(7),   /* band 1 */
       .p1_r1 = GPIO_BIT(12), .p1_g1 = GPIO_BIT(5),  .p1_b1 = GPIO_BIT(6),   /* band 2 */
       .p2_r1 = GPIO_BIT(2),  .p2_g1 = GPIO_BIT(3),  .p2_b1 = GPIO_BIT(26),  /* band 3 */
       .p3_r1 = GPIO_BIT(8),  .p3_g1 = GPIO_BIT(9),  .p3_b1 = GPIO_BIT(10),  /* band 4 */
       .p4_r1 = GPIO_BIT(13), .p4_g1 = GPIO_BIT(19), .p4_b1 = GPIO_BIT(20),  /* band 5 */
     },
   ```

   `struct HardwareMapping` already declares fields for up to 6 chains, and every pin here is GPIO 2–27,
   so a normal build is enough — no wide-GPIO build.

2. **Five parallel chains, for this map only.** The framebuffer already handles up to 6; the only
   refusal is `Options::Validate()` in `lib/options-initialize.cc`, which caps parallel at 3 (6 only for
   the compute-module map).

3. **One sub-panel per chain.** `ONLY_SINGLE_SUB_PANEL` is only tested in `lib/framebuffer.cc`, and the
   CMake/Python build never defines it, so the patch defines it right above that test. With one
   sub-panel, rows 8 × parallel 5 gives the 40 rows, and the row address uses A/B/C only.

`Validate()` accepts rows 8 and cols 48 as they are. The Python build compiles its fast image path
against Pillow's `Imaging.h`, which on Debian 13 comes from `python3-pil` — the same Pillow the program
runs with. The settings live in `MATRIX_OPTIONS` in `config.py`.

---

## Testing a panel without the LED library

`tools/panel_poke.py` talks to the GPIO registers directly and needs no library at all. That makes it the
quickest way to check a newly wired panel, and the way to tell a wiring fault from a library problem:

```bash
sudo python3 tools/panel_poke.py
```

That lights **band 1 in red at brightness 0.2**, deliberately modest. Then:

| Command | Tells you |
|---|---|
| `--pattern bands` | which panel pins drive which group of 8 rows (it prints the band as it changes) |
| `--pattern rows --band all` | whether A/B/C are wired right, and that it really is 1/8 scan |
| `--pattern columns` | whether the shift clock works |
| `--pattern walk` | which edge data shifts in from — and a missing LAT on a chained panel |
| `--static-row 0` | light with row scanning off, which rules out A/B/C |
| `--cols 96` / `144` / `192` | two, three or four chained panels (48 columns each) |

**Watch the current.** The defaults light at most 40 LEDs at once. `--band all` lights 200, and
`--color white` triples that. A first measurement put a whole panel of full red at about 5 W (1 A at
5 V). White adds green and blue on top (not measured yet), so it could come close to the 3 A a USB-C
port gives at 5 V on its own. Raise `--band`, `--color` and `--brightness` one at a time.

---

## Troubleshooting

### A panel stays dark

1. **SR.** Is that panel's pin 28 at 3.3 V? This is the usual cause.
2. **Is every signal arriving?** Run `panel_poke.py` with its default pattern and measure at the panel's
   J1 header, DC volts against GND. A meter averages a line that's switching fast, so a working signal
   reads somewhere in between:

   | Panel pin | Signal | Expect | If not |
   |---|---|---|---|
   | 1 | RD1 | ~3.3 V, steady | data isn't reaching the panel |
   | 2, 3 | GD1, BD1 | ~0 V | |
   | 21, 22, 23 | A, B, C | ~1.6 V each | 0 V or 3.3 V means that line isn't switching |
   | 25 | CLK | roughly 0.5–1.2 V | 0 V means the clock isn't running |
   | 27 | OE | ~2.6 V | 3.3 V means never enabled, 0 V means always enabled |
   | 28 | SR | 3.3 V | not tied high |

   Skip pin 26 (LAT): its pulses are too short for a meter and it reads near 0 V even when working.
   Jumpers cover the pins, so probe from behind — slide the probe into the back of the jumper's housing,
   or touch J1's solder joints on the back of the board.
3. **Everything arrives but it's still dark?** Try `--oe-active-high`, and check the panel's power rails.

### Reading the symptoms

With every row showing the same data (`--pattern solid`), a fault on one line leaves a recognisable
pattern. The row address counts 0–7 down a band, with A as bit 0, B as bit 1 and C as bit 2.

| What you see | Line at fault | Panel pin | Pi pin |
|---|---|---|---|
| alternating single rows dark | A | 21 | 15 |
| alternating **pairs** of rows dark | B | 22 | 16 |
| half the band (4 rows) dark | C | 23 | 18 |
| a whole band dims or flickers evenly | OE, SR, or the VDD power crimp | 27 / 28 | 12 / 17 |
| speckled or patchy pixels in one band | that band's data line | 1–19 | see the pin map |
| a chained panel smears single columns | LAT not reaching that panel | 26 | 7 |
| an 8-pixel black stripe down one edge of every panel | `PANEL_COLUMN_OFFSET` | — | — |

Why a stuck address line looks like that: if B drops out, the panel reads it stuck at one level, so it
only ever selects the four rows with that value of B. Four rows are lit twice as often; the other four
never.

### The Pi won't boot, or clicks, with the panels wired

The Pi dies when the wiring is connected, won't boot with it already connected, and an LED flickers in
time with a faint ticking from the board. That ticking is a switching regulator in **hiccup mode** —
start, hit the overcurrent limit, shut down, retry — and it means **a short between a Pi power rail and
ground** somewhere in the wiring. Stop retrying: each cycle is a short-circuit event, and repeated hard
power cuts corrupt SD cards.

- **Check any GPIO breakout board end to end with a meter before trusting its labels.** A breakout whose
  "GND" pad isn't really ground, or a ribbon cable shifted by one position inside it, produces exactly
  this. So does an IDC socket pushed onto the Pi's unshrouded header rotated 180° or one column off.
- With everything unpowered, measure 5 V (Pi pin 2) → GND (pin 6), 3.3 V (pin 1) → GND, and 3.3 V → 5 V
  at the Pi end of the wiring. All three should read open, or at least tens of kΩ.
- Pin 4 (5 V) and pin 6 (GND) sit next to each other, so a single stray strand of wire there shorts the
  rail.

### Finding a flaky jumper

Power everything off, set the meter to continuity, put one probe on the Pi pin and one on the panel pin,
and wiggle the jumper. If the beep cuts out, replace it. Dupont jumpers on bare header pins loosen
easily; latching connectors are the permanent fix.
