#!/usr/bin/env python3
"""Demo: Black vertical band animating left-to-right with transparency over gradient background.

Requires a Pixoo 64 at 192.168.0.37. Run from project root:
  PIXOO_REAL_DEVICE=1 python demos/black_band_transparent.py
"""

from pathlib import Path

from pypixoo import Pixoo
from pypixoo.animation import AnimationPlayer, AnimationSequence, Frame
from pypixoo.buffer import Buffer

SIZE = 64
IP = "192.168.0.37"
GRADIENT_PATH = Path(__file__).resolve().parent.parent / "features" / "fixtures" / "gradient_magenta_to_black.png"


def _load_gradient_buffer() -> Buffer:
    from PIL import Image

    img = Image.open(GRADIENT_PATH).convert("RGB")
    if img.size != (SIZE, SIZE):
        img = img.resize((SIZE, SIZE))
    data = [c for pixel in img.getdata() for c in pixel]
    return Buffer.from_flat_list(data)


def _make_band_frame(band_x: int, transparent_color: tuple) -> Buffer:
    """Frame: black vertical band at band_x, rest transparent (transparent_color)."""
    data = []
    for y in range(SIZE):
        for x in range(SIZE):
            if x == band_x:
                data.extend([0, 0, 0])  # black band (visible)
            else:
                data.extend(transparent_color)  # transparent (show background)
    return Buffer.from_flat_list(data)


def main():
    transparent_color = (255, 0, 255)  # magenta = transparent
    gradient = _load_gradient_buffer()
    frames = [
        Frame(image=_make_band_frame(x, transparent_color), duration_ms=50)
        for x in range(SIZE)
    ]
    sequence = AnimationSequence(frames=frames, background=gradient)
    player = AnimationPlayer(
        sequence,
        loop=1,
        end_on="last_frame",
        blend_mode="transparent",
        transparent_color=transparent_color,
    )
    pixoo = Pixoo(IP)
    if not pixoo.connect():
        raise RuntimeError("Failed to connect to Pixoo")
    player.play_async(pixoo)
    player.wait()
    print("Done (transparent blend)")


if __name__ == "__main__":
    main()
