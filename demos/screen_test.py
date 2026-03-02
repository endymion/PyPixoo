#!/usr/bin/env python3
"""Cycle through screen test patterns on the Pixoo (5 seconds each).

Letter A is captured from local HTML (Tiny5 web font) using a 192×192 viewport
and 18px font so the glyph is 5+ pixels tall after 3×3 downscale to 64×64.
Requires: pip install -e ".[browser]"

  python demos/screen_test.py
  python demos/screen_test.py --duration 3
  python demos/screen_test.py --save-frame                    # save to demos/fixtures/letter_a_rendered.png
  python demos/screen_test.py --save-frame /path/to/frame.png # save to given path

Press Ctrl+C to stop.
"""

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("PIXOO_REAL_DEVICE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image

from pypixoo import (
    Pixoo,
    AnimationPlayer,
    AnimationSequence,
    Frame,
    FrameRenderer,
    StaticFrameSource,
    WebFrameSource,
)
from pypixoo.buffer import Buffer

IP_DEFAULT = "192.168.0.37"
SIZE = 64
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _black_buffer() -> list[int]:
    return [0] * (SIZE * SIZE * 3)


def _single_pixel_buffer() -> Buffer:
    """One white pixel at (0, 0)."""
    data = _black_buffer()
    data[0] = data[1] = data[2] = 255
    return Buffer.from_flat_list(data)


def _stripe_pattern_buffer() -> Buffer:
    """Vertical strips: every-other pixel on in even columns; odd columns blank."""
    data = _black_buffer()
    for x in range(0, SIZE, 2):
        for y in range(0, SIZE, 2):
            i = (y * SIZE + x) * 3
            data[i] = data[i + 1] = data[i + 2] = 255
    return Buffer.from_flat_list(data)


def _threshold_to_binary(buf: Buffer) -> Buffer:
    """Force each pixel to black or white by luminance. Uses 64 so rows that were averaged with background in 2x downsampling (e.g. ~64) still light up."""
    data = list(buf.data)
    for i in range(0, len(data), 3):
        r, g, b = data[i], data[i + 1], data[i + 2]
        lum = (r + g + b) / 3
        v = 255 if lum >= 64 else 0
        data[i] = data[i + 1] = data[i + 2] = v
    return Buffer.from_flat_list(data)


def _buffer_to_png(buf: Buffer, path: Path) -> None:
    """Write a 64×64 Buffer to a PNG file for inspection. (0,0) is top-left."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (buf.width, buf.height))
    pixels = img.load()
    for y in range(buf.height):
        for x in range(buf.width):
            r, g, b = buf.get_pixel(x, y)
            pixels[x, y] = (r, g, b)
    img.save(path)


def _threshold_png_to_binary(src_path: Path, dst_path: Path, threshold: int = 64) -> None:
    """Convert an RGB PNG to black/white for crisp inspection."""
    src_path = Path(src_path)
    dst_path = Path(dst_path)
    img = Image.open(src_path).convert("RGB")
    pix = img.load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b = pix[x, y]
            lum = (r + g + b) / 3
            v = 255 if lum >= threshold else 0
            pix[x, y] = (v, v, v)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(dst_path)


def main():
    parser = argparse.ArgumentParser(
        description="Cycle screen test patterns on Pixoo (5s each)."
    )
    parser.add_argument("--ip", default=IP_DEFAULT, help=f"Device IP (default: {IP_DEFAULT})")
    parser.add_argument(
        "--duration",
        type=float,
        default=5.0,
        help="Seconds per screen (default: 5)",
    )
    parser.add_argument(
        "--save-frame",
        nargs="?",
        const="",
        default=None,
        metavar="PATH",
        help="Save the rendered letter A frame(s) to PATH (default: demos/fixtures/letter_a_rendered.png). Writes both pre- and post-threshold PNGs so you can inspect what we send to the device.",
    )
    args = parser.parse_args()

    duration_ms = int(args.duration * 1000)
    letter_a_path = FIXTURES_DIR / "letter_a_192.html"
    if not letter_a_path.exists():
        print(f"error: Fixture not found: {letter_a_path}", file=sys.stderr)
        sys.exit(1)

    save_raw_path = str((FIXTURES_DIR / "letter_a_fullres.png").resolve()) if args.save_frame is not None else None
    sources = [
        WebFrameSource(
            url=letter_a_path.as_uri(),
            timestamps=[0],
            duration_per_frame_ms=duration_ms,
            browser_mode="per_frame",
            timestamp_param="t",
            viewport_size=192,
            save_raw_screenshot_path=save_raw_path,
        ),
    ]
    print("Precomputing letter A frame...")
    if save_raw_path:
        print(f"Will save full-resolution screenshot to: {save_raw_path}")
    renderer = FrameRenderer(sources)
    seq = renderer.precompute()
    raw_frame = seq.frames[0].image
    frames = [
        Frame(
            image=_threshold_to_binary(raw_frame),
            duration_ms=seq.frames[0].duration_ms,
        )
    ]
    seq = AnimationSequence(frames=frames)

    if args.save_frame is not None:
        base = Path(args.save_frame) if args.save_frame else FIXTURES_DIR / "letter_a_rendered"
        if base.suffix.lower() == ".png":
            pre_path = base.parent / (base.stem + "_pre.png")
            post_path = base
        else:
            pre_path = Path(str(base) + "_pre.png")
            post_path = Path(str(base) + ".png")
        _buffer_to_png(raw_frame, pre_path)
        _buffer_to_png(seq.frames[0].image, post_path)
        fullres = FIXTURES_DIR / "letter_a_fullres.png"
        fullres_binary = FIXTURES_DIR / "letter_a_fullres_binary.png"
        if fullres.exists():
            _threshold_png_to_binary(fullres, fullres_binary, threshold=64)
        print(f"Saved full-resolution (192x192) screenshot: {fullres}")
        print(f"Saved full-resolution binary (192x192):   {fullres_binary}")
        print(f"Saved pre-threshold (64x64):  {pre_path}")
        print(f"Saved post-threshold (64x64): {post_path}")
        print("(Open fullres_binary PNG for a crisp no-anti-aliasing debug view.)")

    print(f"Got {len(seq.frames)} screen(s). Connecting to Pixoo...")

    pixoo = Pixoo(args.ip)
    if not pixoo.connect():
        print(f"error: Failed to connect to {args.ip}", file=sys.stderr)
        sys.exit(1)
    try:
        player = AnimationPlayer(
            seq,
            loop=1,
            end_on="last_frame",
            blend_mode="opaque",
        )
        print(f"Showing letter A ({args.duration}s). Ctrl+C to stop.")
        while True:
            player.play_async(pixoo)
            player.wait()
    except KeyboardInterrupt:
        print("\nStopped")
    finally:
        pixoo.close()


if __name__ == "__main__":
    main()
