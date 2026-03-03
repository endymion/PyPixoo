"""Tell the device to fetch and play a GIF from a URL."""

from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv

from pypixoo import GifSource, Pixoo

load_dotenv()
DEFAULT_IP = os.environ.get("PIXOO_DEVICE_IP") or os.environ.get("PIXOO_IP") or "192.168.0.37"
DEFAULT_URL = "https://media.giphy.com/media/ICOgUNjpvO0PC/giphy.gif"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Play a GIF via device URL fetch")
    parser.add_argument("--ip", default=DEFAULT_IP)
    parser.add_argument("--url", default=DEFAULT_URL)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    pixoo = Pixoo(args.ip)
    if not pixoo.connect():
        raise SystemExit("Failed to connect")

    pixoo.play_gif(GifSource.url(args.url))


if __name__ == "__main__":
    main()
