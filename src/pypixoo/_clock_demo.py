"""Shared clock demo runtime for native and web experimental modes."""

from __future__ import annotations

import argparse
import time
from datetime import datetime
from typing import Dict, Iterable, Optional
from urllib.parse import urlencode

import requests

from pypixoo.browser import FrameRenderer, WebFrameSource
from pypixoo.native import UploadMode
from pypixoo.pixoo import Pixoo

STORYBOOK_IFRAME = "http://localhost:6006/iframe.html"
CLOCK_STORY_ID = "pixoo-clock--time-with-seconds"
CLOCKFACE_MODES = [
    "dot12",
    "dots_quarters",
    "ticks_all",
    "dots_all_thick_quarters",
    "ticks_all_thick_quarters",
]

MODE_NATIVE = "native_clock"
MODE_WEB_EXPERIMENTAL = "web_clock_experimental"

WEB_ONLY_OPTION_DESTS = (
    "url",
    "fps",
    "render_lead_ms",
    "delivery",
    "window_seconds",
    "dial_color",
    "hands_color",
    "hour_hand_color",
    "minute_hand_color",
    "no_second_hand",
    "second_hand_color",
    "clockface",
    "marker_color",
    "top_marker_color",
    "fade",
    "upload_mode",
    "chunk_size",
    "refresh_seconds",
    "loop_seconds",
)

NATIVE_ONLY_OPTION_DESTS = (
    "clock_id",
    "channel_index",
    "sync_utc",
    "twenty_four_hour",
    "poll_seconds",
)


def _log(msg: str) -> None:
    print(f"{datetime.now().strftime('%H:%M:%S')} {msg}", flush=True)


