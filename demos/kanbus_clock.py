#!/usr/bin/env python3
"""Compatibility launcher for KanbusClock.

Kanbus clock has moved to the standalone repository:
  /Users/ryan.porter/Projects/KanbusClock
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    target_repo = Path("/Users/ryan.porter/Projects/KanbusClock")
    target_script = target_repo / "demos" / "kanbus_clock.py"

    if not target_script.is_file():
        print(
            "KanbusClock standalone app not found. Expected:\n"
            f"  {target_script}\n"
            "Create/clone the KanbusClock project first.",
            file=sys.stderr,
        )
        return 2

    print(
        "[PyPixoo shim] Kanbus clock moved to standalone KanbusClock. "
        "Launching new app...",
        file=sys.stderr,
    )

    env = os.environ.copy()
    src_path = str(target_repo / "src")
    env["PYTHONPATH"] = f"{src_path}:{env.get('PYTHONPATH', '')}" if env.get("PYTHONPATH") else src_path

    cmd = [sys.executable, str(target_script), "run", *sys.argv[1:]]
    return subprocess.call(cmd, cwd=str(target_repo), env=env)


if __name__ == "__main__":
    raise SystemExit(main())
