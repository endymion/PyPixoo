#!/usr/bin/env python3
"""Play the Storybook Clock story smoothly on Pixoo.

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

from dotenv import load_dotenv
# Ensure we can import pypixoo (run from project root)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pypixoo import FrameRenderer, Pixoo, UploadMode, WebFrameSource

load_dotenv()
IP_DEFAULT = os.environ.get("PIXOO_DEVICE_IP") or os.environ.get("PIXOO_IP") or "192.168.0.37"
# Clock story iframe URL (t is appended per frame)
CLOCK_URL_DEFAULT = "http://localhost:6006/iframe.html?id=pixoo-clock--default"


def _run_push_loop(pixoo: Pixoo, sequence) -> None:
    frame_payloads = [list(frame.image.data) for frame in sequence.frames]
    frame_delays = [max(0.02, frame.duration_ms / 1000.0) for frame in sequence.frames]
    next_tick = time.monotonic()
    loop_count = 0
    print("Pushing pre-rendered frames in a timed loop (no native upload/loading overlay).")
    while True:
        for payload, delay in zip(frame_payloads, frame_delays):
            pixoo.push_buffer(payload)
            next_tick += delay
            sleep_for = next_tick - time.monotonic()
            if sleep_for > 0:
                time.sleep(sleep_for)
        loop_count += 1
        if loop_count % 10 == 0:
            print(f"completed {loop_count} loops", flush=True)


def _run_upload_loop(pixoo: Pixoo, sequence, upload_mode: UploadMode, chunk_size: int, refresh_seconds: float) -> None:
    pixoo.upload_sequence(
        sequence,
        mode=upload_mode,
        chunk_size=chunk_size,
    )
    if refresh_seconds <= 0:
        print("Uploaded once. Device should loop natively (Ctrl+C to stop)...")
        while True:
            time.sleep(1.0)
    else:
        print(
            f"Uploaded initial sequence. Refreshing every {refresh_seconds:.1f}s "
            "(Ctrl+C to stop)..."
        )
        while True:
            time.sleep(max(0.1, refresh_seconds))
            pixoo.upload_sequence(
                sequence,
                mode=upload_mode,
                chunk_size=chunk_size,
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Loop Storybook Clock smoothly via push or native upload delivery")
    parser.add_argument("--ip", default=IP_DEFAULT, help=f"Device IP (default: {IP_DEFAULT})")
    parser.add_argument("--url", default=CLOCK_URL_DEFAULT, help="Clock iframe URL")
    parser.add_argument("--fps", type=int, default=10, help="Frames per second (default: 10)")
    parser.add_argument("--loop-seconds", type=float, default=2.0, help="Animation loop length in seconds (default: 2)")
    parser.add_argument(
        "--delivery",
        choices=["push", "upload"],
        default="push",
        help="Frame delivery mode: push=no-loading loop, upload=native sequence upload",
    )
    parser.add_argument(
        "--upload-mode",
        choices=[UploadMode.FRAME_BY_FRAME.value, UploadMode.COMMAND_LIST.value],
        default=UploadMode.COMMAND_LIST.value,
        help="Upload mode only: native upload transport mode",
    )
    parser.add_argument("--chunk-size", type=int, default=40, help="Upload mode only: CommandList chunk size")
    parser.add_argument(
        "--refresh-seconds",
        type=float,
        default=0.0,
        help="Upload mode only: periodic re-upload interval. 0 means upload once and rely on native loop.",
    )
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

        if args.delivery == "push":
            _run_push_loop(pixoo, seq)
        else:
            _run_upload_loop(
                pixoo,
                seq,
                UploadMode(args.upload_mode),
                args.chunk_size,
                args.refresh_seconds,
            )
    except KeyboardInterrupt:
        print("\nStopped")
    finally:
        pixoo.close()


if __name__ == "__main__":
    main()
