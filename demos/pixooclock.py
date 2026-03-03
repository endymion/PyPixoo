#!/usr/bin/env python3
"""Smooth analog clock demo for Pixoo.

`pixooclock` renders a three-hand analog clock in Python and pushes frames
continuously to the device. It also supports a stitched upload mode for
transport diagnostics.

Key options:
- Named clock faces (`--face`) including prior designed marker styles
- Second hand toggle (`--second-hand` / `--no-second-hand`)
- Optional anti-aliasing (`--anti-aliasing`)
- Full color controls for dial, markers, hands, and center
"""

from __future__ import annotations

import argparse
import math
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

import requests
from dotenv import load_dotenv

from pypixoo import GifFrame, GifSequence, Pixoo, UploadMode
from pypixoo.buffer import Buffer
from pypixoo.color import list_radix_tokens, parse_color

load_dotenv()
SIZE = 64
CENTER = SIZE // 2
DEFAULT_IP = os.environ.get("PIXOO_DEVICE_IP") or os.environ.get("PIXOO_IP") or "192.168.0.37"


FACE_NAMES = (
    "default",
    "dot12",
    "dots_quarters",
    "ticks_all",
    "dots_all_thick_quarters",
    "ticks_all_thick_quarters",
)

DEFAULT_DIAL_COLOR = (0, 0, 0)
DEFAULT_MARKER_COLOR = parse_color("dark.purple7")
DEFAULT_TOP_MARKER_COLOR = parse_color("dark.purple10")
DEFAULT_HOUR_HAND_COLOR = parse_color("dark.purple9")
DEFAULT_MINUTE_HAND_COLOR = parse_color("dark.purple7")
DEFAULT_SECOND_HAND_COLOR = parse_color("dark.purple5")
DEFAULT_CENTER_COLOR = parse_color("dark.purple5")


@dataclass(frozen=True)
class ClockStyle:
    dial_color: tuple[int, int, int]
    marker_color: tuple[int, int, int]
    top_marker_color: tuple[int, int, int]
    hour_hand_color: tuple[int, int, int]
    minute_hand_color: tuple[int, int, int]
    second_hand_color: tuple[int, int, int]
    center_color: tuple[int, int, int]
    hour_length: int
    minute_length: int
    second_length: int
    marker_inner_radius: int
    marker_outer_radius: int
    marker_thickness: int
    top_marker_thickness: int
    quarter_marker_thickness: int
    hour_thickness: int
    minute_thickness: int
    second_thickness: int
    center_radius: int
    face: str
    band: str
    second_hand: bool
    anti_aliasing: bool
    dot_anti_aliasing: bool


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be > 0")
    return parsed


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be > 0")
    return parsed


