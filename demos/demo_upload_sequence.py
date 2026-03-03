"""Upload a short sequence by pushing frames from the client."""

from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv

from pypixoo import GifFrame, GifSequence, Pixoo, UploadMode
from pypixoo.buffer import Buffer

load_dotenv()
DEFAULT_IP = os.environ.get("PIXOO_DEVICE_IP") or os.environ.get("PIXOO_IP") or "192.168.0.37"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload a simple two-frame sequence")
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

    frames = [
        GifFrame(image=_solid(255, 0, 0), duration_ms=200),
        GifFrame(image=_solid(0, 0, 255), duration_ms=200),
    ]
    seq = GifSequence(frames=frames, speed_ms=200)
    pixoo.upload_sequence(seq, mode=UploadMode.COMMAND_LIST)


if __name__ == "__main__":
    main()
