#!/usr/bin/env python3
"""Demo: Chain sequences using on_finished. Sequence 1 (band left-to-right) runs, then
sequence 2 (band right-to-left), then back to sequence 1, in a loop.

Requires a Pixoo 64 at 192.168.0.37. Run from project root:
  PIXOO_REAL_DEVICE=1 python demos/black_band_chained.py

Press Ctrl+C to stop.
"""

import time
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
    """Frame: black vertical band at band_x, rest transparent."""
    data = []
    for y in range(SIZE):
        for x in range(SIZE):
            if x == band_x:
                data.extend([0, 0, 0])
            else:
                data.extend(transparent_color)
    return Buffer.from_flat_list(data)


def main():
    transparent_color = (255, 0, 255)
    gradient = _load_gradient_buffer()

    # Sequence 1: band left-to-right
    seq1 = AnimationSequence(
        frames=[
            Frame(image=_make_band_frame(x, transparent_color), duration_ms=50)
            for x in range(SIZE)
        ],
        background=gradient,
    )
    # Sequence 2: band right-to-left
    seq2 = AnimationSequence(
        frames=[
            Frame(image=_make_band_frame(x, transparent_color), duration_ms=50)
            for x in range(SIZE - 1, -1, -1)
        ],
        background=gradient,
    )

    pixoo = Pixoo(IP)
    try:
        if not pixoo.connect():
            raise RuntimeError("Failed to connect to Pixoo")

        def make_player(seq: AnimationSequence, next_player_getter):
            def on_finished():
                next_player_getter().play_async(pixoo)

            return AnimationPlayer(
                seq,
                loop=1,
                end_on="last_frame",
                blend_mode="transparent",
                transparent_color=transparent_color,
                on_finished=on_finished,
            )

        # Use a list to break circular reference: player1 -> on_finished -> player2 -> on_finished -> player1
        players = []
        player1 = make_player(seq1, lambda: players[1])
        player2 = make_player(seq2, lambda: players[0])
        players.extend([player1, player2])

        print("Chained demo running (Ctrl+C to stop)...")
        player1.play_async(pixoo)

        # Keep main thread alive; animation threads chain indefinitely
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopped")
    finally:
        pixoo.close()


if __name__ == "__main__":
    main()
