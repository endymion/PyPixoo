#!/usr/bin/env python3
"""Cycle through deterministic pixel-font demo screens on the Pixoo.

Shows: alphabet, numbers, alert, warning, success, info, custom — in a loop.
Uses a local 192x192 fixture and deterministic per-glyph composition at 64x64.

Requires: pip install -e ".[browser]"

  python demos/font_showcase.py
  python demos/font_showcase.py --ip 192.168.0.38 --duration 10

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

FONT_REGISTRY = {
    "tiny5": {"display_name": "Tiny5", "height_px": 5},
    "micro5": {"display_name": "Micro5", "height_px": 5},
    "bytesized": {"display_name": "Bytesized", "height_px": 4},
    "jersey10": {"display_name": "Jersey10", "height_px": 10},
    "jersey15": {"display_name": "Jersey15", "height_px": 15},
}

FONT_ALPHABET_SCREENS = [
    {"name": "tiny5_alphabet", "variant": "alphabet", "font": "tiny5"},
    {"name": "micro5_alphabet", "variant": "alphabet", "font": "micro5"},
    {"name": "bytesized_alphabet", "variant": "alphabet4", "font": "bytesized"},
    {"name": "jersey10_alphabet", "variant": "alphabet10", "font": "jersey10"},
]

BASE_SHOWCASE_SCREENS: list[dict[str, str | int]] = []

DEFAULT_BG_COLOR = "#000"
DEFAULT_TEXT_COLOR = "#6af"


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) != 6:
        raise ValueError(f"Unsupported color format: {value}")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def _has_foreground(buf: Buffer, bg_rgb: tuple[int, int, int]) -> bool:
    data = buf.data
    br, bg, bb = bg_rgb
    for i in range(0, len(data), 3):
        if data[i] != br or data[i + 1] != bg or data[i + 2] != bb:
            return True
    return False


def _build_font_list_param() -> str:
    parts = []
    for font_key, meta in FONT_REGISTRY.items():
        parts.append(f"{font_key}:{meta['display_name']}:{meta['height_px']}")
    return ",".join(parts)


def _build_showcase_screens() -> list[dict[str, str | int]]:
    screens: list[dict[str, str | int]] = []
    screens.extend(FONT_ALPHABET_SCREENS)
    font_list_pages = min(1, (len(FONT_REGISTRY) + 3) // 4)
    for page in range(font_list_pages):
        screens.append(
            {
                "name": f"font_list_p{page + 1}",
                "variant": "font_list",
                "font": "tiny5",
                "font_list_page": page,
            }
        )
    screens.extend(BASE_SHOWCASE_SCREENS)
    numbered: list[dict[str, str | int]] = []
    for idx, screen in enumerate(screens):
        numbered.append({**screen, "name": f"{idx:02d}_{screen['name']}"})
    return numbered


def build_variant_url(screen: dict[str, str | int], text_color: str, bg_color: str) -> str:
    query = {
        "variant": screen["variant"],
        "tracking": TRACKING_PX,
        "font": screen["font"],
        "fg": text_color,
        "bg": bg_color,
    }
    if screen["variant"] == "font_list":
        query["font_list"] = _build_font_list_param()
        query["font_list_page"] = int(screen.get("font_list_page", 0))
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
        description="Cycle TinyText font demo screens on Pixoo (10s each)."
    )
    parser.add_argument("--ip", default=IP_DEFAULT, help=f"Device IP (default: {IP_DEFAULT})")
    parser.add_argument(
        "--duration",
        type=float,
        default=10.0,
        help="Seconds per screen (default: 10)",
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
    parser.add_argument(
        "--text-color",
        default=DEFAULT_TEXT_COLOR,
        help=f"Text hex color (#RGB or #RRGGBB). Default: {DEFAULT_TEXT_COLOR}",
    )
    parser.add_argument(
        "--bg-color",
        default=DEFAULT_BG_COLOR,
        help=f"Background hex color (#RGB or #RRGGBB). Default: {DEFAULT_BG_COLOR}",
    )
    args = parser.parse_args()

    duration_ms = int(args.duration * 1000)
    bg_rgb = _hex_to_rgb(args.bg_color)
    if not TINYTEXT_FIXTURE.exists():
        print(f"error: Fixture not found: {TINYTEXT_FIXTURE}", file=sys.stderr)
        sys.exit(1)

    showcase_screens = _build_showcase_screens()

    sources = [
        WebFrameSource(
            url=build_variant_url(screen, args.text_color, args.bg_color),
            timestamps=[0],
            duration_per_frame_ms=duration_ms,
            browser_mode="per_frame",
            timestamp_param="t",
            viewport_size=192,
            downsample_mode="nearest",
        )
        for screen in showcase_screens
    ]

    print("Precomputing deterministic font showcase frames from local fixture...")
    max_precompute_attempts = 3
    seq = None
    for attempt in range(1, max_precompute_attempts + 1):
        renderer = FrameRenderer(sources)
        candidate = renderer.precompute()
        frames = []
        blank_name: str | None = None
        for screen, f in zip(showcase_screens, candidate.frames):
            if not _has_foreground(f.image, bg_rgb):
                blank_name = str(screen["name"])
                break
            frames.append(Frame(image=f.image, duration_ms=f.duration_ms))
        if blank_name is None:
            seq = AnimationSequence(frames=frames)
            break
        print(f"Retrying precompute due to blank frame: {blank_name} (attempt {attempt}/{max_precompute_attempts})")
    if seq is None:
        raise RuntimeError("Failed to precompute showcase frames without blanks after retries")

    if args.save_frames is not None:
        out_dir = Path(args.save_frames) if args.save_frames else FIXTURES_DIR / "font_showcase_frames"
        out_dir.mkdir(parents=True, exist_ok=True)
        for old_png in out_dir.glob("*.png"):
            old_png.unlink()
        for screen, frame in zip(showcase_screens, seq.frames):
            out_path = out_dir / f"{screen['name']}.png"
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
