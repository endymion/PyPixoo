#!/usr/bin/env python3
"""Demo: Mix static frames and browser-rendered frames in one sequence.

Uses FrameRenderer with StaticFrameSource (solid buffers) and WebFrameSource
(pointing at a local HTML fixture). Demonstrates on_first_frame and on_all_frames
callbacks, then plays the sequence on the device in a loop until Ctrl+C.

Requires: pip install -e ".[browser]" (Playwright)
Requires a Pixoo 64 at 192.168.0.37. Run from project root:

  python demos/browser_mixed.py
"""

import os
from pathlib import Path
import time

# Demos always use the real device
os.environ.setdefault("PIXOO_REAL_DEVICE", "1")

from pypixoo import Pixoo, FrameRenderer, StaticFrameSource, WebFrameSource, AnimationPlayer
from pypixoo.buffer import Buffer

SIZE = 64
IP = "192.168.0.37"

# Local HTML that changes color with query param ?t=0..1 (see demos/fixtures/web_frame.html)
FIXTURE_HTML = (
    Path(__file__).resolve().parent / "fixtures" / "web_frame.html"
)
WEB_URL = FIXTURE_HTML.as_uri() if FIXTURE_HTML.exists() else None


def _solid_buffer(r: int, g: int, b: int) -> Buffer:
    data = [c for _ in range(SIZE * SIZE) for c in (r, g, b)]
    return Buffer.from_flat_list(data)


def main():
    if not FIXTURE_HTML.exists():
        raise FileNotFoundError(
            f"Fixture not found: {FIXTURE_HTML}. Run from project root."
        )

    # Static frames: solid red, then solid blue
    red = _solid_buffer(255, 0, 0)
    blue = _solid_buffer(0, 0, 255)

    # Web frames: HTML at t=0, 0.5, 1.0 (different colors)
    sources = [
        StaticFrameSource(buffer=red, duration_ms=200),
        WebFrameSource(
            url=WEB_URL,
            timestamps=[0.0, 0.5, 1.0],
            duration_per_frame_ms=150,
            browser_mode="persistent",
            timestamp_param="t",
        ),
        StaticFrameSource(buffer=blue, duration_ms=200),
    ]

    first_ready = []
    all_ready = []

    renderer = FrameRenderer(sources)
    print("Precomputing frames (static + browser)...")
    sequence = renderer.precompute(
        on_first_frame=lambda: first_ready.append(True),
        on_all_frames=lambda: all_ready.append(True),
    )

    if first_ready:
        print("(on_first_frame was called when first web frame was ready)")
    if all_ready:
        print("(on_all_frames was called when all frames were ready)")

    print(f"Sequence has {len(sequence.frames)} frames. Connecting to Pixoo...")
    pixoo = Pixoo(IP)
    try:
        if not pixoo.connect():
            raise RuntimeError("Failed to connect to Pixoo")

        player = AnimationPlayer(
            sequence,
            loop=1,
            end_on="last_frame",
            blend_mode="opaque",
        )

        print("Looping (Ctrl+C to stop)...")
        while True:
            player.play_async(pixoo)
            player.wait()
    except KeyboardInterrupt:
        print("\nStopped")
    finally:
        pixoo.close()


if __name__ == "__main__":
    main()
