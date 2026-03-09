#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _terminate_process(proc: subprocess.Popen[bytes], timeout_s: float = 10.0) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=timeout_s)
        return
    except subprocess.TimeoutExpired:
        pass
    proc.kill()
    proc.wait(timeout=timeout_s)


def _kill_existing_clock_processes() -> None:
    subprocess.run(["pkill", "-f", "demos/kanbus_clock.py"], check=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Restart kanbus_clock.py on a fixed interval")
    parser.add_argument("--restart-seconds", type=int, default=420, help="Restart interval in seconds (default: 420 = 7 min)")
    parser.add_argument("--python", default="./.venv/bin/python", help="Python executable for running kanbus_clock")
    parser.add_argument("--root", default="/Users/ryan.porter/Projects", help="kanbus_clock --root")
    parser.add_argument("--ip", default="192.168.0.37", help="kanbus_clock --ip")
    parser.add_argument("--theme", default="dark", choices=["auto", "dark", "light"], help="kanbus_clock --theme")
    parser.add_argument("--auto-info-seconds", type=float, default=30.0)
    parser.add_argument("--fps", type=int, default=5)
    parser.add_argument("--react-frame-workers", type=int, default=2)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--log-file", default="/tmp/kanbus_clock_supervisor.log")
    return parser


def launch_clock(args: argparse.Namespace, env: dict[str, str]) -> subprocess.Popen[bytes]:
    cmd = [
        args.python,
        "-u",
        "demos/kanbus_clock.py",
        "--root",
        args.root,
        "--ip",
        args.ip,
        "--theme",
        args.theme,
        "--auto-info-seconds",
        str(args.auto_info_seconds),
        "--fps",
        str(args.fps),
        "--react-frame-workers",
        str(args.react_frame_workers),
        "--no-repl",
    ]
    if args.debug:
        cmd.append("--debug")

    log_path = Path(args.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_handle = log_path.open("ab", buffering=0)
    log_handle.write(f"\n[{_utc_now()}] launching: {' '.join(cmd)}\n".encode("utf-8"))
    return subprocess.Popen(cmd, env=env, stdout=log_handle, stderr=log_handle, start_new_session=True)


def main() -> int:
    args = build_parser().parse_args()
    if args.restart_seconds <= 0:
        print("restart-seconds must be > 0", file=sys.stderr)
        return 2

    env = os.environ.copy()
    env["PYTHONPATH"] = "src"

    _kill_existing_clock_processes()

    stop = False

    def _handle_signal(signum: int, _frame: object) -> None:
        nonlocal stop
        stop = True
        print(f"[{_utc_now()}] supervisor received signal {signum}; stopping")

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    while not stop:
        proc = launch_clock(args, env)
        print(f"[{_utc_now()}] started kanbus_clock pid={proc.pid}")

        deadline = time.monotonic() + args.restart_seconds
        while not stop and time.monotonic() < deadline:
            rc = proc.poll()
            if rc is not None:
                print(f"[{_utc_now()}] kanbus_clock exited early rc={rc}; restarting in 2s")
                time.sleep(2)
                break
            time.sleep(1)
        else:
            print(f"[{_utc_now()}] restart interval reached; restarting pid={proc.pid}")

        _terminate_process(proc)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
