#!/usr/bin/env python3
"""Push a single white pixel at (0,0) to the device.

Pixel alignment test: black background, one white pixel at top-left.
Uses local HTML fixture (no Storybook required) to isolate the capture pipeline.

Requires: pip install -e ".[browser]"

  python demos/single_pixel_test.py
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pypixoo import Pixoo, FrameRenderer, WebFrameSource

load_dotenv()
IP_DEFAULT = os.environ.get("PIXOO_DEVICE_IP") or os.environ.get("PIXOO_IP") or "192.168.0.37"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "single_pixel.html"


def main():
    if not FIXTURE.exists():
        print(f"error: Fixture not found: {FIXTURE}", file=sys.stderr)
        sys.exit(1)
    url = FIXTURE.as_uri()
    source = WebFrameSource(
        url=str(url),
        timestamps=[0],
        duration_per_frame_ms=0,
        browser_mode="per_frame",
        timestamp_param="t",
    )
    renderer = FrameRenderer([source])
    seq = renderer.precompute()
    buf = list(seq.frames[0].image.data)

    pixoo = Pixoo(IP_DEFAULT)
    if not pixoo.connect():
        print("error: Failed to connect to device", file=sys.stderr)
        sys.exit(1)
    try:
        pixoo.push_buffer(buf)
        print("Pushed single pixel (0,0) to device. What do you see?")
    finally:
        pixoo.close()


if __name__ == "__main__":
    main()
