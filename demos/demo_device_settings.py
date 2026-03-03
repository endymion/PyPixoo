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

    original_rotation = 0
    original_mirror = 0
    try:
        conf = pixoo.get_all_conf()
        if isinstance(conf.get("ScreenRotationAngle"), int):
            original_rotation = int(conf["ScreenRotationAngle"])
        if isinstance(conf.get("MirrorMode"), int):
            original_mirror = int(conf["MirrorMode"])
    except Exception:
        # Keep safe defaults if config keys are unavailable on a firmware variant.
        pass

    try:
        pixoo.set_brightness(50)
        time.sleep(1)
        pixoo.set_screen_on(True)
        time.sleep(1)
        pixoo.set_screen_rotation(1)
        time.sleep(1)
        pixoo.set_mirror_mode(1)
        time.sleep(1)
        pixoo.set_time_24_flag(1)
    finally:
        # Prevent this demo from leaving the device in a rotated/mirrored state.
        pixoo.set_screen_rotation(original_rotation)
        pixoo.set_mirror_mode(original_mirror)
        pixoo.close()


if __name__ == "__main__":
    main()
