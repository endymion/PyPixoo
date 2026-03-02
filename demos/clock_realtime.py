#!/usr/bin/env python3
"""Show a smoother real-time Storybook Clock on Pixoo using V2 native uploads.

Instead of rendering and pushing one frame just-in-time every second,
this demo pre-renders a short multi-frame time window and uploads it as a
native HttpGif sequence for smoother motion.

Requires Storybook: cd storybook-app && npm run storybook
Requires: pip install -e ".[browser]"

  python demos/clock_realtime.py
  python demos/clock_realtime.py --fps 10 --window-seconds 3 --preload-ms 900
  python demos/clock_realtime.py --dial-color "#111" --hands-color cyan

Press Ctrl+C to stop.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

# Demos always use the real device; set env so the library acquires the device lock.
os.environ.setdefault("PIXOO_REAL_DEVICE", "1")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pypixoo import FrameRenderer, Pixoo, UploadMode, WebFrameSource

IP_DEFAULT = "192.168.0.37"
STORYBOOK_IFRAME = "http://localhost:6006/iframe.html"
CLOCK_STORY_ID = "pixoo-clock--time-with-seconds"


def _format_story_arg(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        rendered = f"{value:.3f}".rstrip("0").rstrip(".")
        return rendered if rendered else "0"
    return str(value)


def build_clock_url(
    frame_time_epoch: float,
    face_color: str,
    hand_color: str,
    show_second_hand: bool,
    second_hand_color: str,
) -> str:
    """Build Storybook iframe URL using args=... semantics for deterministic frame rendering."""
    dt = datetime.fromtimestamp(frame_time_epoch)
    second_value = dt.second + (dt.microsecond / 1_000_000.0)
    args_map = {
        "hour": dt.hour % 12,
        "minute": dt.minute,
        "second": second_value,
        "showSecondHand": show_second_hand,
        "faceColor": face_color,
        "handColor": hand_color,
        "secondHandColor": second_hand_color,
    }
    args_str = ";".join(f"{key}:{_format_story_arg(value)}" for key, value in args_map.items())
    return f"{STORYBOOK_IFRAME}?{urlencode({'id': CLOCK_STORY_ID, 'viewMode': 'story', 'args': args_str})}"


def build_sources(
    start_epoch: float,
    frame_count: int,
    fps: int,
    duration_ms: int,
    dial_color: str,
    hands_color: str,
    show_second_hand: bool,
    second_hand_color: str,
) -> list[WebFrameSource]:
    sources: list[WebFrameSource] = []
    for i in range(frame_count):
        frame_time = start_epoch + (i / fps)
        sources.append(
            WebFrameSource(
                url=build_clock_url(
                    frame_time,
                    dial_color,
                    hands_color,
                    show_second_hand,
                    second_hand_color,
                ),
                timestamps=[0],
                duration_per_frame_ms=duration_ms,
                browser_mode="per_frame",
                timestamp_param="t",
            )
        )
    return sources


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Show smooth real-time Storybook clock using V2 native sequence uploads"
    )
    parser.add_argument("--ip", default=IP_DEFAULT, help=f"Device IP (default: {IP_DEFAULT})")
    parser.add_argument("--fps", type=int, default=10, help="Target frames per second (default: 10)")
    parser.add_argument(
        "--window-seconds",
        type=float,
        default=3.0,
        help="Seconds of animation to pre-render and upload per cycle (default: 3)",
    )
    parser.add_argument(
        "--preload-ms",
        type=int,
        default=900,
        help="Begin rendering this many ms before cycle boundary (default: 900)",
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
    parser.add_argument(
        "--upload-mode",
        choices=[UploadMode.FRAME_BY_FRAME.value, UploadMode.COMMAND_LIST.value],
        default=UploadMode.COMMAND_LIST.value,
        help="Native upload transport mode",
    )
    parser.add_argument("--chunk-size", type=int, default=40, help="CommandList chunk size")
    args = parser.parse_args()

    fps = max(1, args.fps)
    window_seconds = max(1.0 / fps, args.window_seconds)
    frame_count = max(1, int(round(fps * window_seconds)))
    frame_duration_ms = max(20, int(round(1000 / fps)))

    pixoo = Pixoo(args.ip)
    if not pixoo.connect():
        print(f"error: Failed to connect to {args.ip}", file=sys.stderr)
        sys.exit(1)

    print(
        f"Clock smooth mode: fps={fps}, window={window_seconds:.2f}s ({frame_count} frames), "
        f"lead={args.preload_ms}ms, upload_mode={args.upload_mode}, chunk={args.chunk_size}"
    )
    print("Press Ctrl+C to stop.")

    render_estimate_sec = window_seconds
    min_lead_sec = max(0.1, args.preload_ms / 1000.0)

    try:
        while True:
            cycle_start = time.time() + max(min_lead_sec, render_estimate_sec)

            render_started = time.time()
            sources = build_sources(
                start_epoch=cycle_start,
                frame_count=frame_count,
                fps=fps,
                duration_ms=frame_duration_ms,
                dial_color=args.dial_color,
                hands_color=args.hands_color,
                show_second_hand=not args.no_second_hand,
                second_hand_color=args.second_hand_color,
            )
            sequence = FrameRenderer(sources).precompute()
            render_duration_sec = time.time() - render_started

            pixoo.upload_sequence(
                sequence,
                mode=UploadMode(args.upload_mode),
                chunk_size=args.chunk_size,
            )
            render_estimate_sec = (render_estimate_sec * 0.7) + (render_duration_sec * 0.3)
            print(
                f"{datetime.now().strftime('%H:%M:%S')} uploaded {frame_count} frames "
                f"(render {render_duration_sec:.2f}s, lead target {max(min_lead_sec, render_estimate_sec):.2f}s)",
                flush=True,
            )
    except KeyboardInterrupt:
        print("\nStopped")
    finally:
        pixoo.close()


if __name__ == "__main__":
    main()