def _parse_color_arg(value: str) -> tuple[int, int, int]:
    try:
        return parse_color(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _dark_band_names() -> tuple[str, ...]:
    bands: set[str] = set()
    for token in list_radix_tokens(dark=True):
        match = re.match(r"^dark\.([a-z]+)([0-9]{1,2})$", token)
        if not match:
            continue
        band = match.group(1)
        if band.endswith("a"):
            continue
        bands.add(band)
    return tuple(sorted(bands))


ALL_DARK_BANDS = _dark_band_names()


def _parse_band_arg(value: str) -> str:
    band = value.strip().lower().replace("-", "").replace("_", "")
    if not band:
        raise argparse.ArgumentTypeError("band name cannot be empty")
    if band not in ALL_DARK_BANDS:
        raise argparse.ArgumentTypeError(
            f"unknown Radix dark band '{value}' (valid: {', '.join(ALL_DARK_BANDS)})"
        )
    return band


def _parse_band_list_arg(value: str) -> tuple[str, ...]:
    entries = [part.strip() for part in value.split(",")]
    bands = tuple(_parse_band_arg(part) for part in entries if part)
    if not bands:
        raise argparse.ArgumentTypeError("demo bands list cannot be empty")
    return bands


def build_parser(ip_default: str = DEFAULT_IP) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "pixooclock: smooth analog clock via native uploads. "
            "Color args support hex/rgb/names plus Radix tokens "
            "(gray11, dark.gray11, grayDark11)."
        )
    )
    parser.add_argument("--ip", default=ip_default, help=f"Device IP (default: {ip_default})")
    parser.add_argument(
        "--delivery",
        choices=["push", "stitched"],
        default="push",
        help="push=no-loading continuous frame push; stitched=segment uploads (may show loading overlay)",
    )
    parser.add_argument("--fps", type=_positive_int, default=3, help="Target frames per second")
    parser.add_argument(
        "--segment-seconds",
        type=_positive_float,
        default=12.0,
        help="Duration of each stitched segment",
    )
    parser.add_argument(
        "--max-frames",
        type=_positive_int,
        default=88,
        help="Hard frame cap per uploaded segment",
    )
    parser.add_argument(
        "--upload-mode",
        choices=[UploadMode.FRAME_BY_FRAME.value, UploadMode.COMMAND_LIST.value],
        default=UploadMode.FRAME_BY_FRAME.value,
    )
    parser.add_argument("--chunk-size", type=_positive_int, default=8)
    parser.add_argument(
        "--sync-utc",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Sync device UTC from host at startup and periodically",
    )
    parser.add_argument(
        "--utc-resync-segments",
        type=_positive_int,
        default=5,
        help="When sync_utc is enabled, resync every N segments",
    )
    parser.add_argument("--once", action="store_true", help="Upload a single segment and exit")
    parser.add_argument(
        "--demo",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Cycle through face and rendering combinations for visual comparison",
    )
    parser.add_argument(
        "--demo-interval-seconds",
        type=_positive_float,
        default=5.0,
        help="How long each demo variation stays on screen",
    )
    parser.add_argument(
        "--demo-bands",
        type=_parse_band_list_arg,
        default=ALL_DARK_BANDS,
        help="Comma-separated Radix dark color bands for demo cycling (default: all non-alpha bands)",
    )

    # Face + visual controls.
    parser.add_argument(
        "--face",
        choices=FACE_NAMES,
        default="dot12",
        help="Clock face marker design",
    )
    parser.add_argument(
        "--band",
        type=_parse_band_arg,
        default="sand",
        help="Apply Radix dark color band to marker/hands/center (example: purple, tomato)",
    )
    parser.add_argument(
        "--second-hand",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Enable the second hand",
    )
    parser.add_argument(
        "--anti-aliasing",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable anti-aliased hand rendering (slower)",
    )
    parser.add_argument(
        "--dot-anti-aliasing",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable anti-aliased rendering for marker/center dots",
    )

    # Colors
    parser.add_argument("--dial-color", type=_parse_color_arg, default=DEFAULT_DIAL_COLOR)
    parser.add_argument("--marker-color", type=_parse_color_arg, default=DEFAULT_MARKER_COLOR)
    parser.add_argument("--top-marker-color", type=_parse_color_arg, default=DEFAULT_TOP_MARKER_COLOR)
    parser.add_argument("--hour-hand-color", type=_parse_color_arg, default=DEFAULT_HOUR_HAND_COLOR)
    parser.add_argument("--minute-hand-color", type=_parse_color_arg, default=DEFAULT_MINUTE_HAND_COLOR)
    parser.add_argument("--second-hand-color", type=_parse_color_arg, default=DEFAULT_SECOND_HAND_COLOR)
    parser.add_argument("--center-color", type=_parse_color_arg, default=DEFAULT_CENTER_COLOR)

    # Geometry
    parser.add_argument("--hour-length", type=_positive_int, default=16)
    parser.add_argument("--minute-length", type=_positive_int, default=23)
    parser.add_argument("--second-length", type=_positive_int, default=28)
    parser.add_argument("--marker-thickness", type=_positive_int, default=1)
    parser.add_argument("--top-marker-thickness", type=_positive_int, default=2)
    parser.add_argument("--quarter-marker-thickness", type=_positive_int, default=2)
    parser.add_argument("--hour-thickness", type=_positive_int, default=2)
    parser.add_argument("--minute-thickness", type=_positive_int, default=2)
    parser.add_argument("--second-thickness", type=_positive_int, default=1)
    parser.add_argument("--center-radius", type=_positive_int, default=1)
    return parser


