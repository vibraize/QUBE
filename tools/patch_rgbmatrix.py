"""
tools/patch_rgbmatrix.py - teach rpi-rgb-led-matrix to drive QUBE's 28-pin panels.

    python3 tools/patch_rgbmatrix.py ~/rpi-rgb-led-matrix

Three small changes, written against the library's master branch as of September 2026:

  1. lib/hardware-mapping.c     adds the "qube-28pin" pin map (the same pins as WIRING.md)
  2. lib/options-initialize.cc  allows 5 parallel chains for that map (the stock limit is 3)
  3. lib/framebuffer.cc         one sub-panel per chain, so each band is 8 rows on A/B/C

Why this works: each panel has 5 bands of 8 rows, each band with its own R/G/B data lines
sharing clock, latch, output enable and row address. That is exactly how the library
drives "parallel chains", so each band becomes one chain. The library's framebuffer
already handles up to 6 chains; only the option check and the sub-panel default stop it.

Safe to run twice: files that are already patched are left alone. If the library has
changed so a change can't be applied exactly, it stops and says which one, before
writing anything.
"""
import os
import sys

MARK = "qube-28pin"

MAPPING = """  /*
   * qube-28pin: DI-P6.4F03M-8CS-2.7 40x40 panels with a 2x14 (28-pin) connector.
   * 5 bands of 8 rows (RD1-5/GD1-5/BD1-5), 1/8 scan on A/B/C. Needs the
   * single-sub-panel build, so only r1/g1/b1 of each chain are used.
   * Panel pin 28 (SR) must be held high; it is a fixed level, not in this map.
   * Pin numbers: see WIRING.md in the QUBE project.
   */
  {
    .name                = "qube-28pin",
    .max_parallel_chains = 5,

    .output_enable = GPIO_BIT(18),  /* panel pin 27 */
    .clock         = GPIO_BIT(17),  /* panel pin 25 */
    .strobe        = GPIO_BIT(4),   /* panel pin 26 (LAT) */

    .a             = GPIO_BIT(22),  /* panel pin 21 */
    .b             = GPIO_BIT(23),  /* panel pin 22 */
    .c             = GPIO_BIT(24),  /* panel pin 23 */

    .p0_r1 = GPIO_BIT(11), .p0_g1 = GPIO_BIT(27), .p0_b1 = GPIO_BIT(7),   /* band 1: pins 1-3 */
    .p1_r1 = GPIO_BIT(12), .p1_g1 = GPIO_BIT(5),  .p1_b1 = GPIO_BIT(6),   /* band 2: pins 5-7 */
    .p2_r1 = GPIO_BIT(2),  .p2_g1 = GPIO_BIT(3),  .p2_b1 = GPIO_BIT(26),  /* band 3: pins 9-11 */
    .p3_r1 = GPIO_BIT(8),  .p3_g1 = GPIO_BIT(9),  .p3_b1 = GPIO_BIT(10),  /* band 4: pins 13-15 */
    .p4_r1 = GPIO_BIT(13), .p4_g1 = GPIO_BIT(19), .p4_b1 = GPIO_BIT(20),  /* band 5: pins 17-19 */
  },

"""

# (file, what to find, what to put in its place). Each "find" must appear exactly once.
CHANGES = [
    ("lib/hardware-mapping.c",
     "  {0}\n};",
     MAPPING + "  {0}\n};"),
    ("lib/options-initialize.cc",
     "if (parallel < 1 || parallel > (is_cm ? 6 : 3)) {",
     "// qube-28pin: 5 bands per panel, each driven as a parallel chain.\n"
     "  const bool is_qube = hardware_mapping != nullptr\n"
     "      && strcmp(hardware_mapping, \"qube-28pin\") == 0;\n"
     "  if (parallel < 1 || parallel > (is_cm ? 6 : (is_qube ? 5 : 3))) {"),
    ("lib/framebuffer.cc",
     "#ifdef ONLY_SINGLE_SUB_PANEL",
     "#define ONLY_SINGLE_SUB_PANEL  // qube-28pin: each band is one 8-row sub-panel\n"
     "#ifdef ONLY_SINGLE_SUB_PANEL"),
]


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: python3 tools/patch_rgbmatrix.py <path to rpi-rgb-led-matrix>")
    root = os.path.expanduser(sys.argv[1])

    # Check everything first, so a problem never leaves the library half patched.
    plan = []
    for name, find, replace in CHANGES:
        path = os.path.join(root, name)
        try:
            with open(path, encoding="utf-8", newline="") as f:
                text = f.read()
        except OSError as error:
            sys.exit(f"Can't read {path}: {error}\nIs {root} the rpi-rgb-led-matrix folder?")
        if "\r\n" in text:
            text_lf = text.replace("\r\n", "\n")
        else:
            text_lf = text
        if MARK in text_lf:
            print(f"  already patched: {name}")
            continue
        count = text_lf.count(find)
        if count != 1:
            sys.exit(f"Can't patch {name}: expected to find this once, found it {count} times:\n"
                     f"    {find!r}\nThe library has probably changed. Nothing was modified.")
        plan.append((path, name, text_lf.replace(find, replace)))

    for path, name, new_text in plan:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(new_text)
        print(f"  patched: {name}")
    print("Done. Build and install with:  sudo pip install . --break-system-packages")


if __name__ == "__main__":
    main()
