#!/usr/bin/env python3
"""Play the Storybook Clock story as an animation on the Pixoo.

Requires Storybook running: cd storybook-app && npm run storybook
Requires: pip install -e ".[browser]"
Run: python demos/storybook_clock.py

Press Ctrl+C to stop.
"""

import os
import sys
from pathlib import Path

# Demos always use the real device
os.environ.setdefault("PIXOO_REAL_DEVICE", "1")

# Ensure we can import pypixoo (run from project root)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pypixoo import Pixoo, FrameRenderer, WebFrameSource, AnimationPlayer

IP = "192.168.0.37"
# Clock story iframe URL (t is appended per frame)
CLOCK_URL = "http://localhost:6006/iframe.html?id=pixoo-clock--default"

# 8 frames per full rotation for a smooth sweep
TIMESTAMPS = [i / 8 for i in range(8)]


def main():
    sources = [
        WebFrameSource(
            url=CLOCK_URL,
            timestamps=TIMESTAMPS,
            duration_per_frame_ms=150,
            browser_mode="persistent",
            timestamp_param="t",
        )
    ]
    print("Precomputing Clock frames from Storybook...")
    renderer = FrameRenderer(sources)
    seq = renderer.precompute()
    print(f"Got {len(seq.frames)} frames. Connecting to Pixoo...")

    pixoo = Pixoo(IP)
    try:
        if not pixoo.connect():
            raise RuntimeError("Failed to connect to Pixoo")
        player = AnimationPlayer(seq, loop=1, end_on="last_frame", blend_mode="opaque")
        print("Looping Clock animation (Ctrl+C to stop)...")
        while True:
            player.play_async(pixoo)
            player.wait()
    except KeyboardInterrupt:
        print("\nStopped")
    finally:
        pixoo.close()


if __name__ == "__main__":
    main()
