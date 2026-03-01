#!/usr/bin/env python3
"""Show current time on the Pixoo using the Storybook Clock (hour + minute + second).

Updates every second. Pre-renders the frame before each tick (default 800 ms before)
so the push happens on the second boundary for better accuracy.

Requires Storybook: cd storybook-app && npm run storybook
Requires: pip install -e ".[browser]"

  python demos/clock_realtime.py
  python demos/clock_realtime.py --preload-ms 500 --dial-color black --hands-color white
  python demos/clock_realtime.py --interval 1 --preload-ms 800
  python demos/clock_realtime.py --no-second-hand
  python demos/clock_realtime.py --second-hand-color cyan

Press Ctrl+C to stop.
"""

import argparse
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

# Demos always use the real device; set env so the library acquires the device lock.
os.environ.setdefault("PIXOO_REAL_DEVICE", "1")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pypixoo import Pixoo, FrameRenderer, WebFrameSource

IP_DEFAULT = "192.168.0.37"
STORYBOOK_IFRAME = "http://localhost:6006/iframe.html"
CLOCK_STORY_ID = "pixoo-clock--time-with-seconds"


def build_clock_url(
    hour: int,
    minute: int,
    second: int,
    face_color: str,
    hand_color: str,
    show_second_hand: bool,
    second_hand_color: str,
) -> str:
    """Build Storybook iframe URL. Preview decorator reads hour/minute/second from URL."""
    query = {
        "id": CLOCK_STORY_ID,
        "viewMode": "story",
        "hour": str(hour % 12),
        "minute": str(minute),
        "second": str(second),
        "faceColor": face_color,
        "handColor": hand_color,
        "showSecondHand": "true" if show_second_hand else "false",
        "secondHandColor": second_hand_color,
    }
    return f"{STORYBOOK_IFRAME}?{urlencode(query)}"


def main():
    parser = argparse.ArgumentParser(
        description="Show current time on Pixoo (Storybook Clock). Updates every second with pre-rendering."
    )
    parser.add_argument("--ip", default=IP_DEFAULT, help=f"Device IP (default: {IP_DEFAULT})")
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Update interval in seconds (default: 1)",
    )
    parser.add_argument(
        "--preload-ms",
        type=int,
        default=800,
        help="Start rendering this many ms before the second mark (default: 800)",
    )
    parser.add_argument(
        "--dial-color",
        default="black",
        help="Clock face/dial color (default: black)",
    )
    parser.add_argument(
        "--hands-color",
        default="white",
        help="Hour and minute hands color (default: white)",
    )
    parser.add_argument(
        "--no-second-hand",
        action="store_true",
        help="Hide the second hand (default: show second hand)",
    )
    parser.add_argument(
        "--second-hand-color",
        default="rgba(255,100,100,0.9)",
        help="Second hand color (default: reddish)",
    )
    parse_args = parser.parse_args()

    pixoo = Pixoo(parse_args.ip)
    if not pixoo.connect():
        print(f"error: Failed to connect to {parse_args.ip}", file=sys.stderr)
        sys.exit(1)

    interval = parse_args.interval

    print(
        f"Clock realtime: interval={interval}s, preload={parse_args.preload_ms}ms, "
        f"dial={parse_args.dial_color}, hands={parse_args.hands_color}, "
        f"second_hand={'off' if parse_args.no_second_hand else 'on'} ({parse_args.second_hand_color})"
    )
    print("Press Ctrl+C to stop.")

    try:
        while True:
            now = datetime.now()
            next_display = (now + timedelta(seconds=interval)).replace(microsecond=0)
            render_at = next_display - timedelta(milliseconds=parse_args.preload_ms)

            now = datetime.now()
            if render_at > now:
                sleep_sec = (render_at - now).total_seconds()
                time.sleep(max(0, sleep_sec))

            url = build_clock_url(
                next_display.hour,
                next_display.minute,
                next_display.second,
                parse_args.dial_color,
                parse_args.hands_color,
                show_second_hand=not parse_args.no_second_hand,
                second_hand_color=parse_args.second_hand_color,
            )
            source = WebFrameSource(
                url=url,
                timestamps=[0],
                duration_per_frame_ms=0,
                browser_mode="per_frame",
                timestamp_param="t",
            )
            renderer = FrameRenderer([source])
            sequence = renderer.precompute()
            frame = sequence.frames[0]
            buffer_data = list(frame.image.data)

            now = datetime.now()
            if next_display > now:
                sleep_sec = (next_display - now).total_seconds()
                time.sleep(max(0, sleep_sec))

            pixoo.push_buffer(buffer_data)
            print(next_display.strftime("%H:%M:%S"), flush=True)
    except KeyboardInterrupt:
        print("\nStopped")
    finally:
        pixoo.close()


if __name__ == "__main__":
    main()
