"""Render web fonts via Playwright, then upload frames to the device."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

from pypixoo import FrameRenderer, Pixoo, UploadMode, WebFrameSource

load_dotenv()
DEFAULT_IP = os.environ.get("PIXOO_DEVICE_IP") or os.environ.get("PIXOO_IP") or "192.168.0.37"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a web font and upload frames")
    parser.add_argument("--ip", default=DEFAULT_IP)
    parser.add_argument(
        "--html",
        default=str(Path(__file__).parent / "fixtures" / "web_font_demo.html"),
        help="Path to local HTML file",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    html_path = Path(args.html).resolve()
    if not html_path.exists():
        raise SystemExit(f"HTML not found: {html_path}")

    url = html_path.as_uri()
    renderer = FrameRenderer(
        sources=[
            WebFrameSource(
                url=url,
                timestamps=[0.0],
                duration_per_frame_ms=1000,
                viewport_size=192,
                downsample_mode="maxpool",
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
