"""Send a display list item using dial/display fonts."""

from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv

from pypixoo import DisplayItem, GifFrame, GifSequence, Pixoo, UploadMode
from pypixoo.buffer import Buffer

load_dotenv()
DEFAULT_IP = os.environ.get("PIXOO_DEVICE_IP") or os.environ.get("PIXOO_IP") or "192.168.0.37"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send a display list item")
    parser.add_argument("--ip", default=DEFAULT_IP)
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

    item = DisplayItem(
        text_id=1,
        item_type=1,
        x=0,
        y=0,
        direction=0,
        font=4,
        text_width=32,
        text_height=16,
        text="HELLO",
        speed=10,
        color="#FFFFFF",
    )
    pixoo.send_display_list([item])


if __name__ == "__main__":
    main()
