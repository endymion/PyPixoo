#!/usr/bin/env python3
"""Show a smoother real-time Storybook Clock on Pixoo.

Default mode avoids repeated "Loading..." indicators by pre-rendering future
frames and pushing single frames (`push_buffer`) on schedule.

Optional upload mode is still available for native sequence upload windows.

Requires Storybook: cd storybook-app && npm run storybook
Requires: pip install -e ".[browser]"

  python demos/clock_realtime.py
  python demos/clock_realtime.py --fps 3 --render-lead-ms 1500
  python demos/clock_realtime.py --clockface ticks_all_thick_quarters --no-second-hand
  python demos/clock_realtime.py --no-second-hand --marker-color "#ff00ff"
  python demos/clock_realtime.py --fade 20
  python demos/clock_realtime.py --delivery upload --fps 6 --window-seconds 3

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

import requests

# Demos always use the real device; set env so the library acquires the device lock.
os.environ.setdefault("PIXOO_REAL_DEVICE", "1")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pypixoo import FrameRenderer, Pixoo, UploadMode, WebFrameSource

IP_DEFAULT = "192.168.0.37"
STORYBOOK_IFRAME = "http://localhost:6006/iframe.html"
CLOCK_STORY_ID = "pixoo-clock--time-with-seconds"
CLOCKFACE_MODES = [
    "dot12",
    "dots_quarters",
    "ticks_all",
    "dots_all_thick_quarters",
    "ticks_all_thick_quarters",
]


def _log(msg: str) -> None:
    print(f"{datetime.now().strftime('%H:%M:%S')} {msg}", flush=True)


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
    hour_hand_color: str,
    minute_hand_color: str,
    show_second_hand: bool,
    second_hand_color: str,
    marker_mode: str,
    marker_color: str,
    top_marker_color: str | None,
    face_fade: float,
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
        "hourHandColor": hour_hand_color,
        "minuteHandColor": minute_hand_color,
        "secondHandColor": second_hand_color,
        "markerMode": marker_mode,
        "markerColor": marker_color,
        "faceFade": face_fade,
    }
    if top_marker_color:
        args_map["topMarkerColor"] = top_marker_color
    args_str = ";".join(f"{key}:{_format_story_arg(value)}" for key, value in args_map.items())
    return f"{STORYBOOK_IFRAME}?{urlencode({'id': CLOCK_STORY_ID, 'viewMode': 'story', 'args': args_str})}"


def resolve_clockface_mode(frame_time_epoch: float, fixed_clockface: str | None) -> str:
    if fixed_clockface:
        return fixed_clockface
    minute = datetime.fromtimestamp(frame_time_epoch).minute
    return CLOCKFACE_MODES[minute % len(CLOCKFACE_MODES)]


def _render_single_frame(
    display_time: float,
    dial_color: str,
    hour_hand_color: str,
    minute_hand_color: str,
    show_second_hand: bool,
    second_hand_color: str,
    marker_mode: str,
    marker_color: str,
    top_marker_color: str | None,
    face_fade: float,
):
    source = WebFrameSource(
        url=build_clock_url(
            display_time,
            dial_color,
            hour_hand_color,
            minute_hand_color,
            show_second_hand,
            second_hand_color,
            marker_mode,
            marker_color,
            top_marker_color,
            face_fade,
        ),
        timestamps=[0],
        duration_per_frame_ms=0,
        browser_mode="per_frame",
        timestamp_param="t",
    )
    return FrameRenderer([source]).precompute().frames[0]


def _run_push_mode(pixoo: Pixoo, args, fps: int) -> None:
    """Default no-loading mode: push pre-rendered single frames on schedule."""
    interval = 1.0 / fps
    lead_sec = max(0.2, args.render_lead_ms / 1000.0)
    avg_render_sec = lead_sec
    show_second_hand = not args.no_second_hand
    hour_hand_color = args.hour_hand_color or args.hands_color or "white"
    minute_hand_color = args.minute_hand_color or args.hands_color or "white"
    face_fade = max(0.0, min(100.0, args.fade)) / 100.0
    last_mode = None

    next_target = time.time() + max(lead_sec, interval)
    print(
        f"Clock push mode: fps={fps}, interval={interval:.3f}s, lead={lead_sec:.2f}s "
        f"(no repeated animation upload)",
        flush=True,
    )

    while True:
        # Ensure render target stays ahead of current time by our lead estimate.
        min_target = time.time() + max(lead_sec, avg_render_sec + 0.05)
        if next_target < min_target:
            next_target = min_target

        render_started = time.time()
        marker_mode = resolve_clockface_mode(next_target, args.clockface)
        if marker_mode != last_mode:
            mode_source = "fixed --clockface" if args.clockface else "minute cycle"
            _log(f"clockface mode -> {marker_mode} ({mode_source})")
            last_mode = marker_mode
        frame = _render_single_frame(
            display_time=next_target,
            dial_color=args.dial_color,
            hour_hand_color=hour_hand_color,
            minute_hand_color=minute_hand_color,
            show_second_hand=show_second_hand,
            second_hand_color=args.second_hand_color,
            marker_mode=marker_mode,
            marker_color=args.marker_color,
            top_marker_color=args.top_marker_color,
            face_fade=face_fade,
        )
        render_dur = time.time() - render_started
        avg_render_sec = (avg_render_sec * 0.8) + (render_dur * 0.2)

        now = time.time()
        if now < next_target:
            time.sleep(next_target - now)

        pixoo.push_buffer(list(frame.image.data))
        _log(
            f"pushed frame (render {render_dur:.2f}s, "
            f"lead {max(lead_sec, avg_render_sec + 0.05):.2f}s)"
        )

        next_target += interval


def _run_upload_mode(pixoo: Pixoo, args, fps: int) -> None:
    """Optional native-sequence mode (may show loading indicators while uploading)."""
    window_seconds = max(1.0 / fps, args.window_seconds)
    frame_count = max(1, int(round(fps * window_seconds)))
    frame_duration_ms = max(20, int(round(1000 / fps)))
    render_estimate_sec = window_seconds
    min_lead_sec = max(0.2, args.render_lead_ms / 1000.0)
    hour_hand_color = args.hour_hand_color or args.hands_color or "white"
    minute_hand_color = args.minute_hand_color or args.hands_color or "white"
    face_fade = max(0.0, min(100.0, args.fade)) / 100.0
    last_mode = None

    print(
        f"Clock upload mode: fps={fps}, window={window_seconds:.2f}s ({frame_count} frames), "
        f"lead={min_lead_sec:.2f}s, upload_mode={args.upload_mode}, chunk={args.chunk_size}",
        flush=True,
    )

    while True:
        cycle_start = time.time() + max(min_lead_sec, render_estimate_sec)
        sources = []
        cycle_modes = []
        for i in range(frame_count):
            frame_time = cycle_start + (i / fps)
            marker_mode = resolve_clockface_mode(frame_time, args.clockface)
            cycle_modes.append(marker_mode)
            sources.append(
                WebFrameSource(
                    url=build_clock_url(
                        frame_time,
                        args.dial_color,
                        hour_hand_color,
                        minute_hand_color,
                        not args.no_second_hand,
                        args.second_hand_color,
                        marker_mode,
                        args.marker_color,
                        args.top_marker_color,
                        face_fade,
                    ),
                    timestamps=[0],
                    duration_per_frame_ms=frame_duration_ms,
                    browser_mode="per_frame",
                    timestamp_param="t",
                )
            )

        render_started = time.time()
        sequence = FrameRenderer(sources).precompute()
        render_dur = time.time() - render_started
        render_estimate_sec = (render_estimate_sec * 0.7) + (render_dur * 0.3)

        first_mode = cycle_modes[0]
        if first_mode != last_mode:
            mode_source = "fixed --clockface" if args.clockface else "minute cycle"
            _log(f"clockface mode -> {first_mode} ({mode_source})")
            last_mode = first_mode

        pixoo.upload_sequence(
            sequence,
            mode=UploadMode(args.upload_mode),
            chunk_size=args.chunk_size,
        )
        _log(f"uploaded {frame_count} frames (render {render_dur:.2f}s)")


def _wait_for_connection(pixoo: Pixoo, reconnect_delay_seconds: float) -> None:
    while True:
        try:
            if pixoo.connect():
                _log("connected to device")
                return
            _log("connect check failed; retrying")
        except requests.exceptions.RequestException as exc:
            _log(f"connect error ({type(exc).__name__}): {exc}")
        except RuntimeError as exc:
            _log(f"connect runtime error: {exc}")
        time.sleep(reconnect_delay_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Show smooth real-time Storybook clock with push or upload delivery"
    )
    parser.add_argument("--ip", default=IP_DEFAULT, help=f"Device IP (default: {IP_DEFAULT})")
    parser.add_argument("--fps", type=int, default=2, help="Target frames per second (default: 2)")
    parser.add_argument(
        "--render-lead-ms",
        type=int,
        default=1200,
        help="Render this far ahead of display time in push mode (default: 1200)",
    )
    parser.add_argument(
        "--delivery",
        choices=["push", "upload"],
        default="push",
        help="Frame delivery mode: push=no-loading single frames, upload=native sequence windows",
    )
    parser.add_argument(
        "--window-seconds",
        type=float,
        default=3.0,
        help="Upload mode only: seconds of animation to pre-render per upload",
    )
    parser.add_argument(
        "--dial-color",
        default="black",
        help="Clock face/dial color (default: black)",
    )
    parser.add_argument(
        "--hands-color",
        default=None,
        help="Legacy fallback for both hour/minute hand colors when dedicated colors are not set",
    )
    parser.add_argument(
        "--hour-hand-color",
        default="rgba(242,232,255,0.6)",
        help="Hour hand color (default: rgba(242,232,255,0.6))",
    )
    parser.add_argument(
        "--minute-hand-color",
        default="rgba(242,232,255,0.5)",
        help="Minute hand color (default: rgba(242,232,255,0.5))",
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
        "--clockface",
        choices=CLOCKFACE_MODES,
        default=None,
        help=(
            "Fixed clockface marker mode. If omitted, demo mode cycles marker styles "
            "every minute in this order: " + ", ".join(CLOCKFACE_MODES)
        ),
    )
    parser.add_argument(
        "--marker-color",
        default="rgba(255,0,255,0.5)",
        help="Clockface marker color (default: rgba(255,0,255,0.5))",
    )
    parser.add_argument(
        "--top-marker-color",
        default="rgba(255,0,255,0.3)",
        help="Top-center marker color override (default: rgba(255,0,255,0.3))",
    )
    parser.add_argument(
        "--fade",
        type=float,
        default=100.0,
        help="Markers+hands intensity percent (0-100, default: 100)",
    )
    parser.add_argument(
        "--reconnect-delay-seconds",
        type=float,
        default=3.0,
        help="Reconnect delay after connection failure (default: 3.0)",
    )
    parser.add_argument(
        "--upload-mode",
        choices=[UploadMode.FRAME_BY_FRAME.value, UploadMode.COMMAND_LIST.value],
        default=UploadMode.COMMAND_LIST.value,
        help="Upload mode only: native transport mode",
    )
    parser.add_argument("--chunk-size", type=int, default=40, help="Upload mode only: CommandList chunk size")
    args = parser.parse_args()

    fps = max(1, args.fps)
    reconnect_delay_seconds = max(0.5, args.reconnect_delay_seconds)
    pixoo = Pixoo(args.ip)
    print("Press Ctrl+C to stop.")
    _log(
        f"resilient mode enabled (auto-reconnect every {reconnect_delay_seconds:.1f}s on disconnect)"
    )

    try:
        while True:
            _wait_for_connection(pixoo, reconnect_delay_seconds)
            try:
                if args.delivery == "push":
                    _run_push_mode(pixoo, args, fps)
                else:
                    _run_upload_mode(pixoo, args, fps)
            except requests.exceptions.RequestException as exc:
                _log(f"device connection lost ({type(exc).__name__}): {exc}")
                time.sleep(reconnect_delay_seconds)
            except RuntimeError as exc:
                _log(f"device command failure: {exc}")
                time.sleep(reconnect_delay_seconds)
    except KeyboardInterrupt:
        print("\nStopped")
    finally:
        pixoo.close()


if __name__ == "__main__":
    main()
