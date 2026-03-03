#!/usr/bin/env python3
"""Three-hand analog clock demo using stitched native uploads.

This demo renders a true analog clock (hour/minute/second hands) in Python and
uploads short phase-locked frame segments to the device. It is intentionally
bounded by frame budget controls to stay within device upload limits.
"""

from __future__ import annotations

import argparse
import math
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

import requests
from dotenv import load_dotenv

from pypixoo import GifFrame, GifSequence, Pixoo, UploadMode
from pypixoo.buffer import Buffer
from pypixoo.color import parse_color

load_dotenv()
SIZE = 64
CENTER = SIZE // 2
DEFAULT_IP = os.environ.get("PIXOO_DEVICE_IP") or os.environ.get("PIXOO_IP") or "192.168.0.37"


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
    hour_thickness: int
    minute_thickness: int
    second_thickness: int
    center_radius: int


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


def build_parser(ip_default: str = DEFAULT_IP) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Three-hand analog clock via stitched native uploads. "
            "Color args support hex/rgb/names plus Radix tokens (gray11, dark.gray11, grayDark11)."
        )
    )
    parser.add_argument("--ip", default=ip_default, help=f"Device IP (default: {ip_default})")
    parser.add_argument(
        "--delivery",
        choices=["push", "stitched"],
        default="push",
        help="push=no-loading continuous frame push; stitched=segment uploads (may show loading overlay)",
    )
    parser.add_argument("--fps", type=_positive_int, default=5, help="Target frames per second")
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

    # Style
    parser.add_argument("--dial-color", type=_parse_color_arg, default=(0, 0, 0))
    parser.add_argument("--marker-color", type=_parse_color_arg, default=parse_color("dark.purple7"))
    parser.add_argument("--top-marker-color", type=_parse_color_arg, default=parse_color("dark.purple10"))
    parser.add_argument("--hour-hand-color", type=_parse_color_arg, default=parse_color("dark.purple9"))
    parser.add_argument("--minute-hand-color", type=_parse_color_arg, default=parse_color("dark.purple7"))
    parser.add_argument("--second-hand-color", type=_parse_color_arg, default=parse_color("dark.purple5"))
    parser.add_argument("--center-color", type=_parse_color_arg, default=parse_color("dark.purple5"))
    parser.add_argument("--hour-length", type=_positive_int, default=16)
    parser.add_argument("--minute-length", type=_positive_int, default=23)
    parser.add_argument("--second-length", type=_positive_int, default=28)
    parser.add_argument("--marker-thickness", type=_positive_int, default=1)
    parser.add_argument("--top-marker-thickness", type=_positive_int, default=2)
    parser.add_argument("--hour-thickness", type=_positive_int, default=2)
    parser.add_argument("--minute-thickness", type=_positive_int, default=2)
    parser.add_argument("--second-thickness", type=_positive_int, default=1)
    return parser


def _style_from_args(args: argparse.Namespace) -> ClockStyle:
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
        hour_thickness=args.hour_thickness,
        minute_thickness=args.minute_thickness,
        second_thickness=args.second_thickness,
        center_radius=1,
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


def _draw_disk(data: list[int], cx: int, cy: int, radius: int, color: tuple[int, int, int]) -> None:
    radius = max(0, radius)
    rr = radius * radius
    for y in range(cy - radius, cy + radius + 1):
        for x in range(cx - radius, cx + radius + 1):
            dx = x - cx
            dy = y - cy
            if (dx * dx) + (dy * dy) <= rr:
                _set_px(data, x, y, color)


def _draw_line(
    data: list[int],
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    color: tuple[int, int, int],
    thickness: int = 1,
) -> None:
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


def _point_on_angle(angle: float, radius: int) -> tuple[int, int]:
    x = int(round(CENTER + (math.cos(angle) * radius)))
    y = int(round(CENTER + (math.sin(angle) * radius)))
    return x, y


def render_clock_frame(ts: float, style: ClockStyle) -> Buffer:
    data = _new_canvas(style.dial_color)

    # Tick markers (12 brighter).
    for i in range(12):
        marker_angle = ((i / 12.0) * 2.0 * math.pi) - (math.pi / 2.0)
        x0, y0 = _point_on_angle(marker_angle, style.marker_inner_radius)
        x1, y1 = _point_on_angle(marker_angle, style.marker_outer_radius)
        color = style.top_marker_color if i == 0 else style.marker_color
        thickness = style.top_marker_thickness if i == 0 else style.marker_thickness
        _draw_line(data, x0, y0, x1, y1, color, thickness)

    hour_a, minute_a, second_a = angles_for_epoch(ts)
    hx, hy = _point_on_angle(hour_a, style.hour_length)
    mx, my = _point_on_angle(minute_a, style.minute_length)
    sx, sy = _point_on_angle(second_a, style.second_length)

    _draw_line(data, CENTER, CENTER, hx, hy, style.hour_hand_color, style.hour_thickness)
    _draw_line(data, CENTER, CENTER, mx, my, style.minute_hand_color, style.minute_thickness)
    _draw_line(data, CENTER, CENTER, sx, sy, style.second_hand_color, style.second_thickness)
    _draw_disk(data, CENTER, CENTER, style.center_radius, style.center_color)

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
            "Starting three-hand clock: "
            f"fps={adaptive_fps} segment={segment_seconds:.1f}s max_frames={args.max_frames} "
            f"upload_mode={upload_mode.value} delivery={args.delivery}"
        )
        _log("Native clock should show continuously advancing seconds.")

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


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
