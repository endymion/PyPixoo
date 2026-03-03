"""Render Tiny5 from a local fixture, then upload one frame to the device."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from urllib.parse import urlencode

from dotenv import load_dotenv

from pypixoo import FrameRenderer, Pixoo, UploadMode, WebFrameSource
from pypixoo.color import parse_color

load_dotenv()
DEFAULT_IP = os.environ.get("PIXOO_DEVICE_IP") or os.environ.get("PIXOO_IP") or "192.168.0.37"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render Tiny5 and upload a single frame")
    parser.add_argument("--ip", default=DEFAULT_IP)
    parser.add_argument(
        "--fixture",
        default=str(Path(__file__).parent / "fixtures" / "tinytext_192.html"),
        help="Path to local HTML fixture",
    )
    parser.add_argument(
        "--variant",
        default="single_a",
        help="tinytext variant (default: single_a)",
    )
    parser.add_argument(
        "--font",
        default="tiny5",
        help="tinytext font key (default: tiny5)",
    )
    parser.add_argument(
        "--text-color",
        default="dark.sand5",
        help="Text color token/hex/rgb (default: dark.sand5)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    fixture_path = Path(args.fixture).resolve()
    if not fixture_path.exists():
        raise SystemExit(f"Fixture not found: {fixture_path}")

    text_rgb = parse_color(args.text_color)
    text_hex = f"{text_rgb[0]:02x}{text_rgb[1]:02x}{text_rgb[2]:02x}"

    query = urlencode(
        {
            "variant": args.variant,
            "font": args.font,
            "tracking": 0,
            "fg": text_hex,
            "bg": "000000",
        }
    )
    url = f"{fixture_path.as_uri()}?{query}"
    renderer = FrameRenderer(
        sources=[
            WebFrameSource(
                url=url,
                timestamps=[0.0],
                duration_per_frame_ms=1000,
                viewport_size=192,
                device_scale_factor=1,
                downsample_mode="nearest",
            )
        ]
    )
    seq = renderer.precompute()

    pixoo = Pixoo(args.ip)
    if not pixoo.connect():
        raise SystemExit("Failed to connect")

    pixoo.upload_sequence(seq, mode=UploadMode.COMMAND_LIST)


if __name__ == "__main__":
    main()
