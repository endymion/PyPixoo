#!/usr/bin/env python3
"""Experiment: switching between two sequences with minimal visible gaps.

This demo compares two strategies:

- stitched (recommended): build one combined sequence and upload once.
  This gives the smoothest switching because there is no network upload at
  switch boundaries.
- live (experimental): upload sequence A, then sequence B, repeatedly.
  This may show pauses/stalls during each switch because uploads happen while
  the device is actively displaying.
"""

from __future__ import annotations

import argparse
import os
import time

from dotenv import load_dotenv
import requests

from pypixoo import GifFrame, GifSequence, Pixoo, UploadMode
from pypixoo.buffer import Buffer

load_dotenv()
DEFAULT_IP = os.environ.get("PIXOO_DEVICE_IP") or os.environ.get("PIXOO_IP") or "192.168.0.37"
SIZE = 64


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sequence switching smoothness experiment")
    parser.add_argument("--ip", default=DEFAULT_IP, help=f"Device IP (default: {DEFAULT_IP})")
    parser.add_argument(
        "--mode",
        choices=["stitched", "live"],
        default="stitched",
        help="stitched=single upload with smooth boundaries; live=upload/switch repeatedly",
    )
    parser.add_argument("--fps", type=int, default=5, help="Frames per second for generated sequences")
    parser.add_argument("--bar-width", type=int, default=2, help="Moving bar width in pixels")
    parser.add_argument("--step", type=int, default=2, help="Horizontal movement step in pixels")
    parser.add_argument(
        "--edge-hold-frames",
        type=int,
        default=3,
        help="Extra frames to hold at each edge so endpoint reaches are obvious",
    )
    parser.add_argument(
        "--segment-loops",
        type=int,
        default=1,
        help="How many times each sequence repeats before switching",
    )
    parser.add_argument("--cycles", type=int, default=1, help="Number of A->B switch cycles")
    parser.add_argument(
        "--max-stitched-frames",
        type=int,
        default=88,
        help="Maximum frames to upload in stitched mode (auto-downsamples above this)",
    )
    parser.add_argument(
        "--upload-mode",
        choices=[UploadMode.COMMAND_LIST.value, UploadMode.FRAME_BY_FRAME.value],
        default=UploadMode.FRAME_BY_FRAME.value,
    )
    parser.add_argument("--chunk-size", type=int, default=8, help="CommandList chunk size")
    return parser.parse_args()


def _make_frame(bar_x: int, bar_width: int, bar_rgb: tuple[int, int, int], bg_rgb: tuple[int, int, int]) -> Buffer:
    data: list[int] = []
    for _y in range(SIZE):
        for x in range(SIZE):
            if bar_x <= x < bar_x + bar_width:
                data.extend(bar_rgb)
            else:
                data.extend(bg_rgb)
    return Buffer.from_flat_list(data)


def _build_scan_sequence(
    *,
    fps: int,
    bar_width: int,
    step: int,
    edge_hold_frames: int,
    bar_rgb: tuple[int, int, int],
    bg_rgb: tuple[int, int, int],
    reverse: bool,
) -> GifSequence:
    speed_ms = max(20, int(round(1000 / max(1, fps))))
    xs = list(range(0, SIZE - max(1, bar_width) + 1, max(1, step)))
    if xs[-1] != SIZE - max(1, bar_width):
        xs.append(SIZE - max(1, bar_width))
    if reverse:
        xs = list(reversed(xs))
    hold = max(0, edge_hold_frames)
    if hold > 0 and xs:
        xs = ([xs[0]] * hold) + xs + ([xs[-1]] * hold)
    frames = [
        GifFrame(
            image=_make_frame(x, max(1, bar_width), bar_rgb=bar_rgb, bg_rgb=bg_rgb),
            duration_ms=speed_ms,
        )
        for x in xs
    ]
    return GifSequence(frames=frames, speed_ms=speed_ms)


def _repeat_sequence(sequence: GifSequence, loops: int) -> GifSequence:
    repeated_frames: list[GifFrame] = []
    for _ in range(max(1, loops)):
        repeated_frames.extend(sequence.frames)
    return GifSequence(frames=repeated_frames, speed_ms=sequence.speed_ms)


def _duration_seconds(sequence: GifSequence) -> float:
    return (len(sequence.frames) * sequence.speed_ms) / 1000.0


