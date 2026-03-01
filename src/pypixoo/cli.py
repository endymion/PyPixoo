"""CLI for PyPixoo: fill, load-image, and future subcommands."""

import argparse
import os
import sys
from pathlib import Path

from pypixoo import Pixoo, DeviceInUseError
from pypixoo.color import parse_color


DEFAULT_IP = "192.168.0.37"


def _require_real_device() -> None:
    if os.environ.get("PIXOO_REAL_DEVICE") != "1":
        print("error: Set PIXOO_REAL_DEVICE=1 to send to a real device.", file=sys.stderr)
        sys.exit(1)


def _connect(ip: str) -> Pixoo:
    _require_real_device()
    pixoo = Pixoo(ip)
    try:
        if not pixoo.connect():
            print(f"error: Failed to connect to {ip}", file=sys.stderr)
            sys.exit(1)
        return pixoo
    except DeviceInUseError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_fill(ip: str, color: str) -> None:
    """Fill the display with a solid color and push once."""
    r, g, b = parse_color(color)
    pixoo = _connect(ip)
    try:
        pixoo.fill(r, g, b)
        pixoo.push()
    finally:
        pixoo.close()


def cmd_load_image(ip: str, path: Path) -> None:
    """Load an image file onto the display (resized to 64x64) and push once."""
    if not path.exists():
        print(f"error: File not found: {path}", file=sys.stderr)
        sys.exit(1)
    pixoo = _connect(ip)
    try:
        pixoo.load_image(path)
        pixoo.push()
    finally:
        pixoo.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pypixoo",
        description="PyPixoo CLI for Divoom Pixoo 64. Set PIXOO_REAL_DEVICE=1 to use a real device.",
    )
    parser.add_argument(
        "--ip",
        default=DEFAULT_IP,
        help=f"Device IP (default: {DEFAULT_IP})",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    fill_p = subparsers.add_parser("fill", help="Fill the display with a solid color")
    fill_p.add_argument(
        "color",
        help="Color: hex (FF00FF, f0f, #f0f) or name (e.g. fuchsia, red)",
    )
    fill_p.set_defaults(func=lambda ns: cmd_fill(ns.ip, ns.color))

    load_p = subparsers.add_parser("load-image", help="Load an image file (resized to 64x64) and push")
    load_p.add_argument("path", type=Path, help="Path to image file")
    load_p.set_defaults(func=lambda ns: cmd_load_image(ns.ip, ns.path))

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