def _apply_band_defaults(args: argparse.Namespace) -> None:
    if not args.band:
        return

    # Band colors only replace values still on defaults so explicit color args
    # always win.
    band_levels = (
        ("marker_color", DEFAULT_MARKER_COLOR, 7),
        ("top_marker_color", DEFAULT_TOP_MARKER_COLOR, 10),
        ("hour_hand_color", DEFAULT_HOUR_HAND_COLOR, 9),
        ("minute_hand_color", DEFAULT_MINUTE_HAND_COLOR, 7),
        ("second_hand_color", DEFAULT_SECOND_HAND_COLOR, 5),
        ("center_color", DEFAULT_CENTER_COLOR, 5),
    )
    for attr, default_value, level in band_levels:
        if getattr(args, attr) != default_value:
            continue
        setattr(args, attr, parse_color(f"dark.{args.band}{level}"))


def _style_from_args(args: argparse.Namespace) -> ClockStyle:
    _apply_band_defaults(args)
    return ClockStyle(
        dial_color=args.dial_color,
        marker_color=args.marker_color,
        top_marker_color=args.top_marker_color,
        hour_hand_color=args.hour_hand_color,
        minute_hand_color=args.minute_hand_color,
        second_hand_color=args.second_hand_color,
        center_color=args.center_color,
        hour_length=min(args.hour_length, 30),
        minute_length=min(args.minute_length, 30),
        second_length=min(args.second_length, 30),
        marker_inner_radius=26,
        marker_outer_radius=30,
        marker_thickness=args.marker_thickness,
        top_marker_thickness=args.top_marker_thickness,
        quarter_marker_thickness=args.quarter_marker_thickness,
        hour_thickness=args.hour_thickness,
        minute_thickness=args.minute_thickness,
        second_thickness=args.second_thickness,
        center_radius=max(0, min(args.center_radius, 8)),
        face=args.face,
        band=args.band or "custom",
        second_hand=args.second_hand,
        anti_aliasing=args.anti_aliasing,
        dot_anti_aliasing=args.dot_anti_aliasing,
    )


def angles_for_hms(hour: int, minute: int, second: float) -> tuple[float, float, float]:
    minute_total = minute + (second / 60.0)
    hour_total = (hour % 12) + (minute_total / 60.0)
    hour_angle = ((hour_total / 12.0) * 2.0 * math.pi) - (math.pi / 2.0)
    minute_angle = ((minute_total / 60.0) * 2.0 * math.pi) - (math.pi / 2.0)
    second_angle = ((second / 60.0) * 2.0 * math.pi) - (math.pi / 2.0)
    return hour_angle, minute_angle, second_angle


def angles_for_epoch(ts: float) -> tuple[float, float, float]:
    dt = datetime.fromtimestamp(ts)
    second = dt.second + (dt.microsecond / 1_000_000.0)
    return angles_for_hms(dt.hour, dt.minute, second)


def aligned_segment_start(now_epoch: float, segment_seconds: float) -> float:
    return math.ceil(now_epoch / segment_seconds) * segment_seconds


def _new_canvas(color: tuple[int, int, int]) -> list[int]:
    return [component for _ in range(SIZE * SIZE) for component in color]


def _set_px(data: list[int], x: int, y: int, color: tuple[int, int, int]) -> None:
    if x < 0 or y < 0 or x >= SIZE or y >= SIZE:
        return
    idx = (y * SIZE + x) * 3
    data[idx : idx + 3] = [color[0], color[1], color[2]]


def _blend_px(data: list[int], x: int, y: int, color: tuple[int, int, int], alpha: float) -> None:
    if x < 0 or y < 0 or x >= SIZE or y >= SIZE:
        return
    if alpha <= 0:
        return
    alpha = min(1.0, alpha)
    inv = 1.0 - alpha
    idx = (y * SIZE + x) * 3
    data[idx] = int(round((data[idx] * inv) + (color[0] * alpha)))
    data[idx + 1] = int(round((data[idx + 1] * inv) + (color[1] * alpha)))
    data[idx + 2] = int(round((data[idx + 2] * inv) + (color[2] * alpha)))


def _draw_subpixel_dot(
    data: list[int],
    x: float,
    y: float,
    color: tuple[int, int, int],
    strength: float = 1.0,
) -> None:
    x0 = math.floor(x)
    y0 = math.floor(y)
    tx = x - x0
    ty = y - y0
    weights = (
        (x0, y0, (1.0 - tx) * (1.0 - ty)),
        (x0 + 1, y0, tx * (1.0 - ty)),
        (x0, y0 + 1, (1.0 - tx) * ty),
        (x0 + 1, y0 + 1, tx * ty),
    )
    for px, py, w in weights:
        _blend_px(data, px, py, color, w * strength)


