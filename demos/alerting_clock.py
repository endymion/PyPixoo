#!/usr/bin/env python3
"""Interactive alerting clock demo.

This demo keeps a clock scene visible by default, and accepts REPL commands to
show transient alert/info/warn scenes:

  alert "SOMETHING\nIS\nWRONG"
  alert --seconds 5 "lorem ipsum"
  alert -s5 "lorem ipsum"
  alert --color red-10 --background-color red-5 "lorem ipsum"
  warn "disk nearing full"
  info "backup completed"

Behavior:
- Message scene transitions in from the right (`push_left`),
- stays for configured seconds (default 10),
- transitions out to the right (`push_right`) back to the clock.
"""

from __future__ import annotations

import argparse
import asyncio
import atexit
import os
import re
from pathlib import Path
import shlex
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

import pixooclock as clock
from pypixoo import ClockScene, InfoScene, Pixoo, TextRow, TextStyle, header_layout
from pypixoo.color import parse_color
from pypixoo.info_dsl import BorderConfig
from pypixoo.raster import AsyncRasterClient, PixooFrameSink
from pypixoo.scene import QueueItem, ScenePlayer
from pypixoo.transitions import TransitionSpec

load_dotenv()
DEFAULT_IP = os.environ.get("PIXOO_DEVICE_IP") or os.environ.get("PIXOO_IP") or "192.168.0.37"


@dataclass(frozen=True)
class AlertLevelDefaults:
    title: str
    fg: str
    bg: str


_LEVEL_DEFAULTS = {
    "alert": AlertLevelDefaults(title="ALERT", fg="dark.red8", bg="dark.red2"),
    "warn": AlertLevelDefaults(title="WARNING", fg="dark.yellow8", bg="dark.yellow2"),
    "info": AlertLevelDefaults(title="INFO", fg="dark.sand8", bg="dark.sand2"),
}


