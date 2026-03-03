#!/usr/bin/env python3
"""Demo: Chain two uploaded sequences in a loop using V2 cycle APIs.

Requires a Pixoo 64 (PIXOO_DEVICE_IP or 192.168.0.37). Run from project root:
  python demos/black_band_chained.py

Press Ctrl+C to stop.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from pypixoo import CycleItem, GifFrame, GifSequence, Pixoo, UploadMode
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


def _build_sequence(x_values: list[int], gradient: Buffer) -> GifSequence:
    frames = [
        GifFrame(image=_make_band_frame_opaque(x, gradient), duration_ms=50)
        for x in x_values
    ]
    return GifSequence(frames=frames, speed_ms=50)


def main():
    gradient = _load_gradient_buffer()

    # Sequence 1: band left-to-right
    seq1 = _build_sequence(list(range(SIZE)), gradient)
    # Sequence 2: band right-to-left
    seq2 = _build_sequence(list(range(SIZE - 1, -1, -1)), gradient)

    pixoo = Pixoo(IP)
    try:
        if not pixoo.connect():
            raise RuntimeError("Failed to connect to Pixoo")

        items = [
            CycleItem(sequence=seq1, upload_mode=UploadMode.COMMAND_LIST, chunk_size=40),
            CycleItem(sequence=seq2, upload_mode=UploadMode.COMMAND_LIST, chunk_size=40),
        ]

        print("Chained demo running (Ctrl+C to stop)...")
        handle = pixoo.start_cycle(items, loop=None)
        try:
            handle.wait()
        except KeyboardInterrupt:
            print("\nStopped")
            handle.stop()
            handle.wait(2.0)
    except KeyboardInterrupt:
        print("\nStopped")
    finally:
        pixoo.close()


if __name__ == "__main__":
    main()