def _draw_disk(data: list[int], cx: int, cy: int, radius: int, color: tuple[int, int, int]) -> None:
    radius = max(0, radius)
    rr = radius * radius
    for y in range(cy - radius, cy + radius + 1):
        for x in range(cx - radius, cx + radius + 1):
            dx = x - cx
            dy = y - cy
            if (dx * dx) + (dy * dy) <= rr:
                _set_px(data, x, y, color)


def _draw_disk_aa(
    data: list[int],
    cx: float,
    cy: float,
    radius: int,
    color: tuple[int, int, int],
) -> None:
    radius = max(0, radius)
    outer = radius + 1
    y_min = int(math.floor(cy - outer))
    y_max = int(math.ceil(cy + outer))
    x_min = int(math.floor(cx - outer))
    x_max = int(math.ceil(cx + outer))

    for y in range(y_min, y_max + 1):
        for x in range(x_min, x_max + 1):
            dist = math.hypot(x - cx, y - cy)
            alpha = (radius + 0.5) - dist
            if alpha >= 1.0:
                _set_px(data, x, y, color)
            elif alpha > 0.0:
                _blend_px(data, x, y, color, alpha)


def _draw_dot(
    data: list[int],
    cx: float,
    cy: float,
    radius: int,
    color: tuple[int, int, int],
    anti_aliasing: bool,
) -> None:
    if anti_aliasing:
        _draw_disk_aa(data, cx, cy, radius, color)
    else:
        _draw_disk(data, int(round(cx)), int(round(cy)), radius, color)


def _draw_line_basic(
    data: list[int],
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    color: tuple[int, int, int],
    thickness: int = 1,
) -> None:
    x0 = int(round(x0))
    y0 = int(round(y0))
    x1 = int(round(x1))
    y1 = int(round(y1))
    thickness = max(1, thickness)
    radius = (thickness - 1) // 2

    dx = abs(x1 - x0)
    sx = 1 if x0 < x1 else -1
    dy = -abs(y1 - y0)
    sy = 1 if y0 < y1 else -1
    err = dx + dy

    x, y = x0, y0
    while True:
        if radius == 0:
            _set_px(data, x, y, color)
        else:
            _draw_disk(data, x, y, radius, color)
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy


def _draw_line_aa(
    data: list[int],
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    color: tuple[int, int, int],
    thickness: int = 1,
) -> None:
    thickness = max(1, thickness)
    dx = x1 - x0
    dy = y1 - y0
    length = math.hypot(dx, dy)
    if length == 0:
        _draw_subpixel_dot(data, float(x0), float(y0), color, strength=1.0)
        return

    steps = max(1, int(math.ceil(length * 2.0)))
    nx = -dy / length
    ny = dx / length
    radius = (thickness - 1) / 2.0

    for i in range(steps + 1):
        t = i / steps
        px = x0 + (dx * t)
        py = y0 + (dy * t)

        if radius <= 0:
            _draw_subpixel_dot(data, px, py, color, strength=1.0)
            continue

        samples = max(3, int(math.ceil(thickness * 2)))
        for j in range(samples):
            if samples == 1:
                offset = 0.0
            else:
                offset = -radius + ((2.0 * radius) * (j / (samples - 1)))
            falloff = 1.0 - (abs(offset) / (radius + 0.0001))
            if falloff <= 0:
                continue
            _draw_subpixel_dot(data, px + (nx * offset), py + (ny * offset), color, strength=falloff)


def _draw_line(
    data: list[int],
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    color: tuple[int, int, int],
    thickness: int,
    anti_aliasing: bool,
) -> None:
    if anti_aliasing:
        _draw_line_aa(data, x0, y0, x1, y1, color, thickness)
    else:
        _draw_line_basic(data, x0, y0, x1, y1, color, thickness)


def _point_on_angle(angle: float, radius: int) -> tuple[int, int]:
    x = int(round(CENTER + (math.cos(angle) * radius)))
    y = int(round(CENTER + (math.sin(angle) * radius)))
    return x, y


