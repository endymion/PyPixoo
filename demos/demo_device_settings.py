"""Exercise device settings like brightness and rotation."""

from __future__ import annotations

import argparse
import os
import time

from dotenv import load_dotenv

from pypixoo import Pixoo

load_dotenv()
DEFAULT_IP = os.environ.get("PIXOO_DEVICE_IP") or os.environ.get("PIXOO_IP") or "192.168.0.37"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run device settings demo")
    parser.add_argument("--ip", default=DEFAULT_IP)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    pixoo = Pixoo(args.ip)
    if not pixoo.connect():
        raise SystemExit("Failed to connect")

    pixoo.set_brightness(50)
    time.sleep(1)
    pixoo.set_screen_on(True)
    time.sleep(1)
    pixoo.set_screen_rotation(1)
    time.sleep(1)
    pixoo.set_mirror_mode(1)
    time.sleep(1)
    pixoo.set_time_24_flag(1)


if __name__ == "__main__":
    main()
