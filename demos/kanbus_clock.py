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
from pypixoo import (
    ClockScene,
    InfoLayout,
    InfoScene,
    Pixoo,
    TableCell,
    TableRow,
    TextRow,
    TextSpan,
    TextStyle,
    header_layout,
)
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
_ISSUE_KEY_RE = re.compile(r"\b([A-Za-z][A-Za-z0-9]*-\d+)\b")
_PROJECT_KEY_FULL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*-\d+$")
MIN_TS = datetime(1970, 1, 1, tzinfo=timezone.utc)
_DEBUG_KBS = False

try:
    import readline
except ImportError:  # pragma: no cover - platform-dependent
    readline = None  # type: ignore[assignment]


class KbsShowAmbiguous(RuntimeError):
    """Raised when kbs show reports an ambiguous identifier."""


def _debug_kbs(message: str) -> None:
    if _DEBUG_KBS:
        print(message)


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
class IssueSnapshot:
    issue_id: str
    id_prefix_upper: str
    issue_type_upper: str
    status_upper: str
    description: str
    title: str = ""
    parent_id: Optional[str] = None
    latest_comment_text: str = ""


@dataclass(frozen=True)
class ParentSnapshot:
    parent_id: str
    description: str
    title: str = ""


@dataclass(frozen=True)
class AutoNotice:
    header: str
    message: str
    level: str = "info"
    scene: Optional[InfoScene] = None
    header_font: str = "bytesized"
    header_tight_padding: bool = True
    header_darker_steps: int = 2
    body_font: str = "bytesized"
    body_align: str = "left"
    body_center_vertical: bool = False
    pin_first_line_top: bool = False
    body_line_vpad: int = 1
    center_first_line: bool = True
    center_line_indices: set[int] | None = None
    first_line_darker_steps: int = 2
    line_darker_steps: dict[int, int] | None = None
    line_indent_px: dict[int, int] | None = None
    line_spacer_before_px: dict[int, int] | None = None
    body_max_lines: int = 7
    body_min_row_height: int = 6
    body_max_row_height: int = 8


_LEVEL_DEFAULTS = {
    "alert": AlertLevelDefaults(title="ALERT", fg="dark.red8", bg="dark.red2"),
    "warn": AlertLevelDefaults(title="WARNING", fg="dark.yellow8", bg="dark.yellow2"),
    "info": AlertLevelDefaults(title="INFO", fg="dark.sand8", bg="dark.sand2"),
}

_ISSUE_TYPE_BANDS = {
    "TASK": "blue",
    "EPIC": "indigo",
    "STORY": "yellow",
    "BUG": "red",
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


def _canonical_issue_type(issue_type_upper: str) -> str:
    text = _normalize_space(str(issue_type_upper or "ISSUE")).upper()
    for token in ("TASK", "EPIC", "STORY", "BUG"):
        if token in text:
            return token
    return "ISSUE"


def _issue_type_card_colors(
    issue_type_upper: str,
) -> tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]:
    canonical = _canonical_issue_type(issue_type_upper)
    band = _ISSUE_TYPE_BANDS.get(canonical, "sand")
    header_fg = _safe_parse_color(f"dark.{band}8", fallback=(145, 145, 145))
    main_fg = _safe_parse_color(f"dark.{band}9", fallback=(180, 180, 180))
    top_dim_fg = _darken_color(header_fg, steps=1)
    bg = _safe_parse_color(f"dark.{band}2", fallback=(8, 8, 8))
    return header_fg, main_fg, top_dim_fg, bg


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