def _quarter_index(marker_i: int) -> int:
    return marker_i % 3


def _draw_marker_face(data: list[int], style: ClockStyle) -> None:
    for i in range(12):
        marker_angle = ((i / 12.0) * 2.0 * math.pi) - (math.pi / 2.0)
        x0, y0 = _point_on_angle(marker_angle, style.marker_inner_radius)
        x1, y1 = _point_on_angle(marker_angle, style.marker_outer_radius)

        is_top = i == 0
        is_quarter = _quarter_index(i) == 0

        if style.face == "dot12":
            if not is_top:
                continue
            _draw_dot(
                data,
                x1,
                y1,
                max(1, style.top_marker_thickness),
                style.top_marker_color,
                style.dot_anti_aliasing,
            )
            continue

        if style.face == "dots_quarters":
            if not is_quarter:
                continue
            color = style.top_marker_color if is_top else style.marker_color
            radius = max(1, style.top_marker_thickness if is_top else style.marker_thickness)
            _draw_dot(data, x1, y1, radius, color, style.dot_anti_aliasing)
            continue

        if style.face == "ticks_all":
            color = style.top_marker_color if is_top else style.marker_color
            thickness = style.top_marker_thickness if is_top else style.marker_thickness
            _draw_line(data, x0, y0, x1, y1, color, thickness, anti_aliasing=False)
            continue

        if style.face == "dots_all_thick_quarters":
            color = style.top_marker_color if is_top else style.marker_color
            if is_top:
                radius = max(1, style.top_marker_thickness)
            elif is_quarter:
                radius = max(1, style.quarter_marker_thickness)
            else:
                radius = max(1, style.marker_thickness)
            _draw_dot(data, x1, y1, radius, color, style.dot_anti_aliasing)
            continue

        if style.face == "ticks_all_thick_quarters":
            color = style.top_marker_color if is_top else style.marker_color
            if is_top:
                thickness = style.top_marker_thickness
            elif is_quarter:
                thickness = style.quarter_marker_thickness
            else:
                thickness = style.marker_thickness
            _draw_line(data, x0, y0, x1, y1, color, thickness, anti_aliasing=False)
            continue

        # default: the current known-good gorgeous face.
        color = style.top_marker_color if is_top else style.marker_color
        thickness = style.top_marker_thickness if is_top else style.marker_thickness
        _draw_line(data, x0, y0, x1, y1, color, thickness, anti_aliasing=False)


def render_clock_frame(ts: float, style: ClockStyle) -> Buffer:
    data = _new_canvas(style.dial_color)

    _draw_marker_face(data, style)

    hour_a, minute_a, second_a = angles_for_epoch(ts)

    hour_tip_x = CENTER + (math.cos(hour_a) * style.hour_length)
    hour_tip_y = CENTER + (math.sin(hour_a) * style.hour_length)
    minute_tip_x = CENTER + (math.cos(minute_a) * style.minute_length)
    minute_tip_y = CENTER + (math.sin(minute_a) * style.minute_length)

    if style.anti_aliasing:
        hx, hy = hour_tip_x, hour_tip_y
        mx, my = minute_tip_x, minute_tip_y
    else:
        hx, hy = _point_on_angle(hour_a, style.hour_length)
        mx, my = _point_on_angle(minute_a, style.minute_length)

    _draw_line(
        data,
        CENTER,
        CENTER,
        hx,
        hy,
        style.hour_hand_color,
        style.hour_thickness,
        anti_aliasing=style.anti_aliasing,
    )
    _draw_line(
        data,
        CENTER,
        CENTER,
        mx,
        my,
        style.minute_hand_color,
        style.minute_thickness,
        anti_aliasing=style.anti_aliasing,
    )

    if style.second_hand:
        second_tip_x = CENTER + (math.cos(second_a) * style.second_length)
        second_tip_y = CENTER + (math.sin(second_a) * style.second_length)
        if style.anti_aliasing:
            sx, sy = second_tip_x, second_tip_y
        else:
            sx, sy = _point_on_angle(second_a, style.second_length)
        _draw_line(
            data,
            CENTER,
            CENTER,
            sx,
            sy,
            style.second_hand_color,
            style.second_thickness,
            anti_aliasing=style.anti_aliasing,
        )

    # Tip accents ensure both hour and minute hands visibly progress each
    # second on a 64x64 grid, even when integer endpoints would look static.
    _draw_subpixel_dot(data, hour_tip_x, hour_tip_y, style.hour_hand_color, strength=1.4)
    _draw_subpixel_dot(data, minute_tip_x, minute_tip_y, style.minute_hand_color, strength=1.8)
    _draw_dot(
        data,
        CENTER,
        CENTER,
        style.center_radius,
        style.center_color,
        style.dot_anti_aliasing,
    )

    return Buffer.from_flat_list(data)


