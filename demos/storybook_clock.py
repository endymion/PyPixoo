#!/usr/bin/env python3
"""Play the Storybook Clock story as a smooth native HttpGif sequence.

Requires Storybook running: cd storybook-app && npm run storybook
Requires: pip install -e ".[browser]"
Run: python demos/storybook_clock.py

Press Ctrl+C to stop.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# Demos always use the real device
os.environ.setdefault("PIXOO_REAL_DEVICE", "1")

# Ensure we can import pypixoo (run from project root)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pypixoo import Pixoo, FrameRenderer, UploadMode, WebFrameSource

IP_DEFAULT = "192.168.0.37"
# Clock story iframe URL (t is appended per frame)
CLOCK_URL_DEFAULT = "http://localhost:6006/iframe.html?id=pixoo-clock--default"


def main() -> None:
    parser = argparse.ArgumentParser(description="Loop Storybook Clock smoothly via V2 native sequence upload")
    parser.add_argument("--ip", default=IP_DEFAULT, help=f"Device IP (default: {IP_DEFAULT})")
    parser.add_argument("--url", default=CLOCK_URL_DEFAULT, help="Clock iframe URL")
    parser.add_argument("--fps", type=int, default=10, help="Frames per second (default: 10)")
    parser.add_argument("--loop-seconds", type=float, default=2.0, help="Animation loop length in seconds (default: 2)")
    parser.add_argument(
        "--upload-mode",
        choices=[UploadMode.FRAME_BY_FRAME.value, UploadMode.COMMAND_LIST.value],
        default=UploadMode.COMMAND_LIST.value,
        help="Native upload transport mode",
    )
    parser.add_argument("--chunk-size", type=int, default=40, help="CommandList chunk size")
    args = parser.parse_args()

    fps = max(1, args.fps)
    loop_seconds = max(0.2, args.loop_seconds)
    frame_count = max(2, int(round(fps * loop_seconds)))
    duration_ms = max(20, int(round(1000 / fps)))
    timestamps = [i / frame_count for i in range(frame_count)]

    sources = [
        WebFrameSource(
            url=args.url,
            timestamps=timestamps,
            duration_per_frame_ms=duration_ms,
            browser_mode="persistent",
            timestamp_param="t",
        )
    ]

    print(f"Precomputing {frame_count} Clock frames from Storybook at {fps} FPS...")
    renderer = FrameRenderer(sources)
    seq = renderer.precompute()
    cycle_seconds = (len(seq.frames) * duration_ms) / 1000.0
    print(f"Got {len(seq.frames)} frames (~{cycle_seconds:.2f}s cycle). Connecting to Pixoo...")

    pixoo = Pixoo(args.ip)
    try:
        if not pixoo.connect():
            raise RuntimeError("Failed to connect to Pixoo")

        print("Looping Clock animation with native upload (Ctrl+C to stop)...")
        while True:
            pixoo.upload_sequence(
                seq,
                mode=UploadMode(args.upload_mode),
                chunk_size=args.chunk_size,
            )
            time.sleep(max(0.1, cycle_seconds))
    except KeyboardInterrupt:
        print("\nStopped")
    finally:
        pixoo.close()


if __name__ == "__main__":
    main()