def _safe_parse_color(token: str, *, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    try:
        return parse_color(token)
    except ValueError:
        return fallback


def _level_colors(level: str) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    defaults = _LEVEL_DEFAULTS[level]
    fg = _safe_parse_color(defaults.fg, fallback=(220, 220, 220))
    bg = _safe_parse_color(defaults.bg, fallback=(20, 20, 20))
    return fg, bg


def _message_scene(level: str, message: str, *, fg: tuple[int, int, int], bg: tuple[int, int, int]) -> InfoScene:
    defaults = _LEVEL_DEFAULTS[level]
    lines = [line.strip() for line in message.splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        lines = ["(empty)"]

    row_height = 12
    max_lines = 4
    shown_lines = lines[:max_lines]
    content_height = len(shown_lines) * row_height
    available_body_height = 64 - 12  # full canvas minus header row
    top_pad = max(0, (available_body_height - content_height) // 2)

    body_rows = []
    if top_pad > 0:
        body_rows.append(
            TextRow(
                height=top_pad,
                align="center",
                background_color=bg,
                style=TextStyle(font="tiny5", color=fg),
                content="",
            )
        )
    for line in shown_lines:
        body_rows.append(
            TextRow(
                height=row_height,
                align="center",
                background_color=bg,
                style=TextStyle(font="tiny5", color=fg),
                content=line,
            )
        )

    border_color = tuple(max(0, int(c * 0.55)) for c in fg)
    layout = header_layout(
        title=defaults.title,
        font="tiny5",
        height=12,
        title_color=fg,
        background_color=bg,
        border=BorderConfig(enabled=True, thickness=1, color=border_color),
        body_rows=body_rows,
        body_background_color=bg,
    )
    return InfoScene(layout=layout, name=f"{level}-scene")


def _build_command_parser(name: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=name, add_help=False)
    parser.add_argument("--seconds", "-s", type=float, default=10.0)
    parser.add_argument("--color", default=None)
    parser.add_argument("--background-color", default=None)
    parser.add_argument("message", nargs="+")
    return parser


_SHORT_SECONDS_RE = re.compile(r"^-s(\d+(?:\.\d+)?)$")
_DEFAULT_HISTORY_FILE = Path(os.path.expanduser("~/.pypixoo/alerting_clock_history"))

try:
    import readline
except ImportError:  # pragma: no cover - platform-dependent
    readline = None  # type: ignore[assignment]


def _normalize_command_tokens(tokens: list[str]) -> list[str]:
    out: list[str] = []
    for token in tokens:
        match = _SHORT_SECONDS_RE.match(token)
        if match:
            out.extend(["--seconds", match.group(1)])
        else:
            out.append(token)
    return out


def _help_text() -> str:
    return (
        "Commands:\n"
        "  alert [--seconds N|-sN] [--color TOKEN] [--background-color TOKEN] \"message\"\n"
        "  warn  [--seconds N|-sN] [--color TOKEN] [--background-color TOKEN] \"message\"\n"
        "  info  [--seconds N|-sN] [--color TOKEN] [--background-color TOKEN] \"message\"\n"
        "  help\n"
        "  quit | exit\n"
        "\n"
        "Examples:\n"
        "  alert \"SOMETHING\\nIS\\nWRONG\"\n"
        "  alert --seconds 5 \"lorem ipsum\"\n"
        "  alert -s5 \"lorem ipsum\"\n"
        "  alert --color red-10 --background-color red-5 \"lorem ipsum\"\n"
    )


def _setup_readline_history() -> None:
    if readline is None:
        return
    history_file = _DEFAULT_HISTORY_FILE
    history_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        readline.read_history_file(str(history_file))
    except FileNotFoundError:
        pass
    readline.set_history_length(2000)

    def _save_history() -> None:
        try:
            readline.write_history_file(str(history_file))
        except OSError:
            pass

    atexit.register(_save_history)


async def _run_repl(
    *,
    player: ScenePlayer,
    clock_scene: ClockScene,
    transition_ms: int,
) -> None:
    await player.set_scene(clock_scene)
    runner = asyncio.create_task(player.run())
    command_parsers = {
        "alert": _build_command_parser("alert"),
        "warn": _build_command_parser("warn"),
        "info": _build_command_parser("info"),
    }

    print("Alerting clock ready. Type 'help' for commands.")
    try:
        while True:
            raw = await asyncio.to_thread(input, "alert-clock> ")
            line = raw.strip()
            if not line:
                continue
            if line.lower() in {"quit", "exit"}:
                break
            if line.lower() == "help":
                print(_help_text())
                continue

            try:
                tokens = shlex.split(line)
            except ValueError as e:
                print(f"parse error: {e}")
                continue

            if not tokens:
                continue
            command = tokens[0].lower()
            if command not in command_parsers:
                print(f"unknown command: {command}")
                print("try: alert, warn, info, help, quit")
                continue

            parser = command_parsers[command]
            normalized = _normalize_command_tokens(tokens[1:])
            try:
                args = parser.parse_args(normalized)
            except SystemExit:
                print(f"invalid arguments for '{command}'")
                continue

            seconds = max(0.1, float(args.seconds))
            message = " ".join(args.message).replace("\\n", "\n")
            default_fg, default_bg = _level_colors(command)
            fg = _safe_parse_color(args.color, fallback=default_fg) if args.color else default_fg
            bg = (
                _safe_parse_color(args.background_color, fallback=default_bg)
                if args.background_color
                else default_bg
            )
            alert_scene = _message_scene(command, message, fg=fg, bg=bg)
            duration_ms = max(1, int(transition_ms))
            hold_ms = int(seconds * 1000)
            await player.enqueue(
                QueueItem(
                    scene=alert_scene,
                    transition=TransitionSpec(kind="push_left", duration_ms=duration_ms),
                    hold_ms=hold_ms,
                )
            )
            await player.enqueue(
                QueueItem(
                    scene=clock_scene,
                    transition=TransitionSpec(kind="push_right", duration_ms=duration_ms),
                    hold_ms=0,
                )
            )
            print(f"queued {command}: {seconds:.1f}s")
    finally:
        await player.stop()
        await runner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Alerting clock REPL demo")
    parser.add_argument("--ip", default=DEFAULT_IP)
    parser.add_argument("--fps", type=int, default=5)
    parser.add_argument("--transition-ms", type=int, default=1200)
    return parser


async def run(*, ip: str, fps: int, transition_ms: int) -> None:
    pixoo = Pixoo(ip)
    if not pixoo.connect():
        raise SystemExit(f"Failed to connect to Pixoo at {ip}")

    try:
        sink = PixooFrameSink(pixoo, reconnect=True)
        raster = AsyncRasterClient(sink)
        player = ScenePlayer(raster, fps=max(1, fps))

        style = clock._style_from_args(clock.build_parser(ip_default=ip).parse_args([]))
        clock_scene = ClockScene(render_frame=lambda ts: clock.render_clock_frame(ts, style), name="clock")
        _setup_readline_history()
        await _run_repl(player=player, clock_scene=clock_scene, transition_ms=transition_ms)
    finally:
        pixoo.close()


def main() -> None:
    args = build_parser().parse_args()
    try:
        asyncio.run(
            run(
                ip=args.ip,
                fps=args.fps,
                transition_ms=max(1, args.transition_ms),
            )
        )
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