def _downsample_sequence(sequence: GifSequence, max_frames: int) -> GifSequence:
    if len(sequence.frames) <= max_frames:
        return sequence
    max_frames = max(1, max_frames)
    step = max(1, len(sequence.frames) // max_frames)
    reduced = sequence.frames[::step]
    if len(reduced) > max_frames:
        reduced = reduced[:max_frames]
    if reduced[-1] is not sequence.frames[-1]:
        reduced = [*reduced, sequence.frames[-1]]
    return GifSequence(frames=reduced, speed_ms=sequence.speed_ms)


def _upload_resilient(pixoo: Pixoo, sequence: GifSequence, args: argparse.Namespace) -> None:
    try:
        pixoo.upload_sequence(
            sequence,
            mode=UploadMode(args.upload_mode),
            chunk_size=args.chunk_size,
        )
        return
    except (RuntimeError, requests.exceptions.RequestException) as exc:
        msg = str(exc)
        if "illegal json" not in msg.lower() and "timed out" not in msg.lower():
            raise
        print("Upload path hit device limit/timeout; retrying with frame_by_frame for compatibility.")
        pixoo.upload_sequence(
            sequence,
            mode=UploadMode.FRAME_BY_FRAME,
            chunk_size=1,
        )


def _run_stitched(pixoo: Pixoo, seq_a: GifSequence, seq_b: GifSequence, args: argparse.Namespace) -> None:
    frames: list[GifFrame] = []
    for _ in range(max(1, args.cycles)):
        frames.extend(_repeat_sequence(seq_a, args.segment_loops).frames)
        frames.extend(_repeat_sequence(seq_b, args.segment_loops).frames)
    stitched = GifSequence(frames=frames, speed_ms=seq_a.speed_ms)
    if args.max_stitched_frames > 0 and len(stitched.frames) > args.max_stitched_frames:
        original_count = len(stitched.frames)
        stitched = _downsample_sequence(stitched, args.max_stitched_frames)
        print(
            f"Downsampled stitched sequence from {original_count} to {len(stitched.frames)} frames "
            f"for device upload compatibility."
        )
    total_s = _duration_seconds(stitched)
    print("Mode: stitched (recommended)")
    print("Expected: smooth A->B switching without network-gap pauses.")
    print(f"Uploading {len(stitched.frames)} frames (~{total_s:.1f}s total) ...")
    _upload_resilient(pixoo, stitched, args)
    print("Upload complete. Watch for uninterrupted switching between magenta and cyan scans.")


def _run_live(pixoo: Pixoo, seq_a: GifSequence, seq_b: GifSequence, args: argparse.Namespace) -> None:
    a_hold = _repeat_sequence(seq_a, args.segment_loops)
    b_hold = _repeat_sequence(seq_b, args.segment_loops)
    a_s = _duration_seconds(a_hold)
    b_s = _duration_seconds(b_hold)
    print("Mode: live (experimental)")
    print("Expected: possible pauses at A/B switch boundaries due to upload time.")
    for i in range(max(1, args.cycles)):
        print(f"Cycle {i + 1}/{args.cycles}: uploading sequence A (magenta)")
        _upload_resilient(pixoo, a_hold, args)
        time.sleep(a_s)
        print(f"Cycle {i + 1}/{args.cycles}: uploading sequence B (cyan)")
        _upload_resilient(pixoo, b_hold, args)
        time.sleep(b_s)
    print("Live switch test finished.")


def main() -> None:
    args = _parse_args()
    seq_a = _build_scan_sequence(
        fps=args.fps,
        bar_width=args.bar_width,
        step=args.step,
        edge_hold_frames=args.edge_hold_frames,
        bar_rgb=(255, 0, 255),
        bg_rgb=(8, 0, 8),
        reverse=False,
    )
    seq_b = _build_scan_sequence(
        fps=args.fps,
        bar_width=args.bar_width,
        step=args.step,
        edge_hold_frames=args.edge_hold_frames,
        bar_rgb=(0, 255, 255),
        bg_rgb=(0, 8, 8),
        reverse=True,
    )

    pixoo = Pixoo(args.ip)
    if not pixoo.connect():
        raise SystemExit("Failed to connect to Pixoo device")
    try:
        if args.mode == "stitched":
            _run_stitched(pixoo, seq_a, seq_b, args)
        else:
            _run_live(pixoo, seq_a, seq_b, args)
    finally:
        pixoo.close()


if __name__ == "__main__":
    main()
