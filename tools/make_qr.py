"""
tools/make_qr.py - build the QR code shown by the QR Code mode.

    python3 tools/make_qr.py "https://example.com"  # point it somewhere else
    python3 tools/make_qr.py                        # rebuild the link it has now

Prints QR_URL and QR_ROWS ready to paste into visuals/qr_code.py, plus a preview.
Needs the `segno` library, which is only used here, never on the Pi at show time:

    pip install segno

The code has to fit a 40x40 face with a quiet zone round it, so 25x25 modules is the
practical limit: that means about 26 characters at error correction level M. Longer
URLs need a bigger version, which won't fit. Keep links short.
"""
import os
import sys

FACE = 40
MAX_MODULES = 33        # 33 + a 4-pixel quiet zone each side is the most a 40x40 face fits


def current_url():
    """The link visuals/qr_code.py holds now, so it only ever lives in one place."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from visuals.qr_code import QR_URL
    return QR_URL


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else current_url()
    try:
        import segno
    except ImportError:
        sys.exit("This needs the segno library:  pip install segno")

    code = segno.make(url, error="m", boost_error=False)
    rows = ["".join("#" if bit else "." for bit in row) for row in code.matrix]
    size = len(rows)
    print(f"{url!r}: {len(url)} characters, version {code.version}, "
          f"error correction {code.error}, {size}x{size} modules")

    if size > MAX_MODULES:
        sys.exit(f"That's {size} modules, too big for a {FACE}x{FACE} face with a quiet "
                 f"zone. Use a shorter link (a redirect service, say).")
    border = (FACE - size) // 2
    print(f"quiet zone: {border} pixels each side (4 is the minimum)\n")

    for row in rows:                                  # preview, 2 chars per module
        print("  " + "".join("##" if c == "#" else "  " for c in row))

    print("\n--- paste over QR_URL and QR_ROWS in visuals/qr_code.py ---")
    print(f'QR_URL = "{url}"')
    print("QR_ROWS = (")
    for row in rows:
        print(f'    "{row}",')
    print(")")

    try:                                              # optional: read it back to be sure
        import numpy as np
        from pyzbar.pyzbar import decode
    except ImportError:
        print("\n(install pyzbar and numpy to have this script check the code by decoding it)")
        return 0
    face = np.full((FACE, FACE), 255, dtype=np.uint8)
    for y, row in enumerate(rows):
        for x, character in enumerate(row):
            if character == "#":
                face[border + y, border + x] = 0
    big = np.repeat(np.repeat(face, 12, axis=0), 12, axis=1)
    found = [d.data.decode() for d in decode((big.tobytes(), big.shape[1], big.shape[0]))]
    print(f"\ndecoded back as: {found}")
    print("OK" if found == [url] else "*** it did not decode back to the URL ***")
    return 0 if found == [url] else 1


if __name__ == "__main__":
    sys.exit(main())
