#!/usr/bin/env python3
"""Demo: Black vertical band animating left-to-right without transparency.

Each frame is pre-composited (gradient + black band). Requires a Pixoo 64 at 192.168.0.37.
Run from project root:
  PIXOO_REAL_DEVICE=1 python demos/black_band_opaque.py
"""

from pathlib import Path

from PIL import Image

from pypixoo import Pixoo
from pypixoo.animation import AnimationPlayer, AnimationSequence, Frame
from pypixoo.buffer import Buffer

SIZE = 64
IP = "192.168.0.37"
GRADIENT_PATH = Path(__file__).resolve().parent.parent / "features" / "fixtures" / "gradient_magenta_to_black.png"


def _load_gradient_data() -> list:
    img = Image.open(GRADIENT_PATH).convert("RGB")
    if img.size != (SIZE, SIZE):
        img = img.resize((SIZE, SIZE))
    return [c for pixel in img.getdata() for c in pixel]


def _make_band_frame_opaque(band_x: int, gradient_data: list) -> Buffer:
    """Frame: gradient with black vertical band at band_x drawn on top."""
    data = list(gradient_data)
    for y in range(SIZE):
        base = (y * SIZE + band_x) * 3
        data[base : base + 3] = [0, 0, 0]
    return Buffer.from_flat_list(data)


def main():
    gradient_data = _load_gradient_data()
    frames = [
        Frame(image=_make_band_frame_opaque(x, gradient_data), duration_ms=50)
        for x in range(SIZE)
    ]
    sequence = AnimationSequence(frames=frames)
    player = AnimationPlayer(
        sequence,
        loop=1,
        end_on="last_frame",
        blend_mode="opaque",
    )
    pixoo = Pixoo(IP)
    try:
        if not pixoo.connect():
            raise RuntimeError("Failed to connect to Pixoo")
        player.play_async(pixoo)
        player.wait()
        print("Done (opaque)")
    finally:
        pixoo.close()


if __name__ == "__main__":
    main()
