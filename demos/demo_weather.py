"""Set weather location and fetch device weather info."""

from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv

from pypixoo import Pixoo

load_dotenv()
DEFAULT_IP = os.environ.get("PIXOO_DEVICE_IP") or os.environ.get("PIXOO_IP") or "192.168.0.37"
DEFAULT_LONGITUDE = "-73.9857"
DEFAULT_LATITUDE = "40.7484"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Weather info demo")
    parser.add_argument("--ip", default=DEFAULT_IP)
    parser.add_argument("--longitude", default=DEFAULT_LONGITUDE)
    parser.add_argument("--latitude", default=DEFAULT_LATITUDE)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    pixoo = Pixoo(args.ip)
    if not pixoo.connect():
        raise SystemExit("Failed to connect")

    pixoo.set_weather_location(args.longitude, args.latitude)
    info = pixoo.get_weather_info()
    print(info)


if __name__ == "__main__":
    main()