def _downsample_frames(frames: Sequence[GifFrame], max_frames: int) -> list[GifFrame]:
    if len(frames) <= max_frames:
        return list(frames)
    max_frames = max(1, max_frames)
    step = max(1, len(frames) // max_frames)
    reduced = list(frames[::step])
    if len(reduced) > max_frames:
        reduced = reduced[:max_frames]
    if reduced[-1] is not frames[-1]:
        reduced.append(frames[-1])
    return reduced


def build_segment_sequence(
    segment_start: float,
    segment_seconds: float,
    fps: int,
    max_frames: int,
    style: ClockStyle,
) -> GifSequence:
    base_count = max(1, int(round(segment_seconds * max(1, fps))))
    frame_count = min(max(1, max_frames), base_count)
    frame_dt = segment_seconds / frame_count
    frame_duration_ms = max(20, int(round(frame_dt * 1000.0)))

    frames = [
        GifFrame(
            image=render_clock_frame(segment_start + (i * frame_dt), style),
            duration_ms=frame_duration_ms,
        )
        for i in range(frame_count)
    ]
    frames = _downsample_frames(frames, max_frames)
    return GifSequence(frames=frames, speed_ms=frame_duration_ms)


def _is_retriable_upload_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "illegal json" in msg or "timed out" in msg or "timeout" in msg


def upload_sequence_resilient(
    pixoo: Pixoo,
    sequence: GifSequence,
    upload_mode: UploadMode,
    chunk_size: int,
) -> tuple[UploadMode, int, int]:
    retries = 0
    mode = upload_mode
    sequence_attempt = sequence

    for _ in range(3):
        try:
            pixoo.upload_sequence(sequence_attempt, mode=mode, chunk_size=chunk_size)
            return mode, retries, len(sequence_attempt.frames)
        except (RuntimeError, requests.exceptions.RequestException) as exc:
            if not _is_retriable_upload_error(exc):
                raise
            retries += 1
            if mode != UploadMode.FRAME_BY_FRAME:
                mode = UploadMode.FRAME_BY_FRAME
                continue
            if len(sequence_attempt.frames) > 16:
                reduced = _downsample_frames(sequence_attempt.frames, len(sequence_attempt.frames) // 2)
                sequence_attempt = GifSequence(frames=reduced, speed_ms=sequence_attempt.speed_ms)
                continue
            raise

    raise RuntimeError("Upload failed after retries")


def _log(msg: str) -> None:
    print(f"{datetime.now().strftime('%H:%M:%S')} {msg}", flush=True)


def _band_palette(band: str) -> tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int], tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]:
    return (
        DEFAULT_DIAL_COLOR,
        parse_color(f"dark.{band}7"),
        parse_color(f"dark.{band}10"),
        parse_color(f"dark.{band}9"),
        parse_color(f"dark.{band}7"),
        parse_color(f"dark.{band}5"),
    )


