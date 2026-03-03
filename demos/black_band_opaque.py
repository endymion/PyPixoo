#!/usr/bin/env python3
"""Demo: Black vertical band animating left-to-right without transparency.

Each frame is pre-composited (gradient + black band). Requires a Pixoo 64
(PIXOO_DEVICE_IP or 192.168.0.37). Run from project root:
  python demos/black_band_opaque.py
"""

import os
from pathlib import Path

from dotenv import load_dotenv

from PIL import Image

from pypixoo import CycleItem, GifFrame, GifSequence, Pixoo, UploadMode
from pypixoo.buffer import Buffer

load_dotenv()

SIZE = 64
IP = os.environ.get("PIXOO_DEVICE_IP") or os.environ.get("PIXOO_IP") or "192.168.0.37"
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
        GifFrame(image=_make_band_frame_opaque(x, gradient_data), duration_ms=50)
        for x in range(SIZE)
    ]
    sequence = GifSequence(frames=frames, speed_ms=50)
    pixoo = Pixoo(IP)
    try:
        if not pixoo.connect():
            raise RuntimeError("Failed to connect to Pixoo")
        handle = pixoo.start_cycle(
            [CycleItem(sequence=sequence, upload_mode=UploadMode.COMMAND_LIST, chunk_size=40)],
            loop=1,
        )
        handle.wait(10.0)
        print("Done (opaque)")
    finally:
        pixoo.close()


if __name__ == "__main__":
    main()