def _run_kbs_show_json(
    issue_id: str, kbs_root: Optional[Path] = None, project_root: Optional[Path] = None
) -> Optional[dict[str, Any]]:
    if not issue_id:
        return None
    cwd = str(kbs_root) if kbs_root else None
    project_hint = f" project_root={project_root}" if project_root else ""
    _debug_kbs(f"kbs: show {issue_id} --json (cwd={cwd or 'default'}){project_hint}")
    command = ["kbs", "show", issue_id, "--json"]
    if project_root is not None:
        command.extend(["--project-root", str(project_root)])
    try:
        proc = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=2.0,
        )
    except Exception:
        return None
    _debug_kbs(f"kbs: exit={proc.returncode}")
    stdout_text = getattr(proc, "stdout", "") or ""
    stderr_text = getattr(proc, "stderr", "") or ""
    if stdout_text:
        _debug_kbs(f"kbs stdout:\n{stdout_text.strip()}")
    if stderr_text:
        _debug_kbs(f"kbs stderr:\n{stderr_text.strip()}")
    if proc.returncode != 0:
        if "ambiguous identifier" in stderr_text.lower():
            raise KbsShowAmbiguous("ambiguous identifier")
        return None
    if not stdout_text:
        return None
    try:
        parsed = json.loads(stdout_text)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _issue_id_prefix_upper(issue_id: str) -> str:
    compact = str(issue_id or "").strip()
    if not compact:
        return "ISSUE"
    prefix = compact.split("-", 1)[0] or compact
    return prefix.upper()


def _extract_issue_key_pattern(*texts: str) -> str:
    for text in texts:
        if not text:
            continue
        for match in _ISSUE_KEY_RE.finditer(text):
            candidate = match.group(1)
            # Ignore keys that are just the tail of an internal kanbus id,
            # e.g. "kanbus-abcdef12-1111" -> "abcdef12-1111".
            if f"kanbus-{candidate}".lower() in text.lower():
                continue
            return candidate
    return ""


def _collect_string_values(node: Any) -> list[str]:
    out: list[str] = []
    if isinstance(node, dict):
        for value in node.values():
            out.extend(_collect_string_values(value))
    elif isinstance(node, list):
        for value in node:
            out.extend(_collect_string_values(value))
    elif isinstance(node, str):
        value = node.strip()
        if value:
            out.append(value)
    return out


