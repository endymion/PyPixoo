#!/usr/bin/env python3
"""Generate the gradient test image: #FF00FF top-left fading to #000000 bottom-right."""

from pathlib import Path

from PIL import Image


def main():
    out = Path(__file__).resolve().parent.parent / "features" / "fixtures" / "gradient_magenta_to_black.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    w, h = 64, 64
    img = Image.new("RGB", (w, h))
    pixels = img.load()
    for y in range(h):
        for x in range(w):
            t = (x + y) / 126.0
            r = int(255 * (1 - t))
            g = 0
            b = int(255 * (1 - t))
            pixels[x, y] = (r, g, b)
    img.save(out)
    print(f"Saved {out}")

    # Small image (32×32) to test resize path
    small = Path(__file__).resolve().parent.parent / "features" / "fixtures" / "small_32x32.png"
    img32 = Image.new("RGB", (32, 32), (255, 0, 255))
    img32.save(small)
    print(f"Saved {small}")


if __name__ == "__main__":
    main()