def _demo_variants(base_style: ClockStyle, bands: Sequence[str]) -> list[ClockStyle]:
    if not bands:
        return []

    combo_grid = [
        (face, second_hand, anti_aliasing)
        for face in FACE_NAMES
        for second_hand in (True, False)
        for anti_aliasing in (False, True)
    ]
    combo_count = len(combo_grid)
    # Step through combos with a stride coprime to combo_count to mix
    # second-hand/AA/face states quickly while cycling color every step.
    combo_stride = 5
    while math.gcd(combo_stride, combo_count) != 1:
        combo_stride += 2

    variants: list[ClockStyle] = []
    total = len(bands) * combo_count
    for index in range(total):
        band = bands[index % len(bands)]
        face, second_hand, anti_aliasing = combo_grid[(index * combo_stride) % combo_count]
        (
            dial_color,
            marker_color,
            top_marker_color,
            hour_hand_color,
            minute_hand_color,
            accent_color,
        ) = _band_palette(band)
        variants.append(
            ClockStyle(
                dial_color=dial_color,
                marker_color=marker_color,
                top_marker_color=top_marker_color,
                hour_hand_color=hour_hand_color,
                minute_hand_color=minute_hand_color,
                second_hand_color=accent_color,
                center_color=accent_color,
                hour_length=base_style.hour_length,
                minute_length=base_style.minute_length,
                second_length=base_style.second_length,
                marker_inner_radius=base_style.marker_inner_radius,
                marker_outer_radius=base_style.marker_outer_radius,
                marker_thickness=base_style.marker_thickness,
                top_marker_thickness=base_style.top_marker_thickness,
                quarter_marker_thickness=base_style.quarter_marker_thickness,
                hour_thickness=base_style.hour_thickness,
                minute_thickness=base_style.minute_thickness,
                second_thickness=base_style.second_thickness,
                center_radius=base_style.center_radius,
                face=face,
                band=band,
                second_hand=second_hand,
                anti_aliasing=anti_aliasing,
                dot_anti_aliasing=base_style.dot_anti_aliasing,
            )
        )
    return variants


