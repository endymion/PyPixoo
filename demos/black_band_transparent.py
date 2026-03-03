#!/usr/bin/env python3
"""Demo: Black vertical band animating left-to-right with transparency over gradient background.

Requires a Pixoo 64 (PIXOO_DEVICE_IP or 192.168.0.37). Run from project root:
  python demos/black_band_transparent.py
"""

import os
from pathlib import Path

from dotenv import load_dotenv

from pypixoo import GifFrame, GifSequence, Pixoo, UploadMode
from pypixoo.buffer import Buffer

load_dotenv()

SIZE = 64
IP = os.environ.get("PIXOO_DEVICE_IP") or os.environ.get("PIXOO_IP") or "192.168.0.37"
GRADIENT_PATH = Path(__file__).resolve().parent.parent / "features" / "fixtures" / "gradient_magenta_to_black.png"


def _load_gradient_buffer() -> Buffer:
    from PIL import Image

    img = Image.open(GRADIENT_PATH).convert("RGB")
    if img.size != (SIZE, SIZE):
        img = img.resize((SIZE, SIZE))
    data = [c for pixel in img.getdata() for c in pixel]
    return Buffer.from_flat_list(data)


def _make_band_frame_opaque(band_x: int, gradient: Buffer) -> Buffer:
    """Frame: pre-composited gradient with a black vertical band at band_x."""
    data = list(gradient.data)
    for y in range(SIZE):
        base = (y * SIZE + band_x) * 3
        data[base : base + 3] = [0, 0, 0]
    return Buffer.from_flat_list(data)


def main():
    gradient = _load_gradient_buffer()
    frames = [
        GifFrame(image=_make_band_frame_opaque(x, gradient), duration_ms=50)
        for x in range(SIZE)
    ]
    sequence = GifSequence(frames=frames, speed_ms=50)
    pixoo = Pixoo(IP)
    try:
        if not pixoo.connect():
            raise RuntimeError("Failed to connect to Pixoo")
        pixoo.upload_sequence(sequence, mode=UploadMode.FRAME_BY_FRAME, chunk_size=1)
        print("Done (transparent blend)")
    finally:
        pixoo.close()


if __name__ == "__main__":
    main()
