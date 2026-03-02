#!/usr/bin/env python3
"""Build the letter A (5 pixels tall) and save to letter_a_rendered.png.

This is the single source of truth for the letter A frame. Push to device with:
  python demos/push_letter_a.py

The A is 3 wide x 5 tall at top-left:
  Row 0: ###   (0,0),(1,0),(2,0)
  Row 1: # #   (0,1),(2,1)  — middle empty
  Row 2: ###   (0,2),(1,2),(2,2)  — crossbar
  Row 3: # #   (0,3),(2,3)
  Row 4: # #   (0,4),(2,4)  — legs only; middle is NOT lit (avoids figure-8 look)
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("PIXOO_REAL_DEVICE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image

from pypixoo import Pixoo

SIZE = 64
FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "letter_a_rendered.png"
IP_DEFAULT = "192.168.0.37"


def build_letter_a_buffer():
    """Return flat RGB list for 64x64: black with 5-pixel-tall A at (0,0)."""
    data = [0] * (SIZE * SIZE * 3)

    def set_(x, y):
        if 0 <= x < SIZE and 0 <= y < SIZE:
            i = (y * SIZE + x) * 3
            data[i] = data[i + 1] = data[i + 2] = 255

    # Left column (0): full 0-4
    for y in range(5):
        set_(0, y)
    # Middle column (1): only top (0) and crossbar (2) — NOT bottom, so it's an A not an 8
    set_(1, 0)
    set_(1, 2)
    # Right column (2): full 0-4
    for y in range(5):
        set_(2, y)

    return data


def save_to_png(data: list, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (SIZE, SIZE))
    px = img.load()
    for y in range(SIZE):
        for x in range(SIZE):
            i = (y * SIZE + x) * 3
            px[x, y] = (data[i], data[i + 1], data[i + 2])
    img.save(path)


def main():
    import argparse
    p = argparse.ArgumentParser(description="Build letter A and optionally push to Pixoo.")
    p.add_argument("--ip", default=IP_DEFAULT, help="Device IP")
    p.add_argument("--no-push", action="store_true", help="Only save PNG, do not push to device")
    args = p.parse_args()

    data = build_letter_a_buffer()
    save_to_png(data, FIXTURE_PATH)
    print(f"Saved: {FIXTURE_PATH}")

    if not args.no_push:
        pixoo = Pixoo(args.ip)
        pixoo.connect()
        pixoo.push_buffer(data)
        pixoo.close()
        print("Pushed to device.")


if __name__ == "__main__":
    main()
