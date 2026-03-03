#!/usr/bin/env python3
"""Clock demo wrapper using shared discovery-first clock runtime.

Default mode is ``native_clock`` to keep behavior aligned with verified
device capabilities. Use ``--mode web_clock_experimental`` to run the
browser-rendered path.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pypixoo._clock_demo import MODE_NATIVE, build_clock_parser, run_clock_demo


def main() -> None:
    load_dotenv()
    ip_default = os.environ.get("PIXOO_DEVICE_IP") or os.environ.get("PIXOO_IP") or "192.168.0.37"
    parser = build_clock_parser(
        description="Clock demo (discovery-first: native_clock default, web_clock_experimental optional)",
        ip_default=ip_default,
        default_mode=MODE_NATIVE,
        default_fps=2,
        default_loop_seconds=2.0,
    )
    args = parser.parse_args()
    run_clock_demo(args, parser)


if __name__ == "__main__":
    main()