def _format_story_arg(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        rendered = f"{value:.3f}".rstrip("0").rstrip(".")
        return rendered if rendered else "0"
    return str(value)


def _parser_defaults(parser: argparse.ArgumentParser) -> Dict[str, object]:
    defaults: Dict[str, object] = {}
    for action in parser._actions:
        if not action.dest or action.dest == "help":
            continue
        defaults[action.dest] = action.default
    return defaults


def _non_default_options(args: argparse.Namespace, defaults: Dict[str, object], option_dests: Iterable[str]) -> list[str]:
    changed = []
    for dest in option_dests:
        if not hasattr(args, dest):
            continue
        if defaults.get(dest) != getattr(args, dest):
            changed.append(dest)
    return changed


def enforce_mode_guardrails(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Reject cross-mode option mixing to avoid ambiguous behavior claims."""
    defaults = _parser_defaults(parser)

    if args.mode == MODE_NATIVE:
        changed_web_options = _non_default_options(args, defaults, WEB_ONLY_OPTION_DESTS)
        if changed_web_options:
            options = ", ".join(f"--{dest.replace('_', '-')}" for dest in changed_web_options)
            raise ValueError(
                f"{MODE_NATIVE} does not allow web-render options: {options}. "
                f"Use --mode {MODE_WEB_EXPERIMENTAL}."
            )
    elif args.mode == MODE_WEB_EXPERIMENTAL:
        changed_native_options = _non_default_options(args, defaults, NATIVE_ONLY_OPTION_DESTS)
        if changed_native_options:
            options = ", ".join(f"--{dest.replace('_', '-')}" for dest in changed_native_options)
            raise ValueError(
                f"{MODE_WEB_EXPERIMENTAL} does not allow native-only options: {options}. "
                f"Use --mode {MODE_NATIVE}."
            )
    else:
        raise ValueError(f"Unsupported mode: {args.mode}")


def build_clock_parser(
    *,
    description: str,
    ip_default: str,
    default_mode: str = MODE_NATIVE,
    default_fps: int = 2,
    default_loop_seconds: float = 2.0,
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--ip", default=ip_default, help=f"Device IP (default: {ip_default})")
    parser.add_argument(
        "--mode",
        choices=[MODE_NATIVE, MODE_WEB_EXPERIMENTAL],
        default=default_mode,
        help=f"Clock mode ({MODE_NATIVE}=device commands, {MODE_WEB_EXPERIMENTAL}=browser render/upload)",
    )

    # Native mode options
    parser.add_argument(
        "--clock-id",
        type=int,
        default=None,
        help=f"{MODE_NATIVE}: optional device clock face id (default keeps current face)",
    )
    parser.add_argument(
        "--channel-index",
        type=int,
        default=None,
        help=f"{MODE_NATIVE}: optional channel index to select before setting clock id",
    )
    parser.add_argument(
        "--sync-utc",
        action="store_true",
        help=f"{MODE_NATIVE}: periodically sync device UTC time from host",
    )
    parser.add_argument(
        "--twenty-four-hour",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=f"{MODE_NATIVE}: set device 24-hour display mode",
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=5.0,
        help=f"{MODE_NATIVE}: loop interval while keeping demo active",
    )

    # Web experimental options
    parser.add_argument("--url", default=None, help=f"{MODE_WEB_EXPERIMENTAL}: optional fixed Storybook iframe URL")
    parser.add_argument(
        "--fps",
        type=int,
        default=default_fps,
        help=f"{MODE_WEB_EXPERIMENTAL}: target frames per second",
    )
    parser.add_argument(
        "--loop-seconds",
        type=float,
        default=default_loop_seconds,
        help=f"{MODE_WEB_EXPERIMENTAL}: animation loop length in seconds",
    )
    parser.add_argument(
        "--render-lead-ms",
        type=int,
        default=1200,
        help=f"{MODE_WEB_EXPERIMENTAL}: render ahead of display time",
    )
    parser.add_argument(
        "--delivery",
        choices=["push", "upload"],
        default="push",
        help=f"{MODE_WEB_EXPERIMENTAL}: push=no-loading single frames, upload=native sequence windows",
    )
    parser.add_argument(
        "--window-seconds",
        type=float,
        default=3.0,
        help=f"{MODE_WEB_EXPERIMENTAL} upload mode: seconds per render window",
    )
    parser.add_argument("--dial-color", default="black", help=f"{MODE_WEB_EXPERIMENTAL}: dial color")
    parser.add_argument(
        "--hands-color",
        default=None,
        help=f"{MODE_WEB_EXPERIMENTAL}: legacy fallback for hour/minute hands",
    )
    parser.add_argument(
        "--hour-hand-color",
        default="rgba(242,232,255,0.6)",
        help=f"{MODE_WEB_EXPERIMENTAL}: hour hand color",
    )
    parser.add_argument(
        "--minute-hand-color",
        default="rgba(242,232,255,0.5)",
        help=f"{MODE_WEB_EXPERIMENTAL}: minute hand color",
    )
    parser.add_argument(
        "--no-second-hand",
        action="store_true",
        help=f"{MODE_WEB_EXPERIMENTAL}: hide second hand",
    )
    parser.add_argument(
        "--second-hand-color",
        default="rgba(255,100,100,0.9)",
        help=f"{MODE_WEB_EXPERIMENTAL}: second hand color",
    )
    parser.add_argument(
        "--clockface",
        choices=CLOCKFACE_MODES,
        default=None,
        help=f"{MODE_WEB_EXPERIMENTAL}: fixed marker style (default cycles by minute)",
    )
    parser.add_argument(
        "--marker-color",
        default="rgba(255,0,255,0.5)",
        help=f"{MODE_WEB_EXPERIMENTAL}: marker color",
    )
    parser.add_argument(
        "--top-marker-color",
        default="rgba(255,0,255,0.8)",
        help=f"{MODE_WEB_EXPERIMENTAL}: top marker override",
    )
    parser.add_argument(
        "--fade",
        type=float,
        default=100.0,
        help=f"{MODE_WEB_EXPERIMENTAL}: markers/hands intensity percent",
    )
    parser.add_argument(
        "--upload-mode",
        choices=[UploadMode.FRAME_BY_FRAME.value, UploadMode.COMMAND_LIST.value],
        default=UploadMode.COMMAND_LIST.value,
        help=f"{MODE_WEB_EXPERIMENTAL} upload mode: native upload transport",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=40,
        help=f"{MODE_WEB_EXPERIMENTAL} upload mode: CommandList chunk size",
    )
    parser.add_argument(
        "--refresh-seconds",
        type=float,
        default=0.0,
        help=f"{MODE_WEB_EXPERIMENTAL} upload mode: periodic re-upload interval; 0=upload once",
    )

    # Common resilience option
    parser.add_argument(
        "--reconnect-delay-seconds",
        type=float,
        default=3.0,
        help="Reconnect delay after connection failure",
    )
    return parser


def _build_clock_url(
    frame_time_epoch: float,
    *,
    face_color: str,
    hour_hand_color: str,
    minute_hand_color: str,
    show_second_hand: bool,
    second_hand_color: str,
    marker_mode: str,
    marker_color: str,
    top_marker_color: Optional[str],
    face_fade: float,
) -> str:
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


def _resolve_clockface_mode(frame_time_epoch: float, fixed_clockface: Optional[str]) -> str:
    if fixed_clockface:
        return fixed_clockface
    minute = datetime.fromtimestamp(frame_time_epoch).minute
    return CLOCKFACE_MODES[minute % len(CLOCKFACE_MODES)]


def _render_single_frame(args: argparse.Namespace, frame_time: float):
    show_second_hand = not args.no_second_hand
    hour_hand_color = args.hour_hand_color or args.hands_color or "white"
    minute_hand_color = args.minute_hand_color or args.hands_color or "white"
    face_fade = max(0.0, min(100.0, args.fade)) / 100.0
    marker_mode = _resolve_clockface_mode(frame_time, args.clockface)

    source = WebFrameSource(
        url=(
            args.url
            or _build_clock_url(
                frame_time,
                face_color=args.dial_color,
                hour_hand_color=hour_hand_color,
                minute_hand_color=minute_hand_color,
                show_second_hand=show_second_hand,
                second_hand_color=args.second_hand_color,
                marker_mode=marker_mode,
                marker_color=args.marker_color,
                top_marker_color=args.top_marker_color,
                face_fade=face_fade,
            )
        ),
        timestamps=[0],
        duration_per_frame_ms=0,
        browser_mode="per_frame",
        timestamp_param="t",
    )
    return FrameRenderer([source]).precompute().frames[0], marker_mode


def _run_web_push_mode(pixoo: Pixoo, args: argparse.Namespace, fps: int) -> None:
    interval = 1.0 / fps
    lead_sec = max(0.2, args.render_lead_ms / 1000.0)
    avg_render_sec = lead_sec
    last_mode = None

    print(
        f"mode={MODE_WEB_EXPERIMENTAL} capability=browser_rendered_upload delivery=push "
        f"fps={fps} lead={lead_sec:.2f}s"
    )

    next_target = time.time() + max(lead_sec, interval)
    while True:
        min_target = time.time() + max(lead_sec, avg_render_sec + 0.05)
        if next_target < min_target:
            next_target = min_target

        render_started = time.time()
        frame, marker_mode = _render_single_frame(args, next_target)
        render_dur = time.time() - render_started
        avg_render_sec = (avg_render_sec * 0.8) + (render_dur * 0.2)

        if marker_mode != last_mode:
            mode_source = "fixed --clockface" if args.clockface else "minute cycle"
            _log(f"clockface mode -> {marker_mode} ({mode_source})")
            last_mode = marker_mode

        now = time.time()
        if now < next_target:
            time.sleep(next_target - now)
        pixoo.push_buffer(list(frame.image.data))

        _log(
            f"pushed frame (render {render_dur:.2f}s, "
            f"lead {max(lead_sec, avg_render_sec + 0.05):.2f}s)"
        )
        next_target += interval


def _run_web_upload_mode(pixoo: Pixoo, args: argparse.Namespace, fps: int) -> None:
    window_seconds = max(1.0 / fps, args.window_seconds)
    frame_count = max(1, int(round(fps * window_seconds)))
    frame_duration_ms = max(20, int(round(1000 / fps)))
    render_estimate_sec = window_seconds
    min_lead_sec = max(0.2, args.render_lead_ms / 1000.0)
    last_mode = None

    print(
        f"mode={MODE_WEB_EXPERIMENTAL} capability=browser_rendered_upload delivery=upload "
        f"fps={fps} window={window_seconds:.2f}s upload_mode={args.upload_mode} chunk={args.chunk_size}"
    )

    while True:
        cycle_start = time.time() + max(min_lead_sec, render_estimate_sec)
        sources: list[WebFrameSource] = []
        cycle_modes = []
        for i in range(frame_count):
            frame_time = cycle_start + (i / fps)
            marker_mode = _resolve_clockface_mode(frame_time, args.clockface)
            cycle_modes.append(marker_mode)
            show_second_hand = not args.no_second_hand
            hour_hand_color = args.hour_hand_color or args.hands_color or "white"
            minute_hand_color = args.minute_hand_color or args.hands_color or "white"
            face_fade = max(0.0, min(100.0, args.fade)) / 100.0
            sources.append(
                WebFrameSource(
                    url=(
                        args.url
                        or _build_clock_url(
                            frame_time,
                            face_color=args.dial_color,
                            hour_hand_color=hour_hand_color,
                            minute_hand_color=minute_hand_color,
                            show_second_hand=show_second_hand,
                            second_hand_color=args.second_hand_color,
                            marker_mode=marker_mode,
                            marker_color=args.marker_color,
                            top_marker_color=args.top_marker_color,
                            face_fade=face_fade,
                        )
                    ),
                    timestamps=[0],
                    duration_per_frame_ms=frame_duration_ms,
                    browser_mode="per_frame",
                    timestamp_param="t",
                )
            )

        render_started = time.time()
        rendered_sequence = FrameRenderer(sources).precompute()
        render_dur = time.time() - render_started
        render_estimate_sec = (render_estimate_sec * 0.7) + (render_dur * 0.3)

        first_mode = cycle_modes[0]
        if first_mode != last_mode:
            mode_source = "fixed --clockface" if args.clockface else "minute cycle"
            _log(f"clockface mode -> {first_mode} ({mode_source})")
            last_mode = first_mode

        pixoo.upload_sequence(
            rendered_sequence,
            mode=UploadMode(args.upload_mode),
            chunk_size=args.chunk_size,
        )
        _log(f"uploaded {frame_count} frames (render {render_dur:.2f}s)")

        if args.refresh_seconds > 0:
            time.sleep(max(0.1, args.refresh_seconds))


def _run_native_clock_mode(pixoo: Pixoo, args: argparse.Namespace) -> None:
    if args.sync_utc:
        pixoo.set_utc_time(int(time.time()))
    if args.twenty_four_hour is not None:
        pixoo.set_time_24_flag(1 if args.twenty_four_hour else 0)
    if args.channel_index is not None:
        pixoo.set_channel_index(args.channel_index)
    if args.clock_id is not None:
        pixoo.set_clock_select_id(args.clock_id)
    info = pixoo.get_clock_info()
    selected_clock_id = args.clock_id if args.clock_id is not None else info.get("ClockId")
    print(
        f"mode={MODE_NATIVE} capability=device_native_clock "
        f"clock_id={selected_clock_id} channel_index={args.channel_index} sync_utc={args.sync_utc}"
    )
    print(f"Clock info: {info}")
    while True:
        if args.sync_utc:
            pixoo.set_utc_time(int(time.time()))
        time.sleep(max(1.0, args.poll_seconds))


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


def run_clock_demo(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    try:
        enforce_mode_guardrails(args, parser)
    except ValueError as exc:
        parser.error(str(exc))
    reconnect_delay_seconds = max(0.5, args.reconnect_delay_seconds)
    fps = max(1, args.fps)

    pixoo = Pixoo(args.ip)
    print("Press Ctrl+C to stop.")
    _log(
        f"mode selected: {args.mode}; resilient reconnect every {reconnect_delay_seconds:.1f}s"
    )

    if args.mode == MODE_WEB_EXPERIMENTAL:
        print("EXPERIMENTAL: smoothness/time fidelity not guaranteed.", flush=True)

    try:
        while True:
            _wait_for_connection(pixoo, reconnect_delay_seconds)
            try:
                if args.mode == MODE_NATIVE:
                    _run_native_clock_mode(pixoo, args)
                elif args.delivery == "push":
                    _run_web_push_mode(pixoo, args, fps)
                else:
                    _run_web_upload_mode(pixoo, args, fps)
            except requests.exceptions.RequestException as exc:
                _log(f"device connection lost ({type(exc).__name__}): {exc}")
                time.sleep(reconnect_delay_seconds)
            except RuntimeError as exc:
                _log(f"runtime error during clock loop: {exc}")
                time.sleep(reconnect_delay_seconds)
    except KeyboardInterrupt:
        print("\nStopped")
    finally:
        pixoo.close()
