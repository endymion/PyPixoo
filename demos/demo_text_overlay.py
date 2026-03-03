"""Upload a frame and render a device overlay text on top."""

from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv

from pypixoo import BuiltinFont, GifFrame, GifSequence, Pixoo, TextOverlay, UploadMode
from pypixoo.buffer import Buffer

load_dotenv()
DEFAULT_IP = os.environ.get("PIXOO_DEVICE_IP") or os.environ.get("PIXOO_IP") or "192.168.0.37"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send a text overlay")
    parser.add_argument("--ip", default=DEFAULT_IP)
    parser.add_argument("--text", default="HELLO")
    return parser.parse_args()


def _solid(r: int, g: int, b: int) -> Buffer:
    data = [c for _ in range(64 * 64) for c in (r, g, b)]
    return Buffer.from_flat_list(data)


def main() -> None:
    args = _parse_args()

    pixoo = Pixoo(args.ip)
    if not pixoo.connect():
        raise SystemExit("Failed to connect")

    frame = GifFrame(image=_solid(0, 0, 0), duration_ms=1000)
    seq = GifSequence(frames=[frame], speed_ms=1000)
    pixoo.upload_sequence(seq, mode=UploadMode.COMMAND_LIST)

    overlay = TextOverlay(
        text=args.text,
        x=0,
        y=40,
        font=BuiltinFont.FONT_4,
        text_width=64,
        speed=10,
        color="#FFFF00",
        align=1,
    )
    pixoo.send_text_overlay(overlay)


if __name__ == "__main__":
    main()