def _pick_issue_key_for_prefix(
    issue: dict[str, Any], requested_issue_id: str, payload: Optional[dict[str, Any]] = None
) -> str:
    """Pick the most human-meaningful issue key for header prefix derivation."""
    issue_id_value = str(issue.get("id") or "").strip()

    def _is_explicit_project_key(value: str) -> bool:
        candidate = value.strip()
        if not candidate:
            return False
        if not _PROJECT_KEY_FULL_RE.fullmatch(candidate):
            return False
        if issue_id_value and issue_id_value.startswith(f"{candidate}-"):
            return False
        return True

    if requested_issue_id and _is_explicit_project_key(requested_issue_id):
        return requested_issue_id.strip()

    if payload:
        for key in ("issue_key", "key", "external_id", "externalId", "display_id", "displayId"):
            value = payload.get(key)
            if isinstance(value, str) and _is_explicit_project_key(value):
                return value.strip()

    candidates: list[str] = []
    key_fields = (
        "key",
        "issue_key",
        "external_id",
        "externalId",
        "display_id",
        "displayId",
        "short_id",
        "shortId",
        "identifier",
        "ticket",
        "ticket_id",
        "jira_key",
        "jiraKey",
        "source_key",
        "sourceKey",
        "reference",
    )

    for key in key_fields:
        value = issue.get(key)
        if isinstance(value, str) and value.strip():
            candidates.append(value.strip())
    custom = issue.get("custom")
    if isinstance(custom, dict):
        for key in key_fields:
            value = custom.get(key)
            if isinstance(value, str) and value.strip():
                candidates.append(value.strip())
    if isinstance(payload, dict):
        for key in key_fields + ("issue_id", "id"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                candidates.append(value.strip())
        payload_custom = payload.get("custom")
        if isinstance(payload_custom, dict):
            for key in key_fields:
                value = payload_custom.get(key)
                if isinstance(value, str) and value.strip():
                    candidates.append(value.strip())

    text_key = _extract_issue_key_pattern(
        _normalize_space(str(issue.get("title") or "")),
        _normalize_space(str(issue.get("description") or "")),
        *(_collect_string_values(issue) if isinstance(issue, dict) else []),
        *(_collect_string_values(payload) if isinstance(payload, dict) else []),
    )
    if text_key:
        candidates.insert(0, text_key)

    # Give explicit, human-facing keys precedence when present.
    for key in ("external_id", "externalId", "key", "issue_key", "reference"):
        value = issue.get(key)
        if isinstance(value, str) and value.strip():
            candidates.insert(0, value.strip())
    if issue_id_value:
        issue_prefix = issue_id_value.split("-", 1)[0]
        if issue_prefix and issue_prefix[:1].isalpha() and not issue_id_value.lower().startswith("kanbus-"):
            candidates.insert(0, issue_id_value)
        else:
            candidates.append(issue_id_value)
    if requested_issue_id:
        candidates.append(requested_issue_id.strip())

    requested = requested_issue_id.strip()

    normalized: list[str] = []

    def _push(value: str) -> None:
        compact = value.strip()
        if not compact:
            return
        if compact not in normalized:
            normalized.append(compact)
        embedded = _extract_issue_key_pattern(compact)
        if embedded and embedded not in normalized:
            normalized.append(embedded)

    for candidate in candidates:
        _push(candidate)
    if requested:
        _push(requested)

    def _score(value: str) -> int:
        text = value.strip()
        if not text:
            return -100
        if _PROJECT_KEY_FULL_RE.fullmatch(text):
            return 100
        if text.isdigit():
            return 0
        if "-" in text and text.split("-", 1)[0][:1].isalpha():
            return 80
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", text):
            return 60
        return 30

    best = max(normalized, key=_score, default="")
    if best:
        return best
    return requested_issue_id


def _extract_latest_comment_text(issue: dict[str, Any]) -> str:
    comments = issue.get("comments")
    if not isinstance(comments, list):
        return ""
    for item in reversed(comments):
        if not isinstance(item, dict):
            continue
        text = _normalize_space(str(item.get("text") or ""))
        if text:
            return text
    return ""


def _extract_parent_id(issue: dict[str, Any]) -> Optional[str]:
    for key in ("parent", "parent_id", "parent_issue_id"):
        value = issue.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            for nested_key in ("id", "issue_id", "key", "external_id"):
                nested = value.get(nested_key)
                if isinstance(nested, str) and nested.strip():
                    return nested.strip()
    return None


def _fetch_issue_snapshot(
    issue_id: str,
    kbs_root: Optional[Path] = None,
    payload: Optional[dict[str, Any]] = None,
    project_root: Optional[Path] = None,
) -> Optional[IssueSnapshot]:
    issue = _run_kbs_show_json(issue_id, kbs_root, project_root)
    if issue is None:
        return None
    issue_id_value = str(issue.get("id") or "").strip()
    issue_prefix = issue_id_value.split("-", 1)[0] if issue_id_value else ""
    if issue_prefix and issue_prefix[:1].isalpha() and not issue_id_value.lower().startswith("kanbus-"):
        issue_key_for_prefix = issue_id_value
    else:
        issue_key_for_prefix = _pick_issue_key_for_prefix(issue, issue_id, payload)
    issue_type = _normalize_space(str(issue.get("type") or issue.get("issue_type") or "ISSUE")).upper()
    status = _format_status_text(issue.get("status") or "OPEN")
    title = _normalize_space(str(issue.get("title") or issue.get("name") or ""))
    description = _normalize_space(str(issue.get("description") or title or ""))
    parent_id = _extract_parent_id(issue)
    return IssueSnapshot(
        issue_id=str(issue.get("id") or issue_id),
        id_prefix_upper=_issue_id_prefix_upper(issue_key_for_prefix),
        issue_type_upper=issue_type or "ISSUE",
        status_upper=status or "OPEN",
        description=description,
        title=title,
        parent_id=parent_id,
        latest_comment_text=_extract_latest_comment_text(issue),
    )


def _fetch_parent_snapshot(
    parent_id: str, kbs_root: Optional[Path] = None, project_root: Optional[Path] = None
) -> Optional[ParentSnapshot]:
    issue = _run_kbs_show_json(parent_id, kbs_root, project_root)
    if issue is None:
        return None
    title = _normalize_space(str(issue.get("title") or issue.get("name") or ""))
    return ParentSnapshot(
        parent_id=str(issue.get("id") or parent_id),
        description=_normalize_space(str(issue.get("description") or title or "")),
        title=title,
    )


def _issue_meta_header_parts(snapshot: IssueSnapshot) -> tuple[str, str, str]:
    prefix = _normalize_space(snapshot.id_prefix_upper or "ISSUE")
    issue_type = _normalize_space(snapshot.issue_type_upper or "ISSUE").upper()
    status = _normalize_space(str(snapshot.status_upper or "OPEN")).upper()
    return (prefix, issue_type, status)


def _event_prefix_override(event_issue_id: str) -> str:
    """Prefer the event issue id for header prefix when it is meaningful."""
    text = (event_issue_id or "").strip()
    if not text:
        return ""
    if text.lower().startswith("kanbus-"):
        return ""
    candidate = _issue_id_prefix_upper(text)
    # Never use a numeric-only prefix like "1234".
    if candidate.isdigit():
        return ""
    return candidate


def _payload_prefix_override(payload: dict[str, Any]) -> str:
    """Extract an issue-key prefix from event payload when available."""
    key_fields = (
        "key",
        "issue_key",
        "external_id",
        "externalId",
        "display_id",
        "displayId",
        "reference",
        "ticket",
        "ticket_id",
        "jira_key",
        "jiraKey",
        "source_key",
        "sourceKey",
        "project_key",
        "projectKey",
        "prefix",
        "issue_prefix",
        "issuePrefix",
    )
    for key in key_fields:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            prefix = _issue_id_prefix_upper(value)
            if prefix and not prefix.isdigit() and prefix != "KANBUS":
                return prefix
    payload_custom = payload.get("custom")
    if isinstance(payload_custom, dict):
        for key in key_fields:
            value = payload_custom.get(key)
            if isinstance(value, str) and value.strip():
                prefix = _issue_id_prefix_upper(value)
                if prefix and not prefix.isdigit() and prefix != "KANBUS":
                    return prefix
    pattern_key = _extract_issue_key_pattern(*_collect_string_values(payload))
    if pattern_key:
        prefix = _issue_id_prefix_upper(pattern_key)
        if prefix and not prefix.isdigit() and prefix != "KANBUS":
            return prefix
    # Compose from common split fields.
    project_key = payload.get("project_key") or payload.get("projectKey") or payload.get("project")
    issue_num = payload.get("issue_number") or payload.get("issueNumber") or payload.get("number")
    if isinstance(project_key, str) and project_key.strip() and issue_num is not None:
        composed = f"{project_key.strip()}-{issue_num}"
        prefix = _issue_id_prefix_upper(composed)
        if prefix and not prefix.isdigit() and prefix != "KANBUS":
            return prefix
    return ""


def _wrap_desc(text: str, *, max_lines: int) -> list[str]:
    wrapped = _wrap_text_lines(text, max_width_px=62, max_lines=max_lines, font_key="bytesized")
    if wrapped:
        return wrapped
    return ["(no description)"]


def _fixed_rows(lines: list[str], count: int) -> list[str]:
    out = list(lines[:count])
    while len(out) < count:
        out.append("")
    return out


def _build_card_scene_from_sections(
    *,
    issue_type_upper: str,
    header_parts: tuple[str, str, str],
    top_lines: list[str],
    bottom_lines: list[str],
    show_middle_divider: bool,
    name: str,
) -> InfoScene:
    header_fg, main_fg, top_dim_fg, bg = _issue_type_card_colors(issue_type_upper)
    header_color = header_fg
    border_color = tuple(max(0, int(c * 0.55)) for c in header_fg)
    row_font = "bytesized"
    row_height = 7

    header_font = "bytesized"
    header_metrics = [measure_scene_text(part, header_font)[1] for part in header_parts if part]
    header_height = max(4, int(max(header_metrics) if header_metrics else 5) + 3)

    def _header_spans(text: str) -> list[TextSpan]:
        words = [token for token in _normalize_space(text).split(" ") if token]
        spans: list[TextSpan] = []
        for idx, word in enumerate(words):
            spans.append(TextSpan(text=word, font=header_font, color=header_color))
            if idx < len(words) - 1:
                spans.append(TextSpan(text="", advance_px=2))
        return spans

    header_spans: list[TextSpan] = []
    for part in [p for p in header_parts if p]:
        if header_spans:
            header_spans.append(TextSpan(text="", advance_px=3))
        header_spans.extend(_header_spans(part))
    rows: list[Any] = [
        TextRow(
            height=header_height,
            align="left",
            background_color=bg,
            border=BorderConfig(enabled=True, thickness=1, color=border_color),
            style=TextStyle(font=header_font, color=header_color),
            content=header_spans,
        )
    ]

    for line in top_lines:
        rows.append(
            TextRow(
                height=row_height,
                align="left",
                background_color=bg,
                style=TextStyle(font=row_font, color=top_dim_fg),
                content=line,
            )
        )
    if show_middle_divider:
        rows.append(
            TextRow(
                height=1,
                align="left",
                background_color=bg,
                border=BorderConfig(enabled=True, thickness=1, color=border_color),
                style=TextStyle(font=row_font, color=header_fg),
                content="",
            )
        )
    for line in bottom_lines:
        rows.append(
            TextRow(
                height=row_height,
                align="left",
                background_color=bg,
                style=TextStyle(font=row_font, color=main_fg),
                content=line,
            )
        )

    return InfoScene(layout=InfoLayout(rows=rows, background_color=bg), name=name)


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
    pin_first_line_top: bool = False,
    body_line_vpad: int = 1,
    center_first_line: bool = False,
    center_line_indices: set[int] | None = None,
    first_line_darker_steps: int = 0,
    line_darker_steps: dict[int, int] | None = None,
    line_indent_px: dict[int, int] | None = None,
    line_spacer_before_px: dict[int, int] | None = None,
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
    pin_first = bool(pin_first_line_top and body_center_vertical and len(shown_lines) > 1)
    pinned_rows = 1 if pin_first else 0
    pinned_height = pinned_rows * row_height
    remaining_lines = max(0, len(shown_lines) - pinned_rows)
    remaining_height = remaining_lines * row_height
    remaining_space = max(0, available_body_height - pinned_height)
    top_pad = max(0, (remaining_space - remaining_height) // 2) if body_center_vertical else 0
    body_row_align = "left" if body_align == "left" else "center"
    first_line_color = _darken_color(fg, steps=first_line_darker_steps)
    header_color = _darken_color(fg, steps=header_darker_steps)

    centered_indices = set(center_line_indices or ())
    spacer_before = dict(line_spacer_before_px or {})
    body_rows: list[TextRow] = []
    if pin_first:
        first_line = shown_lines[0]
        if first_line_darker_steps > 0:
            row_color = first_line_color
        elif line_darker_steps and 0 in line_darker_steps:
            row_color = _darken_color(fg, steps=int(line_darker_steps[0]))
        else:
            row_color = fg
        row_align = "center" if (center_first_line or (0 in centered_indices)) else body_row_align
        body_rows.append(
            TextRow(
                height=row_height,
                align=row_align,
                background_color=bg,
                style=TextStyle(font=body_font, color=row_color),
                content=first_line,
            )
        )
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
    start_idx = 1 if pin_first else 0
    for idx in range(start_idx, len(shown_lines)):
        line = shown_lines[idx]
        spacer_px = max(0, int(spacer_before.get(idx, 0)))
        if spacer_px > 0:
            body_rows.append(
                TextRow(
                    height=spacer_px,
                    align=body_row_align,
                    background_color=bg,
                    style=TextStyle(font=body_font, color=fg),
                    content="",
                )
            )
        if idx == 0 and first_line_darker_steps > 0:
            row_color = first_line_color
        elif line_darker_steps and idx in line_darker_steps:
            row_color = _darken_color(fg, steps=int(line_darker_steps[idx]))
        else:
            row_color = fg
        row_align = "center" if ((idx == 0 and center_first_line) or (idx in centered_indices)) else body_row_align
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


def summarize_event(event: KanbusEvent, kbs_root: Optional[Path] = None) -> Optional[AutoNotice]:
    etype = event.event_type
    payload = event.payload
    payload_prefix = _payload_prefix_override(payload)
    project_root = event.repo_root

    snapshot = _fetch_issue_snapshot(event.issue_id, kbs_root, payload, project_root)
    payload_type = _normalize_space(str(payload.get("issue_type") or payload.get("type") or "ISSUE")).upper()
    payload_status = _format_status_text(payload.get("status") or "OPEN")
    payload_description = _normalize_space(
        str(payload.get("description") or payload.get("issue_description") or payload.get("title") or "")
    )
    if snapshot is None:
        snapshot = IssueSnapshot(
            issue_id=event.issue_id,
            id_prefix_upper=payload_prefix or _issue_id_prefix_upper(event.issue_id),
            issue_type_upper=payload_type or "ISSUE",
            status_upper=payload_status or "OPEN",
            description=payload_description,
            title="",
            parent_id=None,
            latest_comment_text="",
        )
    elif not snapshot.description and payload_description:
        snapshot = IssueSnapshot(
            issue_id=snapshot.issue_id,
            id_prefix_upper=snapshot.id_prefix_upper,
            issue_type_upper=snapshot.issue_type_upper or payload_type or "ISSUE",
            status_upper=snapshot.status_upper or payload_status or "OPEN",
            description=payload_description,
            title=snapshot.title,
            parent_id=snapshot.parent_id,
            latest_comment_text=snapshot.latest_comment_text,
        )
    event_prefix = payload_prefix or _event_prefix_override(event.issue_id)
    if event_prefix and snapshot.id_prefix_upper.isdigit():
        snapshot = IssueSnapshot(
            issue_id=snapshot.issue_id,
            id_prefix_upper=event_prefix,
            issue_type_upper=snapshot.issue_type_upper,
            status_upper=snapshot.status_upper,
            description=snapshot.description,
            title=snapshot.title,
            parent_id=snapshot.parent_id,
            latest_comment_text=snapshot.latest_comment_text,
        )
    header_parts = _issue_meta_header_parts(snapshot)
    header_text = " ".join(header_parts)

    if etype == "issue_created":
        parent_snapshot = (
            _fetch_parent_snapshot(snapshot.parent_id, kbs_root, project_root)
            if snapshot.parent_id
            else None
        )
        if parent_snapshot is not None:
            top_lines = _fixed_rows(_wrap_desc(parent_snapshot.description, max_lines=3), 3)
            bottom_lines = _fixed_rows(_wrap_desc(snapshot.description, max_lines=4), 4)
            show_middle_divider = True
        else:
            top_lines = []
            bottom_lines = _fixed_rows(_wrap_desc(snapshot.description, max_lines=7), 7)
            show_middle_divider = False
        scene = _build_card_scene_from_sections(
            issue_type_upper=snapshot.issue_type_upper,
            header_parts=header_parts,
            top_lines=top_lines,
            bottom_lines=bottom_lines,
            show_middle_divider=show_middle_divider,
            name="created-scene",
        )
        return AutoNotice(
            header=header_text,
            message="\n".join(top_lines + bottom_lines),
            scene=scene,
        )

    if etype == "state_transition":
        parent_snapshot = (
            _fetch_parent_snapshot(snapshot.parent_id, kbs_root, project_root)
            if snapshot.parent_id
            else None
        )
        if parent_snapshot is not None:
            top_lines = _fixed_rows(_wrap_desc(parent_snapshot.description, max_lines=3), 3)
            bottom_lines = _fixed_rows(_wrap_desc(snapshot.description, max_lines=4), 4)
            show_middle_divider = True
        else:
            top_lines = []
            bottom_lines = _fixed_rows(_wrap_desc(snapshot.description, max_lines=7), 7)
            show_middle_divider = False
        scene = _build_card_scene_from_sections(
            issue_type_upper=snapshot.issue_type_upper,
            header_parts=header_parts,
            top_lines=top_lines,
            bottom_lines=bottom_lines,
            show_middle_divider=show_middle_divider,
            name="transition-scene",
        )
        return AutoNotice(
            header=header_text,
            message="\n".join(top_lines + bottom_lines),
            scene=scene,
        )

    if etype == "comment_added":
        comment_text = _extract_comment_text(payload)
        if (not comment_text) or (len(comment_text) < 8) or (" " not in comment_text):
            comment_text = snapshot.latest_comment_text

        issue_lines = _fixed_rows(_wrap_desc(snapshot.description, max_lines=2), 2)
        comment_lines = _fixed_rows(_wrap_desc(comment_text, max_lines=3), 3)
        scene = _build_card_scene_from_sections(
            issue_type_upper=snapshot.issue_type_upper,
            header_parts=header_parts,
            top_lines=issue_lines,
            bottom_lines=comment_lines,
            show_middle_divider=False,
            name="comment-scene",
        )
        return AutoNotice(
            header=header_text,
            message="\n".join(issue_lines + comment_lines),
            scene=scene,
        )

    fallback_line = _trim_to_pixel_width(f"EVENT {etype.upper()}", max_width_px=62, font_key="bytesized")
    scene = _build_card_scene_from_sections(
        issue_type_upper=snapshot.issue_type_upper,
        header_parts=header_parts,
        top_lines=[],
        bottom_lines=_fixed_rows([fallback_line], 5),
        show_middle_divider=False,
        name="event-scene",
    )
    return AutoNotice(header=header_text, message=fallback_line, scene=scene)


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
    kbs_root: Optional[Path],
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
            try:
                notice = summarize_event(event, kbs_root)
            except KbsShowAmbiguous:
                logs.append(
                    f"watcher: ambiguous identifier for {event.issue_id}, skipping"
                )
                continue
            if notice is None:
                logs.append(f"watcher: skipped event {event.event_type} {event.issue_id}")
                continue
            notices.append(notice)
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
    scene: Optional[InfoScene] = None,
    header_title: str | None = None,
    header_font: str = "bytesized",
    header_tight_padding: bool = True,
    header_darker_steps: int = 2,
    body_font: str = "bytesized",
    body_align: str = "left",
    body_center_vertical: bool = False,
    pin_first_line_top: bool = False,
    body_line_vpad: int = 1,
    center_first_line: bool = False,
    center_line_indices: set[int] | None = None,
    first_line_darker_steps: int = 0,
    line_darker_steps: dict[int, int] | None = None,
    line_indent_px: dict[int, int] | None = None,
    line_spacer_before_px: dict[int, int] | None = None,
    body_max_lines: int = 7,
    body_min_row_height: int = 6,
    body_max_row_height: int = 8,
) -> None:
    resolved_scene = scene
    if resolved_scene is None:
        resolved_scene = _message_scene(
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
            pin_first_line_top=pin_first_line_top,
            body_line_vpad=body_line_vpad,
            center_first_line=center_first_line,
            center_line_indices=center_line_indices,
            first_line_darker_steps=first_line_darker_steps,
            line_darker_steps=line_darker_steps,
            line_indent_px=line_indent_px,
            line_spacer_before_px=line_spacer_before_px,
            body_max_lines=body_max_lines,
            body_min_row_height=body_min_row_height,
            body_max_row_height=body_max_row_height,
        )
    hold_ms = int(max(0.1, seconds) * 1000)
    duration_ms = max(1, transition_ms)

    await _wait_for_queue_capacity(player)
    await player.enqueue(
        QueueItem(
            scene=resolved_scene,
            transition=TransitionSpec(kind="push_left", duration_ms=duration_ms),
            hold_ms=hold_ms,
        )
    )

    await _wait_for_queue_capacity(player)
    await player.enqueue(
        QueueItem(
            scene=clock_scene,
            transition=TransitionSpec(kind="push_left", duration_ms=duration_ms),
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
    kbs_root: Optional[Path] = None,
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
            kbs_root=kbs_root,
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
            scene=notice.scene,
            header_title=notice.header,
            header_font=notice.header_font,
            header_tight_padding=notice.header_tight_padding,
            header_darker_steps=notice.header_darker_steps,
            body_font=notice.body_font,
            body_align=notice.body_align,
            body_center_vertical=notice.body_center_vertical,
            pin_first_line_top=notice.pin_first_line_top,
            body_line_vpad=notice.body_line_vpad,
            center_first_line=notice.center_first_line,
            center_line_indices=notice.center_line_indices,
            first_line_darker_steps=notice.first_line_darker_steps,
            line_darker_steps=notice.line_darker_steps,
            line_indent_px=notice.line_indent_px,
            line_spacer_before_px=notice.line_spacer_before_px,
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
    parser.add_argument("--auto-info-seconds", type=float, default=30.0)
    parser.add_argument("--history-file", default=str(DEFAULT_HISTORY_FILE))
    parser.add_argument("--debug", action="store_true", help="print kbs commands and responses")
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
    debug: bool,
) -> None:
    global _DEBUG_KBS
    _DEBUG_KBS = debug
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
                kbs_root=root,
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
                debug=bool(args.debug),
            )
        )
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
