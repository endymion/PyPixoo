#!/usr/bin/env python3
"""Cycle through Tiny5 text demo screens on the Pixoo (5 seconds per screen).

Shows: alphabet, numbers, alert, warning, success, info, custom — in a loop.
Uses a local 192x192 fixture and 3x downsample to produce crisp 4x5 Tiny5 glyphs
on the 64x64 device output.

Requires: pip install -e ".[browser]"

  python demos/font_showcase.py
  python demos/font_showcase.py --ip 192.168.0.38 --duration 3

Press Ctrl+C to stop.
"""

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlencode

os.environ.setdefault("PIXOO_REAL_DEVICE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pypixoo import Pixoo, FrameRenderer, WebFrameSource, AnimationPlayer, AnimationSequence, Frame
from pypixoo.buffer import Buffer
from PIL import Image

IP_DEFAULT = "192.168.0.37"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
TINYTEXT_FIXTURE = FIXTURES_DIR / "tinytext_192.html"
TRACKING_PX = 0

# TinyText variants (one frame per variant)
TINYTEXT_VARIANTS = [
    "alphabet",
    "numbers",
    "alert",
    "warning",
    "success",
    "info",
    "custom",
]

VARIANT_COLORS = {
    "alphabet": ("#000", "#fff"),
    "numbers": ("#000", "#aaa"),
    "alert": ("#200", "#f66"),
    "warning": ("#330", "#ff0"),
    "success": ("#030", "#6f6"),
    "info": ("#003", "#6af"),
    "custom": ("#111", "#0f0"),
}


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) != 6:
        raise ValueError(f"Unsupported color format: {value}")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def _quantize_to_two_colors(
    buf: Buffer,
    bg_rgb: tuple[int, int, int],
    fg_rgb: tuple[int, int, int],
) -> Buffer:
    """Map each pixel to nearest of background/foreground colors for crisp text."""
    data = list(buf.data)
    for i in range(0, len(data), 3):
        r, g, b = data[i], data[i + 1], data[i + 2]
        d_bg = (r - bg_rgb[0]) ** 2 + (g - bg_rgb[1]) ** 2 + (b - bg_rgb[2]) ** 2
        d_fg = (r - fg_rgb[0]) ** 2 + (g - fg_rgb[1]) ** 2 + (b - fg_rgb[2]) ** 2
        pr, pg, pb = fg_rgb if d_fg <= d_bg else bg_rgb
        data[i] = pr
        data[i + 1] = pg
        data[i + 2] = pb
    return Buffer.from_flat_list(data)


def build_variant_url(variant: str) -> str:
    query = {"variant": variant, "tracking": TRACKING_PX}
    return f"{TINYTEXT_FIXTURE.as_uri()}?{urlencode(query)}"


def _buffer_to_png(buf: Buffer, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (buf.width, buf.height))
    pixels = img.load()
    for y in range(buf.height):
        for x in range(buf.width):
            pixels[x, y] = buf.get_pixel(x, y)
    img.save(path)


def main():
    parser = argparse.ArgumentParser(
        description="Cycle TinyText font demo screens on Pixoo (5s each)."
    )
    parser.add_argument("--ip", default=IP_DEFAULT, help=f"Device IP (default: {IP_DEFAULT})")
    parser.add_argument(
        "--duration",
        type=float,
        default=5.0,
        help="Seconds per screen (default: 5)",
    )
    parser.add_argument(
        "--save-frames",
        nargs="?",
        const="",
        default=None,
        metavar="DIR",
        help="Save pre-device 64x64 frames to DIR (default: demos/fixtures/font_showcase_frames).",
    )
    parser.add_argument(
        "--save-only",
        action="store_true",
        help="Precompute and optionally save frames, then exit without connecting to device.",
    )
    args = parser.parse_args()

    duration_ms = int(args.duration * 1000)
    if not TINYTEXT_FIXTURE.exists():
        print(f"error: Fixture not found: {TINYTEXT_FIXTURE}", file=sys.stderr)
        sys.exit(1)

    sources = [
        WebFrameSource(
            url=build_variant_url(variant),
            timestamps=[0],
            duration_per_frame_ms=duration_ms,
            browser_mode="per_frame",
            timestamp_param="t",
            viewport_size=192,
            downsample_mode="nearest",
        )
        for variant in TINYTEXT_VARIANTS
    ]

    print("Precomputing Tiny5 text frames from local fixture...")
    renderer = FrameRenderer(sources)
    seq = renderer.precompute()
    frames = []
    for variant, f in zip(TINYTEXT_VARIANTS, seq.frames):
        bg_hex, fg_hex = VARIANT_COLORS[variant]
        q = _quantize_to_two_colors(
            f.image,
            _hex_to_rgb(bg_hex),
            _hex_to_rgb(fg_hex),
        )
        frames.append(Frame(image=q, duration_ms=f.duration_ms))
    seq = AnimationSequence(frames=frames)

    if args.save_frames is not None:
        out_dir = Path(args.save_frames) if args.save_frames else FIXTURES_DIR / "font_showcase_frames"
        out_dir.mkdir(parents=True, exist_ok=True)
        for idx, (variant, frame) in enumerate(zip(TINYTEXT_VARIANTS, seq.frames)):
            out_path = out_dir / f"{idx:02d}_{variant}.png"
            _buffer_to_png(frame.image, out_path)
        print(f"Saved {len(seq.frames)} frame PNGs to: {out_dir}")

    if args.save_only:
        print("Exiting because --save-only was set.")
        return

    print(f"Got {len(seq.frames)} screens. Connecting to Pixoo...")

    pixoo = Pixoo(args.ip)
    try:
        if not pixoo.connect():
            raise RuntimeError(f"Failed to connect to {args.ip}")
        player = AnimationPlayer(
            seq,
            loop=1,
            end_on="last_frame",
            blend_mode="opaque",
        )
        print(f"Showing font showcase ({args.duration}s per screen). Ctrl+C to stop.")
        while True:
            player.play_async(pixoo)
            player.wait()
    except KeyboardInterrupt:
        print("\nStopped")
    finally:
        pixoo.close()


if __name__ == "__main__":
    main()
