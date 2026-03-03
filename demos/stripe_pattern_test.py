#!/usr/bin/env python3
"""Push the stripe-pattern fixture to the device.

Pattern: vertical strips with every-other pixel on; one blank column between strips.
(Columns 0, 2, 4, ... have pixels at rows 0, 2, 4, ...; columns 1, 3, 5, ... blank.)

Requires: pip install -e ".[browser]"

  python demos/stripe_pattern_test.py
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pypixoo import Pixoo, FrameRenderer, WebFrameSource

load_dotenv()
IP_DEFAULT = os.environ.get("PIXOO_DEVICE_IP") or os.environ.get("PIXOO_IP") or "192.168.0.37"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "stripe_pattern.html"


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
        print("Pushed stripe pattern to device.")
    finally:
        pixoo.close()


if __name__ == "__main__":
    main()
