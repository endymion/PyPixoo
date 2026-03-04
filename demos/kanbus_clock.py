#!/usr/bin/env python3
"""Kanbus Clock: clock REPL plus recursive Kanbus events watcher.

This demo keeps the clock visible by default while providing a REPL for
`alert`, `warn`, and `info` commands. In parallel, it recursively discovers
`project/events` folders and watches for new JSON event files, which are queued
as transient `info` notices.
"""

from __future__ import annotations

import argparse
import asyncio
import atexit
import json
import os
import re
import shlex
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

import pixooclock as clock
from pypixoo import ClockScene, InfoScene, Pixoo, TextRow, TextStyle, header_layout
from pypixoo.color import parse_color
from pypixoo.font_render import measure_text as measure_scene_text
from pypixoo.info_dsl import BorderConfig
from pypixoo.raster import AsyncRasterClient, PixooFrameSink
from pypixoo.scene import QueueItem, ScenePlayer
from pypixoo.transitions import TransitionSpec

load_dotenv()
DEFAULT_IP = os.environ.get("PIXOO_DEVICE_IP") or os.environ.get("PIXOO_IP") or "192.168.0.37"
DEFAULT_HISTORY_FILE = Path(os.path.expanduser("~/.pypixoo/kanbus_clock_history"))
_FILENAME_TS_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)__"
)
_SHORT_SECONDS_RE = re.compile(r"^-s(\d+(?:\.\d+)?)$")
MIN_TS = datetime(1970, 1, 1, tzinfo=timezone.utc)

try:
    import readline
except ImportError:  # pragma: no cover - platform-dependent
    readline = None  # type: ignore[assignment]


@dataclass(frozen=True)
class AlertLevelDefaults:
    title: str
    fg: str
    bg: str


@dataclass(frozen=True)
class KanbusEvent:
    path: Path
    schema_version: int
    event_id: str
    issue_id: str
    event_type: str
    occurred_at: Optional[datetime]
    actor_id: str
    payload: dict[str, Any]
    repo_root: Optional[Path] = None


@dataclass(frozen=True)
class AutoNotice:
    header: str
    message: str
    level: str = "info"
    header_font: str = "bytesized"
    header_tight_padding: bool = True
    header_darker_steps: int = 2
    body_font: str = "bytesized"
    body_align: str = "left"
    body_center_vertical: bool = False
    body_line_vpad: int = 1
    center_first_line: bool = True
    first_line_darker_steps: int = 2
    line_darker_steps: dict[int, int] | None = None
    line_indent_px: dict[int, int] | None = None
    body_max_lines: int = 7
    body_min_row_height: int = 6
    body_max_row_height: int = 8


_LEVEL_DEFAULTS = {
    "alert": AlertLevelDefaults(title="ALERT", fg="dark.red8", bg="dark.red2"),
    "warn": AlertLevelDefaults(title="WARNING", fg="dark.yellow8", bg="dark.yellow2"),
    "info": AlertLevelDefaults(title="INFO", fg="dark.sand8", bg="dark.sand2"),
}


# --------------------------
# Formatting helpers
# --------------------------


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


def _darken_color(color: tuple[int, int, int], *, steps: int) -> tuple[int, int, int]:
    if steps <= 0:
        return color
    factor = 0.82**steps
    return tuple(max(0, min(255, int(c * factor))) for c in color)


