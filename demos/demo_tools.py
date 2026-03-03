"""Exercise device tool commands: timer, stopwatch, scoreboard, noise, buzzer."""

from __future__ import annotations

import argparse
import os
import time

from dotenv import load_dotenv

from pypixoo import Pixoo

load_dotenv()
DEFAULT_IP = os.environ.get("PIXOO_DEVICE_IP") or os.environ.get("PIXOO_IP") or "192.168.0.37"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Pixoo tool demos")
    parser.add_argument("--ip", default=DEFAULT_IP)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    pixoo = Pixoo(args.ip)
    if not pixoo.connect():
        raise SystemExit("Failed to connect")

    pixoo.set_countdown_timer((0, 10, 1))
    time.sleep(1)
    pixoo.set_stopwatch(1)
    time.sleep(1)
    pixoo.set_scoreboard((3, 5))
    time.sleep(1)
    pixoo.set_noise_status(1)
    time.sleep(1)
    pixoo.play_buzzer(300, 300, 1500)


if __name__ == "__main__":
    main()