def run(args: argparse.Namespace) -> None:
    style = _style_from_args(args)
    requested_fps = max(1, args.fps)
    adaptive_fps = requested_fps
    segment_seconds = args.segment_seconds
    upload_mode = UploadMode(args.upload_mode)

    pixoo = Pixoo(args.ip)
    if not pixoo.connect():
        raise SystemExit("Failed to connect to Pixoo device")

    try:
        if args.sync_utc:
            pixoo.set_utc_time(int(time.time()))

        _log(
            "Starting pixooclock: "
            f"face={style.face} band={style.band} second_hand={style.second_hand} anti_aliasing={style.anti_aliasing} "
            f"fps={adaptive_fps} segment={segment_seconds:.1f}s max_frames={args.max_frames} "
            f"upload_mode={upload_mode.value} delivery={args.delivery}"
        )
        _log("Clock should show continuously advancing time with smooth hand movement.")

        if args.demo:
            _run_push_demo(pixoo, args, style, requested_fps)
            return

        if args.delivery == "push":
            _run_push_clock(pixoo, args, style, requested_fps)
            return

        segment_index = 0
        next_start = aligned_segment_start(time.time(), segment_seconds)

        while True:
            now = time.time()
            if next_start <= now:
                missed = int((now - next_start) // segment_seconds) + 1
                next_start += missed * segment_seconds
                _log(f"Skipped {missed} stale segment window(s) to re-align phase.")

            sequence = build_segment_sequence(
                next_start,
                segment_seconds=segment_seconds,
                fps=adaptive_fps,
                max_frames=args.max_frames,
                style=style,
            )

            wait_s = next_start - time.time()
            if wait_s > 0:
                time.sleep(wait_s)

            if args.sync_utc and segment_index > 0 and segment_index % args.utc_resync_segments == 0:
                pixoo.set_utc_time(int(time.time()))

            upload_started = time.time()
            mode_used, retries, frame_count = upload_sequence_resilient(
                pixoo,
                sequence,
                upload_mode=upload_mode,
                chunk_size=args.chunk_size,
            )
            upload_elapsed = time.time() - upload_started
            lag = time.time() - next_start
            _log(
                "uploaded segment "
                f"index={segment_index} start={next_start:.3f} frames={frame_count} "
                f"mode={mode_used.value} retries={retries} upload={upload_elapsed:.2f}s lag={lag:.2f}s"
            )

            budget = segment_seconds * 0.60
            if upload_elapsed > budget and adaptive_fps > 3:
                adaptive_fps -= 1
                _log(f"Upload exceeded budget ({budget:.2f}s); lowering fps to {adaptive_fps}.")
            elif upload_elapsed < (segment_seconds * 0.30) and adaptive_fps < requested_fps:
                adaptive_fps += 1
                _log(f"Upload under budget; raising fps to {adaptive_fps}.")

            segment_index += 1
            if args.once:
                break
            next_start += segment_seconds
    finally:
        pixoo.close()


def _run_push_clock(
    pixoo: Pixoo,
    args: argparse.Namespace,
    style: ClockStyle,
    requested_fps: int,
) -> None:
    adaptive_fps = requested_fps
    interval = 1.0 / adaptive_fps
    frame_index = 0
    next_tick = time.time()
    once_frames = max(1, int(round(args.segment_seconds * requested_fps)))
    resync_every_seconds = max(1, args.utc_resync_segments) * args.segment_seconds
    next_resync_at = time.time() + resync_every_seconds

    _log("delivery=push: no per-segment upload swap; avoids device loading overlay.")

    while True:
        now = time.time()
        if args.sync_utc and now >= next_resync_at:
            pixoo.set_utc_time(int(now))
            next_resync_at = now + resync_every_seconds

        frame = render_clock_frame(now, style)
        upload_started = time.time()
        pixoo.push_buffer(list(frame.data))
        upload_elapsed = time.time() - upload_started

        if frame_index % max(1, adaptive_fps) == 0:
            _log(
                f"pushed frame idx={frame_index} fps={adaptive_fps} "
                f"upload={upload_elapsed:.3f}s"
            )

        budget = interval * 0.90
        if upload_elapsed > budget and adaptive_fps > 3:
            adaptive_fps -= 1
            interval = 1.0 / adaptive_fps
            _log(f"push upload exceeded budget ({budget:.3f}s); lowering fps to {adaptive_fps}.")
        elif upload_elapsed < (interval * 0.40) and adaptive_fps < requested_fps:
            adaptive_fps += 1
            interval = 1.0 / adaptive_fps
            _log(f"push upload under budget; raising fps to {adaptive_fps}.")

        frame_index += 1
        if args.once and frame_index >= once_frames:
            break

        next_tick += interval
        sleep_for = next_tick - time.time()
        if sleep_for > 0:
            time.sleep(sleep_for)
        else:
            while next_tick <= time.time():
                next_tick += interval


def _run_push_demo(
    pixoo: Pixoo,
    args: argparse.Namespace,
    base_style: ClockStyle,
    requested_fps: int,
) -> None:
    adaptive_fps = requested_fps
    interval = 1.0 / adaptive_fps
    next_tick = time.time()
    frame_index = 0
    bands = (args.band,) if args.band else tuple(args.demo_bands)
    variants = _demo_variants(base_style, bands=bands)
    demo_hold = max(0.5, args.demo_interval_seconds)
    variant_index = 0

    if args.delivery != "push":
        _log("--demo forces delivery=push to avoid loading overlays between variations.")

    _log(
        f"demo mode: cycling {len(variants)} variations every {demo_hold:.1f}s "
        f"(bands={len(bands)} x faces={len(FACE_NAMES)} x second_hand=2 x anti_aliasing=2)"
    )

    while True:
        style = variants[variant_index]
        _log(
            "demo variation "
            f"{variant_index + 1}/{len(variants)} band={style.band} face={style.face} "
            f"second_hand={style.second_hand} anti_aliasing={style.anti_aliasing}"
        )
        variant_end = time.time() + demo_hold

        while time.time() < variant_end:
            now = time.time()
            frame = render_clock_frame(now, style)
            upload_started = time.time()
            pixoo.push_buffer(list(frame.data))
            upload_elapsed = time.time() - upload_started

            budget = interval * 0.90
            if upload_elapsed > budget and adaptive_fps > 3:
                adaptive_fps -= 1
                interval = 1.0 / adaptive_fps
                _log(
                    f"push upload exceeded budget ({budget:.3f}s); lowering fps to {adaptive_fps}."
                )
            elif upload_elapsed < (interval * 0.40) and adaptive_fps < requested_fps:
                adaptive_fps += 1
                interval = 1.0 / adaptive_fps
                _log(f"push upload under budget; raising fps to {adaptive_fps}.")

            frame_index += 1
            if frame_index % max(1, adaptive_fps) == 0:
                _log(
                    f"demo frame idx={frame_index} fps={adaptive_fps} "
                    f"upload={upload_elapsed:.3f}s"
                )

            next_tick += interval
            sleep_for = next_tick - time.time()
            if sleep_for > 0:
                time.sleep(sleep_for)
            else:
                while next_tick <= time.time():
                    next_tick += interval

        variant_index = (variant_index + 1) % len(variants)
        if args.once and variant_index == 0:
            break


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