def _truncate(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    if limit <= 1:
        return text[:limit]
    return text[: limit - 1] + "…"


def _normalize_space(text: str) -> str:
    return " ".join(text.split())


def _format_status_text(raw: Any) -> str:
    text = str(raw or "?").replace("_", " ").strip().upper()
    return text or "?"


def _text_width_px(text: str, *, font_key: str) -> int:
    if not text:
        return 0
    try:
        width, _ = measure_scene_text(text, font_key)
        return int(width)
    except Exception:
        # Conservative fallback for tests or renderer failures.
        return len(text) * 5


def _trim_to_pixel_width(text: str, *, max_width_px: int, font_key: str) -> str:
    compact = _normalize_space(text)
    if not compact:
        return ""
    if _text_width_px(compact, font_key=font_key) <= max_width_px:
        return compact
    ellipsis = "…"
    trimmed = compact
    while trimmed and _text_width_px(trimmed + ellipsis, font_key=font_key) > max_width_px:
        trimmed = trimmed[:-1]
    if not trimmed:
        return ellipsis
    return trimmed + ellipsis


def _prefix_for_indent_px(indent_px: int, *, font_key: str) -> str:
    if indent_px <= 0:
        return ""
    space_w = max(1, _text_width_px(" ", font_key=font_key))
    count = max(1, (int(indent_px) + space_w - 1) // space_w)
    return " " * count


def _wrap_text_lines(
    text: str, *, max_width_px: int, max_lines: int, font_key: str = "tiny5"
) -> list[str]:
    compact = _normalize_space(text.strip())
    if not compact or max_width_px <= 0 or max_lines <= 0:
        return []
    words = compact.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if _text_width_px(candidate, font_key=font_key) <= max_width_px:
            current = candidate
            continue
        if current:
            lines.append(current)
            if len(lines) >= max_lines:
                lines[-1] = _trim_to_pixel_width(lines[-1], max_width_px=max_width_px, font_key=font_key)
                return lines
            current = ""
        if _text_width_px(word, font_key=font_key) <= max_width_px:
            current = word
            continue
        lines.append(_trim_to_pixel_width(word, max_width_px=max_width_px, font_key=font_key))
        if len(lines) >= max_lines:
            return lines
    if current and len(lines) < max_lines:
        lines.append(current)
    return lines


def _extract_comment_text(payload: dict[str, Any]) -> str:
    preferred_keys = ("comment", "text", "message", "body", "content", "value")
    deny_tokens = ("kanbus-", "http://", "https://")

    def _score(key: str, value: str) -> tuple[int, int]:
        lowered_key = key.lower()
        score = 0
        if any(token in lowered_key for token in preferred_keys):
            score += 4
        if any(token in lowered_key for token in ("author", "actor", "id", "status", "type")):
            score -= 4
        text = value.strip()
        if len(text) >= 8:
            score += 2
        if " " in text:
            score += 1
        if any(token in text.lower() for token in deny_tokens):
            score -= 2
        return score, len(text)

    def _walk(node: Any, path: str = "") -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        if isinstance(node, dict):
            for k, v in node.items():
                child_path = f"{path}.{k}" if path else str(k)
                out.extend(_walk(v, child_path))
        elif isinstance(node, list):
            for idx, v in enumerate(node):
                out.extend(_walk(v, f"{path}[{idx}]"))
        elif isinstance(node, str):
            text = _normalize_space(node)
            if text:
                out.append((path, text))
        return out

    candidates = _walk(payload)
    if not candidates:
        return ""

    best_path, best_text = "", ""
    best_rank = (-999, -1)
    for path, text in candidates:
        rank = _score(path, text)
        if rank > best_rank:
            best_rank = rank
            best_path, best_text = path, text

    # Avoid returning obvious metadata-y strings unless nothing else exists.
    if best_rank[0] < 1:
        for path, text in candidates:
            lowered = path.lower()
            if any(k in lowered for k in ("author", "actor", "status", "type", "id")):
                continue
            if len(text) >= 8:
                return text
    return best_text


def _fetch_latest_issue_comment_text(issue_id: str, repo_root: Optional[Path] = None) -> str:
    if not issue_id:
        return ""
    try:
        proc = subprocess.run(
            ["kbs", "show", issue_id, "--json"],
            cwd=str(repo_root) if repo_root else None,
            capture_output=True,
            text=True,
            check=False,
            timeout=2.0,
        )
    except Exception:
        return ""
    if proc.returncode != 0 or not proc.stdout:
        return ""
    try:
        issue = json.loads(proc.stdout)
    except Exception:
        return ""
    comments = issue.get("comments")
    if not isinstance(comments, list):
        return ""
    for item in reversed(comments):
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            return _normalize_space(text)
    return ""


def _short_issue_id(issue_id: str) -> str:
    if issue_id.startswith("kanbus-"):
        tail = issue_id[len("kanbus-") :]
        head = tail.split("-", 1)[0]
        if head:
            return f"KBS {head[:6].upper()}"
    compact = issue_id.strip()
    if not compact:
        return "KBS ?"
    return _truncate(compact.upper(), 12)


def _message_scene(
    level: str,
    message: str,
    *,
    fg: tuple[int, int, int],
    bg: tuple[int, int, int],
    header_title: str | None = None,
    header_font: str = "bytesized",
    header_tight_padding: bool = True,
    header_darker_steps: int = 2,
    body_font: str = "bytesized",
    body_align: str = "left",
    body_center_vertical: bool = False,
    body_line_vpad: int = 1,
    center_first_line: bool = False,
    first_line_darker_steps: int = 0,
    line_darker_steps: dict[int, int] | None = None,
    line_indent_px: dict[int, int] | None = None,
    body_max_lines: int = 7,
    body_min_row_height: int = 6,
    body_max_row_height: int = 8,
) -> InfoScene:
    defaults = _LEVEL_DEFAULTS[level]
    resolved_header_title = header_title or defaults.title
    resolved_header_height = 12
    if header_tight_padding:
        try:
            _, header_h = measure_scene_text(resolved_header_title, header_font)
            # Tight mode keeps the header compact but leaves one extra pixel
            # below text before the bottom border line.
            resolved_header_height = max(4, int(header_h) + 3)
        except Exception:
            resolved_header_height = 11

    lines = [line.strip() for line in message.splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        lines = ["(empty)"]

    max_lines = max(1, int(body_max_lines))
    shown_lines = lines[:max_lines]
    if line_indent_px:
        adjusted: list[str] = []
        for idx, text_line in enumerate(shown_lines):
            indent = int(line_indent_px.get(idx, 0))
            if indent > 0:
                adjusted.append(_prefix_for_indent_px(indent, font_key=body_font) + text_line)
            else:
                adjusted.append(text_line)
        shown_lines = adjusted
    available_body_height = 64 - resolved_header_height
    line_vpad = max(0, int(body_line_vpad))
    measured_h = 0
    if shown_lines:
        for text_line in shown_lines:
            _, h = measure_scene_text(text_line, body_font)
            measured_h = max(measured_h, int(h))
    target_h = measured_h + (2 * line_vpad) if measured_h > 0 else 0
    min_h = max(1, int(body_min_row_height))
    max_h = max(min_h, int(body_max_row_height))
    row_height = max(min_h, min(max_h, available_body_height // max(1, len(shown_lines))))
    if target_h > 0 and (target_h * len(shown_lines)) <= available_body_height:
        row_height = target_h
    content_height = len(shown_lines) * row_height
    top_pad = max(0, (available_body_height - content_height) // 2) if body_center_vertical else 0
    body_row_align = "left" if body_align == "left" else "center"
    first_line_color = _darken_color(fg, steps=first_line_darker_steps)
    header_color = _darken_color(fg, steps=header_darker_steps)

    body_rows: list[TextRow] = []
    if top_pad > 0:
        body_rows.append(
            TextRow(
                height=top_pad,
                align=body_row_align,
                background_color=bg,
                style=TextStyle(font=body_font, color=fg),
                content="",
            )
        )
    for idx, line in enumerate(shown_lines):
        if idx == 0 and first_line_darker_steps > 0:
            row_color = first_line_color
        elif line_darker_steps and idx in line_darker_steps:
            row_color = _darken_color(fg, steps=int(line_darker_steps[idx]))
        else:
            row_color = fg
        row_align = "center" if idx == 0 and center_first_line else body_row_align
        body_rows.append(
            TextRow(
                height=row_height,
                align=row_align,
                background_color=bg,
                style=TextStyle(font=body_font, color=row_color),
                content=line,
            )
        )

    border_color = tuple(max(0, int(c * 0.55)) for c in header_color)
    layout = header_layout(
        title=resolved_header_title,
        font=header_font,
        height=resolved_header_height,
        title_color=header_color,
        background_color=bg,
        border=BorderConfig(enabled=True, thickness=1, color=border_color),
        body_rows=body_rows,
        body_background_color=bg,
    )
    return InfoScene(layout=layout, name=f"{level}-scene")


# --------------------------
# Event parsing/discovery
# --------------------------


def discover_event_dirs(root: Path) -> list[Path]:
    """Find all descendant directories that match */project/events."""
    base = root.expanduser().resolve()
    found: set[Path] = set()
    # Large workspace trees can contain many dependency/build folders.
    # Prune obvious heavy directories for responsive discovery.
    skip_names = {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        ".cache",
        ".mypy_cache",
        "dist",
        "build",
        ".next",
        ".idea",
        ".tox",
    }
    for dirpath, dirnames, _ in os.walk(base, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in skip_names]
        path = Path(dirpath)
        if path.name == "events" and path.parent.name == "project":
            found.add(path.resolve())
    return sorted(found)


def _parse_iso8601(raw: Any) -> Optional[datetime]:
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_filename_timestamp(path: Path) -> Optional[datetime]:
    match = _FILENAME_TS_RE.match(path.name)
    if not match:
        return None
    return _parse_iso8601(match.group("ts"))


def _repo_root_from_event_path(path: Path) -> Optional[Path]:
    """Return repo root for paths shaped like <repo>/project/events/<event>.json."""
    try:
        resolved = path.resolve()
    except Exception:
        resolved = path
    if resolved.parent.name == "events" and resolved.parent.parent.name == "project":
        return resolved.parent.parent.parent
    return None


def load_kanbus_event(path: Path) -> KanbusEvent:
    resolved_path = path.resolve()
    raw = json.loads(resolved_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"event file must contain an object: {resolved_path}")

    payload = raw.get("payload")
    if not isinstance(payload, dict):
        payload = {}

    event = KanbusEvent(
        path=resolved_path,
        schema_version=int(raw.get("schema_version", 0) or 0),
        event_id=str(raw.get("event_id") or ""),
        issue_id=str(raw.get("issue_id") or ""),
        event_type=str(raw.get("event_type") or "unknown"),
        occurred_at=_parse_iso8601(raw.get("occurred_at")),
        actor_id=str(raw.get("actor_id") or ""),
        payload=payload,
        repo_root=_repo_root_from_event_path(resolved_path),
    )
    return event


def event_timestamp(event: KanbusEvent) -> Optional[datetime]:
    return event.occurred_at or parse_filename_timestamp(event.path)


def latest_event_timestamp(folder: Path) -> tuple[int, Optional[str]]:
    files = sorted(p for p in folder.glob("*.json") if p.is_file())
    latest: Optional[datetime] = None
    for path in files:
        candidate = None
        try:
            candidate = event_timestamp(load_kanbus_event(path))
        except Exception:
            candidate = parse_filename_timestamp(path)
        if candidate is None:
            continue
        if latest is None or candidate > latest:
            latest = candidate
    if latest is None:
        return len(files), None
    return len(files), latest.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def summarize_event(event: KanbusEvent) -> AutoNotice:
    issue = _short_issue_id(event.issue_id)
    etype = event.event_type
    payload = event.payload

    if etype == "issue_created":
        issue_type = _truncate(str(payload.get("issue_type") or "issue"), 9).upper()
        status = _format_status_text(payload.get("status"))
        title = _truncate(str(payload.get("title") or "(no title)"), 16)
        lines = [f"{issue}", f"{issue_type} {status}", title]
        return AutoNotice(header="CREATED", message="\n".join(lines))

    if etype == "state_transition":
        from_status = _format_status_text(payload.get("from_status"))
        to_status = _format_status_text(payload.get("to_status"))
        lines = [f"{issue}", "FROM:", from_status, "TO:", to_status]
        return AutoNotice(
            header="TRANSITION",
            message="\n".join(lines),
            center_first_line=True,
            line_darker_steps={1: 1, 3: 1},
            line_indent_px={2: 4, 4: 4},
        )

    if etype == "comment_added":
        comment_text = _extract_comment_text(payload)
        if (not comment_text) or (len(comment_text) < 8) or (" " not in comment_text):
            repo_root = event.repo_root or _repo_root_from_event_path(event.path)
            comment_text = _fetch_latest_issue_comment_text(event.issue_id, repo_root)

        lines = [issue]
        if comment_text:
            lines.extend(
                _wrap_text_lines(comment_text, max_width_px=62, max_lines=6, font_key="bytesized")
            )
        if len(lines) == 1:
            author = _truncate(str(payload.get("comment_author") or event.actor_id or "?"), 14)
            lines.append(f"BY {author}")
        return AutoNotice(
            header="COMMENT",
            message="\n".join(lines),
            center_first_line=True,
        )

    lines = [f"{issue}", _truncate(f"EVENT {etype}", 18)]
    return AutoNotice(header=_truncate(etype.upper(), 12), message="\n".join(lines))


def scan_folder_for_new_events(
    folder: Path,
    known_files: set[str],
    failure_counts: dict[Path, int],
    *,
    max_failures: int = 5,
) -> list[KanbusEvent]:
    """Parse newly-seen event files from one folder.

    Existing baseline files are represented in `known_files` and skipped.
    Files that fail parsing are retried until `max_failures`, then skipped.
    """

    events: list[KanbusEvent] = []
    for path in sorted(p for p in folder.glob("*.json") if p.is_file()):
        if path.name in known_files:
            continue
        try:
            event = load_kanbus_event(path)
        except Exception as exc:
            attempts = failure_counts.get(path, 0) + 1
            failure_counts[path] = attempts
            if attempts >= max_failures:
                print(
                    f"watcher: skipping unreadable event after {attempts} attempts: {path.name} ({exc})"
                )
                known_files.add(path.name)
            continue

        known_files.add(path.name)
        failure_counts.pop(path, None)
        events.append(event)

    events.sort(
        key=lambda e: (
            event_timestamp(e) or MIN_TS,
            e.path.name,
        )
    )
    return events


def merge_new_event_dirs(root: Path, tracked: dict[Path, set[str]]) -> list[Path]:
    """Discover and add new event folders; return only newly-added dirs."""
    added: list[Path] = []
    for folder in discover_event_dirs(root):
        if folder in tracked:
            continue
        tracked[folder] = {p.name for p in folder.glob("*.json") if p.is_file()}
        added.append(folder)
    return added


def _watch_poll_step(
    *,
    root: Path,
    tracked: dict[Path, set[str]],
    failures: dict[Path, int],
    do_rescan: bool,
    max_failures: int,
) -> tuple[list[str], list[AutoNotice]]:
    """Run one synchronous watcher poll pass.

    This function intentionally runs in a worker thread so filesystem scans,
    JSON parsing, and optional subprocess fallbacks do not block the main
    asyncio loop that drives frame pacing.
    """

    logs: list[str] = []
    notices: list[AutoNotice] = []

    if do_rescan:
        added = merge_new_event_dirs(root, tracked)
        for folder in added:
            count, latest = latest_event_timestamp(folder)
            latest_text = latest or "none"
            logs.append(f"watcher: + {folder} ({count} files, latest={latest_text})")

    for folder in sorted(tracked.keys()):
        events = scan_folder_for_new_events(
            folder,
            tracked[folder],
            failures,
            max_failures=max_failures,
        )
        for event in events:
            notices.append(summarize_event(event))
            logs.append(f"watcher: event {event.event_type} {event.issue_id}")

    return logs, notices


# --------------------------
# Runtime loops
# --------------------------


def _enqueue_auto_notice(queue: asyncio.Queue[AutoNotice], notice: AutoNotice) -> None:
    if queue.full():
        try:
            queue.get_nowait()
            print("watcher: dropped oldest auto notice (queue full)")
        except asyncio.QueueEmpty:
            pass
    try:
        queue.put_nowait(notice)
    except asyncio.QueueFull:
        print("watcher: auto notice queue still full, dropping new event")


async def _wait_for_queue_capacity(
    player: ScenePlayer,
    *,
    threshold: int = 28,
    sleep_seconds: float = 0.05,
) -> None:
    while player.queue_depth >= threshold:
        await asyncio.sleep(sleep_seconds)


async def _enqueue_message_transition(
    *,
    player: ScenePlayer,
    clock_scene: ClockScene,
    level: str,
    message: str,
    seconds: float,
    transition_ms: int,
    fg: tuple[int, int, int],
    bg: tuple[int, int, int],
    header_title: str | None = None,
    header_font: str = "bytesized",
    header_tight_padding: bool = True,
    header_darker_steps: int = 2,
    body_font: str = "bytesized",
    body_align: str = "left",
    body_center_vertical: bool = False,
    body_line_vpad: int = 1,
    center_first_line: bool = False,
    first_line_darker_steps: int = 0,
    line_darker_steps: dict[int, int] | None = None,
    line_indent_px: dict[int, int] | None = None,
    body_max_lines: int = 7,
    body_min_row_height: int = 6,
    body_max_row_height: int = 8,
) -> None:
    scene = _message_scene(
        level,
        message,
        fg=fg,
        bg=bg,
        header_title=header_title,
        header_font=header_font,
        header_tight_padding=header_tight_padding,
        header_darker_steps=header_darker_steps,
        body_font=body_font,
        body_align=body_align,
        body_center_vertical=body_center_vertical,
        body_line_vpad=body_line_vpad,
        center_first_line=center_first_line,
        first_line_darker_steps=first_line_darker_steps,
        line_darker_steps=line_darker_steps,
        line_indent_px=line_indent_px,
        body_max_lines=body_max_lines,
        body_min_row_height=body_min_row_height,
        body_max_row_height=body_max_row_height,
    )
    hold_ms = int(max(0.1, seconds) * 1000)
    duration_ms = max(1, transition_ms)

    await _wait_for_queue_capacity(player)
    await player.enqueue(
        QueueItem(
            scene=scene,
            transition=TransitionSpec(kind="push_left", duration_ms=duration_ms),
            hold_ms=hold_ms,
        )
    )

    await _wait_for_queue_capacity(player)
    await player.enqueue(
        QueueItem(
            scene=clock_scene,
            transition=TransitionSpec(kind="push_right", duration_ms=duration_ms),
            hold_ms=0,
        )
    )


async def _watch_events_loop(
    *,
    root: Path,
    tracked: dict[Path, set[str]],
    notices: asyncio.Queue[AutoNotice],
    stop_event: asyncio.Event,
    poll_seconds: float,
    rescan_seconds: float,
    max_failures: int = 5,
) -> None:
    failures: dict[Path, int] = {}
    next_rescan = time.monotonic() + max(0.5, rescan_seconds)

    while not stop_event.is_set():
        now = time.monotonic()
        do_rescan = now >= next_rescan
        logs, discovered = await asyncio.to_thread(
            _watch_poll_step,
            root=root,
            tracked=tracked,
            failures=failures,
            do_rescan=do_rescan,
            max_failures=max_failures,
        )
        for line in logs:
            print(line)
        for notice in discovered:
            _enqueue_auto_notice(notices, notice)
        if do_rescan:
            next_rescan = now + max(0.5, rescan_seconds)

        await asyncio.sleep(max(0.1, poll_seconds))


async def _auto_notice_consumer(
    *,
    notices: asyncio.Queue[AutoNotice],
    player: ScenePlayer,
    clock_scene: ClockScene,
    stop_event: asyncio.Event,
    transition_ms: int,
    auto_info_seconds: float,
) -> None:
    while not stop_event.is_set():
        try:
            notice = await asyncio.wait_for(notices.get(), timeout=0.25)
        except asyncio.TimeoutError:
            continue
        fg, bg = _level_colors(notice.level)
        await _enqueue_message_transition(
            player=player,
            clock_scene=clock_scene,
            level=notice.level,
            message=notice.message,
            seconds=auto_info_seconds,
            transition_ms=transition_ms,
            fg=fg,
            bg=bg,
            header_title=notice.header,
            header_font=notice.header_font,
            header_tight_padding=notice.header_tight_padding,
            header_darker_steps=notice.header_darker_steps,
            body_font=notice.body_font,
            body_align=notice.body_align,
            body_center_vertical=notice.body_center_vertical,
            body_line_vpad=notice.body_line_vpad,
            center_first_line=notice.center_first_line,
            first_line_darker_steps=notice.first_line_darker_steps,
            line_darker_steps=notice.line_darker_steps,
            line_indent_px=notice.line_indent_px,
            body_max_lines=notice.body_max_lines,
            body_min_row_height=notice.body_min_row_height,
            body_max_row_height=notice.body_max_row_height,
        )


# --------------------------
# REPL helpers
# --------------------------


def _build_command_parser(name: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=name, add_help=False)
    parser.add_argument("--seconds", "-s", type=float, default=10.0)
    parser.add_argument("--color", default=None)
    parser.add_argument("--background-color", default=None)
    parser.add_argument("message", nargs="+")
    return parser


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


def _setup_readline_history(history_file: Path) -> None:
    if readline is None:
        return
    try:
        history_file.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"history: disabled (cannot create {history_file.parent}: {exc})")
        return

    try:
        readline.read_history_file(str(history_file))
    except FileNotFoundError:
        pass
    except OSError as exc:
        print(f"history: disabled (cannot read {history_file}: {exc})")
        return
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
    command_parsers = {
        "alert": _build_command_parser("alert"),
        "warn": _build_command_parser("warn"),
        "info": _build_command_parser("info"),
    }

    print("Kanbus clock ready. Type 'help' for commands.")
    while True:
        raw = await asyncio.to_thread(input, "kanbus-clock> ")
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

        await _enqueue_message_transition(
            player=player,
            clock_scene=clock_scene,
            level=command,
            message=message,
            seconds=seconds,
            transition_ms=transition_ms,
            fg=fg,
            bg=bg,
        )
        print(f"queued {command}: {seconds:.1f}s")


# --------------------------
# Main runtime
# --------------------------


def _startup_report(root: Path, event_dirs: list[Path]) -> dict[Path, set[str]]:
    tracked: dict[Path, set[str]] = {}
    print(f"kanbus-watch root: {root}")
    if not event_dirs:
        print("kanbus-watch: no project/events folders found")
        return tracked

    print(f"kanbus-watch: found {len(event_dirs)} event folder(s)")
    for folder in event_dirs:
        count, latest = latest_event_timestamp(folder)
        latest_text = latest or "none"
        print(f" - {folder} | files={count} latest={latest_text}")
        tracked[folder] = {p.name for p in folder.glob("*.json") if p.is_file()}
    return tracked


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Kanbus clock REPL + recursive events watcher")
    parser.add_argument("--ip", default=DEFAULT_IP)
    parser.add_argument("--fps", type=int, default=5)
    parser.add_argument("--transition-ms", type=int, default=1200)
    parser.add_argument("--root", default=".")
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    parser.add_argument("--rescan-seconds", type=float, default=10.0)
    parser.add_argument("--auto-info-seconds", type=float, default=5.0)
    parser.add_argument("--history-file", default=str(DEFAULT_HISTORY_FILE))
    return parser


async def run(
    *,
    ip: str,
    fps: int,
    transition_ms: int,
    root: Path,
    poll_seconds: float,
    rescan_seconds: float,
    auto_info_seconds: float,
    history_file: Path,
) -> None:
    print(f"kanbus-watch: scanning for project/events under {root}")
    discovered = discover_event_dirs(root)
    tracked = _startup_report(root, discovered)

    pixoo = Pixoo(ip)
    if not pixoo.connect():
        raise SystemExit(f"Failed to connect to Pixoo at {ip}")
    try:
        sink = PixooFrameSink(pixoo, reconnect=True)
        raster = AsyncRasterClient(sink)
        player = ScenePlayer(raster, fps=max(1, fps))

        style = clock._style_from_args(clock.build_parser(ip_default=ip).parse_args([]))
        clock_scene = ClockScene(render_frame=lambda ts: clock.render_clock_frame(ts, style), name="clock")
        notices: asyncio.Queue[AutoNotice] = asyncio.Queue(maxsize=64)
        stop_event = asyncio.Event()

        _setup_readline_history(history_file)

        await player.set_scene(clock_scene)
        runner = asyncio.create_task(player.run())
        watcher = asyncio.create_task(
            _watch_events_loop(
                root=root,
                tracked=tracked,
                notices=notices,
                stop_event=stop_event,
                poll_seconds=poll_seconds,
                rescan_seconds=rescan_seconds,
            )
        )
        consumer = asyncio.create_task(
            _auto_notice_consumer(
                notices=notices,
                player=player,
                clock_scene=clock_scene,
                stop_event=stop_event,
                transition_ms=transition_ms,
                auto_info_seconds=auto_info_seconds,
            )
        )

        try:
            await _run_repl(player=player, clock_scene=clock_scene, transition_ms=transition_ms)
        finally:
            stop_event.set()
            for task in (watcher, consumer):
                task.cancel()
            await asyncio.gather(watcher, consumer, return_exceptions=True)
            await player.stop()
            await runner
    finally:
        pixoo.close()


def main() -> None:
    args = build_parser().parse_args()
    try:
        asyncio.run(
            run(
                ip=args.ip,
                fps=max(1, args.fps),
                transition_ms=max(1, args.transition_ms),
                root=Path(args.root).expanduser().resolve(),
                poll_seconds=max(0.1, args.poll_seconds),
                rescan_seconds=max(0.5, args.rescan_seconds),
                auto_info_seconds=max(0.1, args.auto_info_seconds),
                history_file=Path(args.history_file).expanduser(),
            )
        )
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
