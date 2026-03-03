"""Send a display list item using dial/display fonts."""

from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv

from pypixoo import DisplayItem, GifFrame, GifSequence, Pixoo, UploadMode
from pypixoo.buffer import Buffer
from pypixoo.color import parse_color

load_dotenv()
DEFAULT_IP = os.environ.get("PIXOO_DEVICE_IP") or os.environ.get("PIXOO_IP") or "192.168.0.37"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send a display list item")
    parser.add_argument("--ip", default=DEFAULT_IP)
    parser.add_argument("--text", default="HELLO")
    parser.add_argument(
        "--color",
        default="dark.sand5",
        help="Text color as Radix token/hex/rgb (default: dark.sand5)",
    )
    parser.add_argument(
        "--font-id",
        type=int,
        default=2,
        help="Display-list font id from Divoom font registry (default: 2)",
    )
    parser.add_argument(
        "--item-type",
        type=int,
        default=22,
        help="Display item type (22=text message, default: 22)",
    )
    parser.add_argument(
        "--channel-index",
        type=int,
        default=-1,
        help="Optional channel index switch before item list (-1 keeps current channel)",
    )
    return parser.parse_args()


def _solid(r: int, g: int, b: int) -> Buffer:
    data = [c for _ in range(64 * 64) for c in (r, g, b)]
    return Buffer.from_flat_list(data)


def main() -> None:
    args = _parse_args()
    rgb = parse_color(args.color)
    color_hex = f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"

    pixoo = Pixoo(args.ip)
    if not pixoo.connect():
        raise SystemExit("Failed to connect")
    if args.channel_index >= 0:
        pixoo.set_channel_index(args.channel_index)

    frame = GifFrame(image=_solid(0, 0, 0), duration_ms=1000)
    seq = GifSequence(frames=[frame], speed_ms=1000)
    pixoo.upload_sequence(seq, mode=UploadMode.FRAME_BY_FRAME)

    item = DisplayItem(
        text_id=1,
        item_type=args.item_type,
        x=0,
        y=0,
        direction=0,
        font=args.font_id,
        text_width=32,
        text_height=16,
        text=args.text,
        speed=10,
        color=color_hex,
    )
    pixoo.send_display_list([item])


if __name__ == "__main__":
    main()
