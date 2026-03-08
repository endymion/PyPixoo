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
from collections import OrderedDict, deque
import concurrent.futures
from concurrent.futures import Future, ThreadPoolExecutor
import io
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urlencode
from urllib.parse import parse_qsl
from urllib.parse import urlsplit
from urllib.parse import urlunsplit

from dotenv import load_dotenv
from PIL import Image

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
from pypixoo.buffer import Buffer
from pypixoo.raster import AsyncRasterClient, PixooFrameSink
from pypixoo.scene import LayerNode, QueueItem, RenderContext, ScenePlayer
from pypixoo.transitions import TransitionSpec

load_dotenv()
DEFAULT_IP = os.environ.get("PIXOO_DEVICE_IP") or os.environ.get("PIXOO_IP") or "192.168.0.37"
DEFAULT_HISTORY_FILE = Path(os.path.expanduser("~/.pypixoo/kanbus_clock_history"))
DEFAULT_RUNTIME_ASSETS = (
    Path(__file__).resolve().parents[1] / "storybook-app" / "dist-pixoo-runtime"
)
DEFAULT_THEME_CHECK_SECONDS = 5.0
_FILENAME_TS_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)__"
)
_SHORT_SECONDS_RE = re.compile(r"^-s(\d+(?:\.\d+)?)$")
_ISSUE_KEY_RE = re.compile(r"\b([A-Za-z][A-Za-z0-9]*-\d+)\b")
_PROJECT_KEY_FULL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*-\d+$")
_PROJECT_PREFIX_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*$")
MIN_TS = datetime(1970, 1, 1, tzinfo=timezone.utc)
_DEBUG_KBS = False
_WORKSPACE_KBS_DISABLED = False
_ISSUE_JSON_CACHE: dict[str, dict[str, Any]] = {}
_ACTIVE_THEME = "dark"

try:
    import readline
except ImportError:  # pragma: no cover - platform-dependent
    readline = None  # type: ignore[assignment]


class KbsShowAmbiguous(RuntimeError):
    """Raised when kbs show reports an ambiguous identifier."""


def _debug_kbs(message: str) -> None:
    if _DEBUG_KBS:
        print(message)


def _detect_system_theme() -> str:
    if sys.platform == "darwin":
        try:
            proc = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True,
                text=True,
                check=False,
                timeout=1.0,
            )
            if proc.returncode == 0 and "dark" in (proc.stdout or "").strip().lower():
                return "dark"
            return "light"
        except Exception:
            return "dark"
    return "dark"


def _resolve_theme(mode: str) -> str:
    value = (mode or "auto").strip().lower()
    if value == "auto":
        return _detect_system_theme()
    if value in {"dark", "light"}:
        return value
    return "dark"


def _set_active_theme(mode: str) -> str:
    global _ACTIVE_THEME
    _ACTIVE_THEME = _resolve_theme(mode)
    return _ACTIVE_THEME


async def _set_active_theme_async(mode: str) -> str:
    resolved = await asyncio.to_thread(_resolve_theme, mode)
    global _ACTIVE_THEME
    _ACTIVE_THEME = resolved
    return _ACTIVE_THEME


async def _theme_monitor_loop(
    *,
    mode: str,
    check_seconds: float,
    stop_event: asyncio.Event,
    on_theme_change: Optional[Callable[[str], None]] = None,
) -> None:
    if (mode or "").strip().lower() != "auto":
        return
    interval = max(1.0, check_seconds)
    last = _ACTIVE_THEME
    next_wait = min(2.0, interval)
    pending: str | None = None
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=next_wait)
            break
        except asyncio.TimeoutError:
            pass
        next_theme = await _set_active_theme_async("auto")
        if next_theme != last:
            if pending != next_theme:
                pending = next_theme
            else:
                print(f"kanbus-watch theme change: {last} -> {next_theme}")
                if on_theme_change is not None:
                    on_theme_change(next_theme)
                last = next_theme
                pending = None
        else:
            pending = None
        next_wait = interval


@dataclass
class _CachedFrame:
    key: str
    buffer: Buffer


class _SilentStaticHandler(SimpleHTTPRequestHandler):
    """Quiet static file handler for local runtime assets."""

    def log_message(self, format: str, *args: Any) -> None:  # pragma: no cover - logging side effect
        return


class _RuntimeStaticServer:
    """Serve prebuilt React runtime assets on localhost for Playwright capture."""

    def __init__(self, assets_dir: Path) -> None:
        self._assets_dir = assets_dir
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.base_url: str = ""

    def start(self) -> None:
        runtime_entry = self._assets_dir / "index.html"
        if not runtime_entry.is_file():
            runtime_entry = self._assets_dir / "runtime.html"
        if not runtime_entry.is_file():
            raise RuntimeError(
                "React runtime assets missing at "
                f"{self._assets_dir}. Build them with "
                "`npm --prefix storybook-app run build-pixoo-runtime`."
            )

        handler = partial(_SilentStaticHandler, directory=str(self._assets_dir))
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.base_url = f"http://127.0.0.1:{self._httpd.server_port}/{runtime_entry.name}"
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None


def _runtime_clock_url(base_url: str, args: dict[str, Any]) -> str:
    query: dict[str, str] = {}
    for key, value in args.items():
        rendered = "true" if isinstance(value, bool) and value else "false" if isinstance(value, bool) else str(value)
        query[key] = rendered
    return f"{base_url}?{urlencode(query)}"


class _RuntimeFrameRenderer:
    """Persistent local Playwright renderer for runtime clock frames."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._loaded_base_url: str | None = None
        self._closed = False

    def _ensure_page(self) -> None:
        if self._page is not None:
            return
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=True)
        self._context = self._browser.new_context(
            viewport={"width": 64, "height": 64},
            device_scale_factor=3,
        )
        self._page = self._context.new_page()
        self._closed = False

    def _shutdown_unlocked(self) -> None:
        if self._page is not None:
            try:
                self._page.close()
            except Exception:
                pass
            self._page = None
        if self._context is not None:
            try:
                self._context.close()
            except Exception:
                pass
            self._context = None
        if self._browser is not None:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
        self._loaded_base_url = None
        self._closed = True

    def close(self) -> None:
        with self._lock:
            self._shutdown_unlocked()


class _ParallelFrameRenderer:
    def __init__(self, worker_count: int) -> None:
        self._worker_count = max(1, worker_count)
        self._executor = ThreadPoolExecutor(
            max_workers=self._worker_count,
            thread_name_prefix="react-clock-render-pool",
        )
        self._futures: "OrderedDict[str, Future[Buffer]]" = OrderedDict()
        self._condition = threading.Condition()

    def submit(self, key: str, url: str) -> Future[Buffer]:
        with self._condition:
            future = self._futures.get(key)
            if future is None or future.done():
                future = self._executor.submit(_render_runtime_frame, url)
                self._futures[key] = future
                while len(self._futures) > self._worker_count * 3:
                    self._futures.popitem(last=False)
            return future

    def result(self, key: str, timeout_s: float) -> Buffer | None:
        with self._condition:
            future = self._futures.get(key)
        if future is None:
            return None
        try:
            return future.result(timeout=timeout_s)
        except concurrent.futures.TimeoutError:
            return None
        except Exception:
            with self._condition:
                self._futures.pop(key, None)
            raise

    def render_sync(self, url: str) -> Buffer:
        return _render_runtime_frame(url)

    def close(self) -> None:
        with self._condition:
            for key, future in list(self._futures.items()):
                self._futures.pop(key, None)
                if not future.done():
                    future.cancel()
        self._executor.shutdown(wait=False)

    def _ensure_runtime_loaded(self, base_url: str) -> None:
        if self._loaded_base_url == base_url:
            return
        assert self._page is not None
        self._page.goto(base_url, wait_until="domcontentloaded", timeout=3000)
        self._page.wait_for_function("() => window.__pixooReady === true", timeout=3000)
        self._loaded_base_url = base_url

    def render(self, url: str) -> bytes:
        with self._lock:
            self._ensure_page()
            assert self._page is not None
            parts = urlsplit(url)
            base_url = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
            payload = {k: v for k, v in parse_qsl(parts.query, keep_blank_values=True)}
            try:
                self._ensure_runtime_loaded(base_url)
                self._page.evaluate(
                    """
                    async (args) => {
                      if (typeof window.__pixooApplyClockArgs !== "function") {
                        throw new Error("runtime missing __pixooApplyClockArgs");
                      }
                      await window.__pixooApplyClockArgs(args);
                    }
                    """,
                    payload,
                )
            except Exception:
                # Recreate browser/page once if runtime update failed.
                self._shutdown_unlocked()
                self._ensure_page()
                assert self._page is not None
                self._ensure_runtime_loaded(base_url)
                self._page.evaluate(
                    """
                    async (args) => {
                      if (typeof window.__pixooApplyClockArgs !== "function") {
                        throw new Error("runtime missing __pixooApplyClockArgs");
                      }
                      await window.__pixooApplyClockArgs(args);
                    }
                    """,
                    payload,
                )
            return self._page.screenshot()


_RUNTIME_FRAME_RENDERER = _RuntimeFrameRenderer()
atexit.register(_RUNTIME_FRAME_RENDERER.close)
DEFAULT_FRAME_WORKERS = 2


def _runtime_screenshot_to_buffer(screenshot_bytes: bytes) -> Buffer:
    img = Image.open(io.BytesIO(screenshot_bytes)).convert("RGB")
    if img.size != (64, 64):
        img = img.resize((64, 64), Image.Resampling.BOX)
    pixels = img.get_flattened_data()
    flat = tuple(channel for pixel in pixels for channel in pixel)
    return Buffer(width=64, height=64, data=flat)


def _render_runtime_frame(
    url: str,
    *,
    t: float = 0.0,
) -> Buffer:
    del t
    screenshot = _RUNTIME_FRAME_RENDERER.render(url)
    return _runtime_screenshot_to_buffer(screenshot)


class ReactClockScene:
    name = "react-clock"

    def __init__(
        self,
        *,
        runtime_base_url: str,
        show_second_hand: bool,
        theme: str,
        refresh_fps: int = 5,
        frame_workers: int = DEFAULT_FRAME_WORKERS,
    ) -> None:
        self._runtime_base_url = runtime_base_url
        self._show_second_hand = show_second_hand
        self._theme = theme
        self._refresh_fps = max(1, int(refresh_fps))
        self._cache: _CachedFrame | None = None
        self._refresh_task: asyncio.Task | None = None
        self._stop_refresh = asyncio.Event()
        self._render_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="react-clock-render")
        self._parallel_renderer = _ParallelFrameRenderer(worker_count=frame_workers)

    def _frame_bucket(self, epoch_s: float) -> int:
        return int(epoch_s * self._refresh_fps)

    def _render_clock_sync(self, epoch_s: float) -> Buffer:
        local = time.localtime(epoch_s)
        second_float = min(59.999, max(0.0, local.tm_sec + (epoch_s - int(epoch_s))))
        key = f"{local.tm_hour}:{local.tm_min}:{second_float:.3f}:{self._frame_bucket(epoch_s)}"
        url = _runtime_clock_url(
            self._runtime_base_url,
            {
                "hour": local.tm_hour % 12,
                "minute": local.tm_min,
                "second": f"{second_float:.3f}",
                "showSecondHand": self._show_second_hand,
                "theme": self._theme,
            },
        )
        future = self._parallel_renderer.submit(key, url)
        buf = self._parallel_renderer.result(key, timeout_s=0.05)
        if buf is None:
            try:
                buf = self._parallel_renderer.render_sync(url)
            except Exception as exc:
                raise RuntimeError(
                    f"{threading.current_thread().name}: {exc}"
                ) from exc
        self._cache = _CachedFrame(key=key, buffer=buf)
        return buf

    def _render_clock_cached(self) -> Buffer:
        if self._cache is None:
            return Buffer(width=64, height=64, data=tuple([0] * (64 * 64 * 3)))
        return self._cache.buffer

    async def _refresh_loop(self) -> None:
        sleep_s = max(0.02, 0.5 / self._refresh_fps)
        loop = asyncio.get_running_loop()
        while not self._stop_refresh.is_set():
            now = time.time()
            local = time.localtime(now)
            second_float = min(59.999, max(0.0, local.tm_sec + (now - int(now))))
            key = f"{local.tm_hour}:{local.tm_min}:{second_float:.3f}:{self._frame_bucket(now)}"
            if self._cache is None or self._cache.key != key:
                try:
                    await loop.run_in_executor(self._render_executor, self._render_clock_sync, now)
                except Exception as exc:
                    print(f"react-clock refresh skipped: {exc}")
            await asyncio.sleep(sleep_s)

    async def start(self) -> None:
        if self._refresh_task is not None and not self._refresh_task.done():
            return
        self._stop_refresh.clear()
        loop = asyncio.get_running_loop()
        if self._cache is None:
            try:
                await loop.run_in_executor(self._render_executor, self._render_clock_sync, time.time())
            except Exception as exc:
                print(f"react-clock warmup skipped: {exc}")
        self._refresh_task = asyncio.create_task(self._refresh_loop())

    async def stop(self) -> None:
        self._stop_refresh.set()
        if self._refresh_task is not None:
            self._refresh_task.cancel()
            await asyncio.gather(self._refresh_task, return_exceptions=True)
            self._refresh_task = None
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(self._render_executor, _RUNTIME_FRAME_RENDERER.close)
        self._render_executor.shutdown(wait=False, cancel_futures=True)
        self._parallel_renderer.close()

    def layers(self, ctx: RenderContext) -> list[LayerNode]:
        scene = self

        class _Layer:
            name = "react-clock-layer"

            def render(self, render_ctx: RenderContext) -> Buffer:
                return scene._render_clock_cached()

        return [LayerNode(id="react-clock-root", layer=_Layer(), z=0)]

    def on_enter(self) -> None:
        print("entered React clock scene")

    def on_exit(self) -> None:
        return

    def set_theme(self, theme: str) -> None:
        next_theme = "light" if (theme or "").strip().lower() == "light" else "dark"
        if next_theme == self._theme:
            return
        self._theme = next_theme
        self._cache = None


@dataclass(frozen=True)
class AlertLevelDefaults:
    title: str
    band: str


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
    issue_type_upper: str = "ISSUE"


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
    "alert": AlertLevelDefaults(title="ALERT", band="red"),
    "warn": AlertLevelDefaults(title="WARNING", band="yellow"),
    "info": AlertLevelDefaults(title="INFO", band="sand"),
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


def _radix_token(band: str, step: int) -> str:
    if _ACTIVE_THEME == "light":
        return f"{band}{step}"
    return f"dark.{band}{step}"


def _radix_color(band: str, step: int, *, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    return _safe_parse_color(_radix_token(band, step), fallback=fallback)


def _level_colors(level: str) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    defaults = _LEVEL_DEFAULTS[level]
    fg = _radix_color(defaults.band, 8, fallback=(220, 220, 220))
    bg = _radix_color(defaults.band, 2, fallback=(20, 20, 20))
    return fg, bg


def _canonical_issue_type(issue_type_upper: str) -> str:
    text = _normalize_space(str(issue_type_upper or "ISSUE")).upper()
    for token in ("TASK", "EPIC", "STORY", "BUG"):
        if token in text:
            return token
    return "ISSUE"


_BASE_STEP = 7
_ATTENTION_STEP = 11
_DIM_STEP = 6


def _issue_type_band(issue_type_upper: str) -> str:
    canonical = _canonical_issue_type(issue_type_upper)
    return _ISSUE_TYPE_BANDS.get(canonical, "sand")


def _issue_type_card_colors(
    issue_type_upper: str,
) -> tuple[
    tuple[int, int, int],
    tuple[int, int, int],
    tuple[int, int, int],
    tuple[int, int, int],
    tuple[int, int, int],
    tuple[int, int, int],
]:
    band = _issue_type_band(issue_type_upper)
    if _ACTIVE_THEME == "light":
        # Higher contrast for light theme: darker backgrounds and brighter text.
        base_fg = _radix_color(band, 11, fallback=(70, 70, 70))
        attention_fg = _radix_color(band, 12, fallback=(40, 40, 40))
        dim_fg = _radix_color(band, 10, fallback=(110, 110, 110))
        bg = _radix_color(band, 3, fallback=(220, 220, 220))
        header_bg = _radix_color(band, 5, fallback=(200, 200, 200))
        border = _radix_color(band, 6, fallback=(170, 170, 170))
    else:
        base_fg = _radix_color(band, _BASE_STEP, fallback=(145, 145, 145))
        attention_fg = _radix_color(band, _ATTENTION_STEP, fallback=(180, 180, 180))
        dim_fg = _radix_color(band, _DIM_STEP, fallback=(120, 120, 120))
        bg = _radix_color(band, 1, fallback=(8, 8, 8))
        header_bg = _radix_color(band, 4, fallback=(18, 18, 18))
        border = _radix_color(band, 5, fallback=(30, 30, 30))
    return base_fg, attention_fg, dim_fg, bg, header_bg, border


def _main_content_body_bg(issue_type_upper: str, *, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    """Background for the large bottom body section on card scenes."""
    if _ACTIVE_THEME == "dark":
        return (0, 0, 0)
    return _radix_color(_issue_type_band(issue_type_upper), 2, fallback=fallback)


def _darken_color(color: tuple[int, int, int], *, steps: int) -> tuple[int, int, int]:
    if steps <= 0:
        return color
    factor = 0.82**steps
    return tuple(max(0, min(255, int(c * factor))) for c in color)


def _lighten_color(color: tuple[int, int, int], *, steps: int) -> tuple[int, int, int]:
    if steps <= 0:
        return color
    factor = 1.18**steps
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
    cached = _ISSUE_JSON_CACHE.get(issue_id)
    if cached is not None:
        return dict(cached)
    
    def _attempt(
        cwd_value: Optional[Path],
        label: str,
        *,
        timeout_s: float,
        extra_args: Optional[list[str]] = None,
    ) -> Optional[dict[str, Any]]:
        cwd = str(cwd_value) if cwd_value else None
        _debug_kbs(f"kbs: show {issue_id} --json ({label}, cwd={cwd or 'default'})")
        command = ["kbs", "show", issue_id, "--json"]
        if extra_args:
            command.extend(extra_args)
        try:
            proc = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired as exc:
            _debug_kbs(f"kbs: timeout after {exc.timeout}s for issue {issue_id} ({label})")
            return None
        except Exception as exc:
            _debug_kbs(f"kbs: exception while running show for {issue_id} ({label}): {exc}")
            return None
        _debug_kbs(f"kbs: exit={proc.returncode} ({label})")
        stdout_text = getattr(proc, "stdout", "") or ""
        stderr_text = getattr(proc, "stderr", "") or ""
        if stdout_text:
            _debug_kbs(f"kbs stdout ({label}):\n{stdout_text.strip()}")
        if stderr_text:
            _debug_kbs(f"kbs stderr ({label}):\n{stderr_text.strip()}")
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
        if not isinstance(parsed, dict):
            return None
        parsed_issue_id = str(parsed.get("id") or "").strip()
        if parsed_issue_id:
            _ISSUE_JSON_CACHE[parsed_issue_id] = dict(parsed)
        _ISSUE_JSON_CACHE[issue_id] = dict(parsed)
        return parsed

    # Preferred behavior: scope to the event's project root when available.
    if project_root is not None:
        project_arg_result = _attempt(
            project_root,
            "project-root-arg",
            timeout_s=3.0,
            extra_args=["--project-root", str(project_root)],
        )
        if project_arg_result is not None:
            return project_arg_result

    # Workspace root lookup (skip if it times out).
    global _WORKSPACE_KBS_DISABLED
    if (not _WORKSPACE_KBS_DISABLED) and kbs_root is not None:
        workspace_result = _attempt(kbs_root, "workspace-root", timeout_s=2.0)
        if workspace_result is not None:
            return workspace_result
        _WORKSPACE_KBS_DISABLED = True
        _debug_kbs("kbs: workspace-root lookup disabled after timeout")

    # Final fallback with process default cwd.
    default_result = _attempt(None, "default-cwd-fallback", timeout_s=10.0)
    if default_result is not None:
        return default_result

    return None


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
    issue = _ISSUE_JSON_CACHE.get(issue_id)
    if issue is not None:
        issue = dict(issue)
    else:
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
    issue = _ISSUE_JSON_CACHE.get(parent_id)
    if issue is not None:
        issue = dict(issue)
    else:
        issue = _run_kbs_show_json(parent_id, kbs_root, project_root)
    if issue is None:
        return None
    title = _normalize_space(str(issue.get("title") or issue.get("name") or ""))
    issue_type = _normalize_space(str(issue.get("type") or issue.get("issue_type") or "ISSUE")).upper()
    return ParentSnapshot(
        parent_id=str(issue.get("id") or parent_id),
        description=_normalize_space(str(issue.get("description") or title or "")),
        title=title,
        issue_type_upper=issue_type or "ISSUE",
    )


def _issue_meta_header_parts(snapshot: IssueSnapshot) -> tuple[str, str, str]:
    prefix = _normalize_space(snapshot.id_prefix_upper or "ISSUE")
    issue_type = _normalize_space(snapshot.issue_type_upper or "ISSUE").upper()
    status = _normalize_space(str(snapshot.status_upper or "OPEN")).upper()
    return (prefix, issue_type, status)


def _is_project_prefix(value: str) -> bool:
    text = _normalize_space(value).upper()
    return bool(text and _PROJECT_PREFIX_RE.fullmatch(text))


def _event_prefix_override(event_issue_id: str) -> str:
    """Prefer the event issue id for header prefix when it is meaningful."""
    text = (event_issue_id or "").strip()
    if not text:
        return ""
    if "-" not in text:
        return ""
    candidate = _issue_id_prefix_upper(text)
    # Never use a numeric-only prefix like "1234".
    if not _is_project_prefix(candidate):
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
            if prefix and not prefix.isdigit():
                return prefix
    payload_custom = payload.get("custom")
    if isinstance(payload_custom, dict):
        for key in key_fields:
            value = payload_custom.get(key)
            if isinstance(value, str) and value.strip():
                prefix = _issue_id_prefix_upper(value)
                if prefix and not prefix.isdigit():
                    return prefix
    pattern_key = _extract_issue_key_pattern(*_collect_string_values(payload))
    if pattern_key:
        prefix = _issue_id_prefix_upper(pattern_key)
        if prefix and not prefix.isdigit():
            return prefix
    # Compose from common split fields.
    project_key = payload.get("project_key") or payload.get("projectKey") or payload.get("project")
    issue_num = payload.get("issue_number") or payload.get("issueNumber") or payload.get("number")
    if isinstance(project_key, str) and project_key.strip() and issue_num is not None:
        composed = f"{project_key.strip()}-{issue_num}"
        prefix = _issue_id_prefix_upper(composed)
        if prefix and not prefix.isdigit():
            return prefix
    return ""


def _wrap_text_or_placeholder(
    text: str,
    *,
    max_lines: int,
    max_width_px: int = 62,
    placeholder: str,
    font_key: str = "bytesized",
) -> list[str]:
    wrapped = _wrap_text_lines(text, max_width_px=max_width_px, max_lines=max_lines, font_key=font_key)
    if wrapped:
        return wrapped
    return [placeholder]


def _wrap_desc(text: str, *, max_lines: int, max_width_px: int = 62) -> list[str]:
    return _wrap_text_or_placeholder(
        text,
        max_lines=max_lines,
        max_width_px=max_width_px,
        placeholder="(no description)",
    )


def _wrap_title(text: str, *, max_lines: int, max_width_px: int = 62) -> list[str]:
    return _wrap_text_or_placeholder(
        text,
        max_lines=max_lines,
        max_width_px=max_width_px,
        placeholder="(no title)",
    )


def _wrap_desc_fill_rows(text: str, *, target_rows: int) -> list[str]:
    # Reflow progressively tighter (word-wrap only) to occupy requested rows.
    best: list[str] = []
    for width in (54, 50, 46, 42, 38, 34):
        wrapped = _wrap_desc(text, max_lines=target_rows, max_width_px=width)
        best = wrapped
        if len(wrapped) >= target_rows:
            break
    return _fixed_rows(best, target_rows)


def _wrap_title_fill_rows(text: str, *, target_rows: int) -> list[str]:
    # Reflow progressively tighter (word-wrap only) to occupy requested rows.
    best: list[str] = []
    for width in (54, 50, 46, 42, 38, 34):
        wrapped = _wrap_title(text, max_lines=target_rows, max_width_px=width)
        best = wrapped
        if len(wrapped) >= target_rows:
            break
    return _fixed_rows(best, target_rows)


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
    status_lighter_steps: int = 0,
    top_section_bg: tuple[int, int, int] | None = None,
    bottom_section_bg: tuple[int, int, int] | None = None,
    header_section_bg: tuple[int, int, int] | None = None,
    show_header_bottom_border: bool = False,
    header_height_extra_px: int = 3,
    body_row_height: int = 7,
    fill_body_to_viewport: bool = False,
) -> InfoScene:
    base_fg, attention_fg, dim_fg, bg, header_bg, border_color = _issue_type_card_colors(issue_type_upper)
    header_color = base_fg
    main_fg = base_fg
    row_font = "bytesized"
    row_height = max(1, int(body_row_height))

    header_font = "bytesized"
    header_metrics = [measure_scene_text(part, header_font)[1] for part in header_parts if part]
    header_height = max(4, int(max(header_metrics) if header_metrics else 5) + int(header_height_extra_px))

    part_colors = [
        header_color,
        header_color,
        attention_fg if status_lighter_steps > 0 else header_color,
    ]

    def _header_spans(text: str, color: tuple[int, int, int]) -> list[TextSpan]:
        words = [token for token in _normalize_space(text).split(" ") if token]
        spans: list[TextSpan] = []
        for idx, word in enumerate(words):
            spans.append(TextSpan(text=word, font=header_font, color=color))
            if idx < len(words) - 1:
                spans.append(TextSpan(text="", advance_px=2))
        return spans

    header_spans: list[TextSpan] = []
    for index, part in enumerate([p for p in header_parts if p]):
        if header_spans:
            header_spans.append(TextSpan(text="", advance_px=3))
        color = part_colors[min(index, len(part_colors) - 1)]
        header_spans.extend(_header_spans(part, color))
    resolved_top_bg = top_section_bg if top_section_bg is not None else bg
    resolved_bottom_bg = bottom_section_bg if bottom_section_bg is not None else bg
    resolved_header_bg = header_section_bg if header_section_bg is not None else header_bg

    content_rows = len(top_lines) + len(bottom_lines) + (1 if show_middle_divider else 0)
    trailing_fill_px = 0
    if fill_body_to_viewport and content_rows > 0:
        available_body = max(0, 64 - header_height)
        row_height = max(1, available_body // content_rows)
        trailing_fill_px = max(0, available_body - (row_height * content_rows))

    rows: list[Any] = [
        TextRow(
            height=header_height,
            align="left",
            background_color=resolved_header_bg,
            border=BorderConfig(
                enabled=show_header_bottom_border,
                thickness=1,
                color=border_color,
            ),
            style=TextStyle(font=header_font, color=header_color),
            content=header_spans,
        )
    ]

    for line in top_lines:
        rows.append(
            TextRow(
                height=row_height,
                align="left",
                background_color=resolved_top_bg,
                style=TextStyle(font=row_font, color=dim_fg),
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
                style=TextStyle(font=row_font, color=header_color),
                content="",
            )
        )
    for line in bottom_lines:
        rows.append(
            TextRow(
                height=row_height,
                align="left",
                background_color=resolved_bottom_bg,
                style=TextStyle(font=row_font, color=main_fg),
                content=line,
            )
        )
    if trailing_fill_px > 0:
        rows.append(
            TextRow(
                height=trailing_fill_px,
                align="left",
                background_color=resolved_bottom_bg,
                style=TextStyle(font=row_font, color=main_fg),
                content="",
            )
        )

    return InfoScene(layout=InfoLayout(rows=rows, background_color=bg), name=name)


def _build_comment_like_scene(
    *,
    issue_type_upper: str,
    header_parts: tuple[str, str, str],
    parent_lines: list[str],
    issue_lines: list[str],
    bottom_lines: list[str],
    parent_text_color: tuple[int, int, int],
    issue_text_color: tuple[int, int, int],
    bottom_text_color: tuple[int, int, int],
    parent_bg: tuple[int, int, int],
    issue_bg: tuple[int, int, int],
    bottom_bg: tuple[int, int, int],
    header_bg: tuple[int, int, int],
    header_text_color: tuple[int, int, int],
    header_id_color: tuple[int, int, int] | None = None,
    header_issue_type_color: tuple[int, int, int] | None = None,
    header_status_color: tuple[int, int, int] | None = None,
    name: str,
) -> InfoScene:
    row_height = 6
    header_height = 6
    header_font = "bytesized"
    border_color = tuple(max(0, int(c * 0.55)) for c in header_text_color)
    header_spans: list[TextSpan] = []
    for index, part in enumerate([p for p in header_parts if p]):
        if header_spans:
            header_spans.append(TextSpan(text="", advance_px=3))
        if index == 0:
            color = header_id_color or header_text_color
        elif index == 1:
            color = header_issue_type_color or header_text_color
        else:
            color = header_status_color or header_text_color
        words = [token for token in _normalize_space(part).split(" ") if token]
        for idx, word in enumerate(words):
            header_spans.append(TextSpan(text=word, font=header_font, color=color))
            if idx < len(words) - 1:
                header_spans.append(TextSpan(text="", advance_px=2))
    rows: list[Any] = [
        TextRow(
            height=header_height,
            align="left",
            background_color=header_bg,
            border=BorderConfig(enabled=False, thickness=1, color=border_color),
            style=TextStyle(font=header_font, color=header_text_color),
            content=header_spans,
        )
    ]
    for line in parent_lines:
        rows.append(
            TextRow(
                height=row_height,
                align="left",
                background_color=parent_bg,
                style=TextStyle(font="bytesized", color=parent_text_color),
                content=line,
            )
        )
    for line in issue_lines:
        rows.append(
            TextRow(
                height=row_height,
                align="left",
                background_color=issue_bg,
                style=TextStyle(font="bytesized", color=issue_text_color),
                content=line,
            )
        )
    for line in bottom_lines:
        rows.append(
            TextRow(
                height=row_height,
                align="left",
                background_color=bottom_bg,
                style=TextStyle(font="bytesized", color=bottom_text_color),
                content=line,
            )
        )
    return InfoScene(layout=InfoLayout(rows=rows, background_color=bottom_bg), name=name)


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
    payload_title = _normalize_space(str(payload.get("title") or payload.get("name") or ""))
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
            title=payload_title,
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
            title=snapshot.title or payload_title,
            parent_id=snapshot.parent_id,
            latest_comment_text=snapshot.latest_comment_text,
        )
    elif not snapshot.title and payload_title:
        snapshot = IssueSnapshot(
            issue_id=snapshot.issue_id,
            id_prefix_upper=snapshot.id_prefix_upper,
            issue_type_upper=snapshot.issue_type_upper or payload_type or "ISSUE",
            status_upper=snapshot.status_upper or payload_status or "OPEN",
            description=snapshot.description,
            title=payload_title,
            parent_id=snapshot.parent_id,
            latest_comment_text=snapshot.latest_comment_text,
        )
    event_prefix = payload_prefix or _event_prefix_override(event.issue_id)
    if event_prefix and not _is_project_prefix(snapshot.id_prefix_upper):
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
    issue_title = snapshot.title

    if etype == "issue_created":
        base_fg, attention_fg, _dim_fg, event_bg, header_bg, _ = _issue_type_card_colors(snapshot.issue_type_upper)
        band = _issue_type_band(snapshot.issue_type_upper)
        id_color = _radix_color(band, min(_BASE_STEP + 1, 12), fallback=base_fg)
        issue_bg = _radix_color(_issue_type_band(snapshot.issue_type_upper), 2, fallback=event_bg)
        body_bg = _main_content_body_bg(snapshot.issue_type_upper, fallback=event_bg)
        parent_snapshot = (
            _fetch_parent_snapshot(snapshot.parent_id, kbs_root, project_root)
            if snapshot.parent_id
            else None
        )
        parent_lines: list[str] = []
        parent_title = ""
        if parent_snapshot is not None:
            parent_title = parent_snapshot.title
            parent_lines = _fixed_rows(_wrap_title(parent_title, max_lines=2), 2)
        issue_lines = _fixed_rows(_wrap_title(issue_title, max_lines=2), 2)
        bottom_count = 5 if parent_snapshot is not None else 7
        bottom_lines = _fixed_rows(_wrap_desc(snapshot.description, max_lines=bottom_count), bottom_count)
        _debug_kbs(
            f"render created: parent_title={parent_title!r} issue_title={issue_title!r} "
            f"bottom_first={bottom_lines[0]!r}"
        )
        parent_text_color = base_fg
        parent_bg = _radix_color(_issue_type_band(snapshot.issue_type_upper), 3, fallback=event_bg)
        if parent_snapshot is not None:
            parent_band = _issue_type_band(parent_snapshot.issue_type_upper)
            parent_base_fg, _, _, _, _, _ = _issue_type_card_colors(parent_snapshot.issue_type_upper)
            parent_text_color = parent_base_fg
            parent_bg = _radix_color(parent_band, 3, fallback=event_bg)
        scene = _build_comment_like_scene(
            issue_type_upper=snapshot.issue_type_upper,
            header_parts=header_parts,
            parent_lines=parent_lines,
            issue_lines=issue_lines,
            bottom_lines=bottom_lines,
            parent_text_color=parent_text_color,
            issue_text_color=base_fg,
            bottom_text_color=attention_fg,
            parent_bg=parent_bg,
            issue_bg=issue_bg,
            bottom_bg=body_bg,
            header_bg=header_bg,
            header_text_color=base_fg,
            header_id_color=id_color,
            header_issue_type_color=base_fg,
            header_status_color=attention_fg,
            name="created-scene",
        )
        return AutoNotice(
            header=header_text,
            message="\n".join(parent_lines + issue_lines + bottom_lines),
            scene=scene,
        )

    if etype == "state_transition":
        base_fg, attention_fg, _dim_fg, event_bg, header_bg, _ = _issue_type_card_colors(snapshot.issue_type_upper)
        band = _issue_type_band(snapshot.issue_type_upper)
        id_color = _radix_color(band, min(_BASE_STEP + 1, 12), fallback=base_fg)
        issue_bg = _radix_color(_issue_type_band(snapshot.issue_type_upper), 2, fallback=event_bg)
        body_bg = _main_content_body_bg(snapshot.issue_type_upper, fallback=event_bg)
        parent_snapshot = (
            _fetch_parent_snapshot(snapshot.parent_id, kbs_root, project_root)
            if snapshot.parent_id
            else None
        )
        parent_lines: list[str] = []
        parent_title = ""
        if parent_snapshot is not None:
            parent_title = parent_snapshot.title
            parent_lines = _fixed_rows(_wrap_title(parent_title, max_lines=2), 2)
        issue_lines = _fixed_rows(_wrap_title(issue_title, max_lines=2), 2)
        bottom_count = 5 if parent_snapshot is not None else 7
        bottom_lines = _fixed_rows(_wrap_desc(snapshot.description, max_lines=bottom_count), bottom_count)
        _debug_kbs(
            f"render transition: parent_title={parent_title!r} issue_title={issue_title!r} "
            f"bottom_first={bottom_lines[0]!r}"
        )
        parent_text_color = base_fg
        parent_bg = _radix_color(_issue_type_band(snapshot.issue_type_upper), 3, fallback=event_bg)
        if parent_snapshot is not None:
            parent_band = _issue_type_band(parent_snapshot.issue_type_upper)
            parent_base_fg, _, _, _, _, _ = _issue_type_card_colors(parent_snapshot.issue_type_upper)
            parent_text_color = parent_base_fg
            parent_bg = _radix_color(parent_band, 3, fallback=event_bg)
        scene = _build_comment_like_scene(
            issue_type_upper=snapshot.issue_type_upper,
            header_parts=header_parts,
            parent_lines=parent_lines,
            issue_lines=issue_lines,
            bottom_lines=bottom_lines,
            parent_text_color=parent_text_color,
            issue_text_color=base_fg,
            bottom_text_color=attention_fg,
            parent_bg=parent_bg,
            issue_bg=issue_bg,
            bottom_bg=body_bg,
            header_bg=header_bg,
            header_text_color=base_fg,
            header_id_color=id_color,
            header_issue_type_color=base_fg,
            header_status_color=attention_fg,
            name="transition-scene",
        )
        return AutoNotice(
            header=header_text,
            message="\n".join(parent_lines + issue_lines + bottom_lines),
            scene=scene,
        )

    if etype == "comment_added":
        base_fg, attention_fg, _dim_fg, event_bg, header_bg, _ = _issue_type_card_colors(snapshot.issue_type_upper)
        band = _issue_type_band(snapshot.issue_type_upper)
        id_color = _radix_color(band, min(_BASE_STEP + 1, 12), fallback=base_fg)
        issue_bg = _radix_color(_issue_type_band(snapshot.issue_type_upper), 2, fallback=event_bg)
        body_bg = _main_content_body_bg(snapshot.issue_type_upper, fallback=event_bg)
        comment_text = _extract_comment_text(payload)
        if (not comment_text) or (len(comment_text) < 8) or (" " not in comment_text):
            comment_text = snapshot.latest_comment_text

        parent_snapshot = (
            _fetch_parent_snapshot(snapshot.parent_id, kbs_root, project_root)
            if snapshot.parent_id
            else None
        )
        parent_lines: list[str] = []
        parent_title = ""
        if parent_snapshot is not None:
            parent_title = parent_snapshot.title
            parent_lines = _fixed_rows(_wrap_title(parent_title, max_lines=2), 2)
        issue_lines = _fixed_rows(_wrap_title(issue_title, max_lines=2), 2)
        bottom_count = 5 if parent_snapshot is not None else 7
        comment_lines = _fixed_rows(_wrap_desc(comment_text, max_lines=bottom_count), bottom_count)
        _debug_kbs(
            f"render comment: parent_title={parent_title!r} issue_title={issue_title!r} "
            f"comment_first={comment_lines[0]!r}"
        )
        comment_fg = _radix_color("sky", _ATTENTION_STEP, fallback=(180, 210, 230))
        parent_text_color = base_fg
        parent_bg = _radix_color(_issue_type_band(snapshot.issue_type_upper), 3, fallback=event_bg)
        if parent_snapshot is not None:
            parent_band = _issue_type_band(parent_snapshot.issue_type_upper)
            parent_base_fg, _, _, _, _, _ = _issue_type_card_colors(parent_snapshot.issue_type_upper)
            parent_text_color = parent_base_fg
            parent_bg = _radix_color(parent_band, 3, fallback=event_bg)
        scene = _build_comment_like_scene(
            issue_type_upper=snapshot.issue_type_upper,
            header_parts=header_parts,
            parent_lines=parent_lines,
            issue_lines=issue_lines,
            bottom_lines=comment_lines,
            parent_text_color=parent_text_color,
            issue_text_color=base_fg,
            bottom_text_color=comment_fg,
            parent_bg=parent_bg,
            issue_bg=issue_bg,
            bottom_bg=body_bg,
            header_bg=header_bg,
            header_text_color=base_fg,
            header_id_color=id_color,
            header_issue_type_color=base_fg,
            header_status_color=base_fg,
            name="comment-scene",
        )
        return AutoNotice(
            header=header_text,
            message="\n".join(parent_lines + issue_lines + comment_lines),
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

    total_events = 0
    for folder in sorted(tracked.keys()):
        events = scan_folder_for_new_events(
            folder,
            tracked[folder],
            failures,
            max_failures=max_failures,
        )
        if _DEBUG_KBS and events:
            logs.append(f"watcher: {len(events)} new event(s) in {folder}")
        for event in events:
            total_events += 1
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

    if _DEBUG_KBS and total_events == 0:
        logs.append("watcher: scan complete (no new events)")

    return logs, notices


def _issue_comment_count(issue: dict[str, Any]) -> int:
    comments = issue.get("comments")
    return len(comments) if isinstance(comments, list) else 0


def _issue_latest_comment_text(issue: dict[str, Any]) -> str:
    comments = issue.get("comments")
    if not isinstance(comments, list):
        return ""
    for item in reversed(comments):
        if isinstance(item, dict):
            text = _normalize_space(str(item.get("text") or ""))
            if text:
                return text
    return ""


def _event_from_gossip_envelope(
    envelope: dict[str, Any],
    *,
    prior_issue: Optional[dict[str, Any]],
    project_root: Optional[Path] = None,
) -> Optional[KanbusEvent]:
    if str(envelope.get("type") or "").strip() != "issue.mutated":
        return None
    issue = envelope.get("issue")
    if not isinstance(issue, dict):
        return None

    issue_id = str(issue.get("id") or envelope.get("issue_id") or "").strip()
    if not issue_id:
        return None

    occurred_at = _parse_iso8601(str(envelope.get("ts") or ""))
    event_id = str(envelope.get("event_id") or envelope.get("id") or "").strip()
    actor_id = str(envelope.get("producer_id") or "gossip").strip() or "gossip"

    current_status = _format_status_text(issue.get("status") or "")
    prior_status = _format_status_text((prior_issue or {}).get("status") or "")
    current_comment_count = _issue_comment_count(issue)
    prior_comment_count = _issue_comment_count(prior_issue or {})
    latest_comment = _issue_latest_comment_text(issue)

    created_at = str(issue.get("created_at") or "")
    updated_at = str(issue.get("updated_at") or "")

    event_type = ""
    payload: dict[str, Any] = {}

    if current_comment_count > prior_comment_count and latest_comment:
        event_type = "comment_added"
        payload = {
            "comment": latest_comment,
            "project_key": str(envelope.get("project") or ""),
        }
    elif prior_issue is not None and current_status and prior_status and current_status != prior_status:
        event_type = "state_transition"
        payload = {
            "from_status": prior_status,
            "to_status": current_status,
            "project_key": str(envelope.get("project") or ""),
        }
    elif prior_issue is None and created_at and updated_at and created_at == updated_at:
        event_type = "issue_created"
        payload = {
            "issue_type": str(issue.get("type") or "issue"),
            "status": str(issue.get("status") or "open"),
            "title": str(issue.get("title") or ""),
            "description": str(issue.get("description") or ""),
            "project_key": str(envelope.get("project") or ""),
        }
    else:
        return None

    return KanbusEvent(
        path=Path(f"gossip://{event_id or issue_id}"),
        schema_version=1,
        event_id=event_id or issue_id,
        issue_id=issue_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor_id=actor_id,
        payload=payload,
        repo_root=project_root,
    )


def _gossip_restart_delay_seconds(consecutive_failures: int) -> float:
    """Return bounded retry delay for gossip worker restarts."""
    failures = max(0, consecutive_failures)
    exponent = min(failures, 6)  # cap at 32x
    return min(30.0, 0.5 * (2 ** exponent))


async def _watch_gossip_worker(
    *,
    root: Path,
    notices: asyncio.Queue[AutoNotice],
    stop_event: asyncio.Event,
    kbs_root: Optional[Path] = None,
    seen_ids: set[str],
    seen_order: deque[str],
    prior_issue_by_id: dict[str, dict[str, Any]],
    startup_cutoff: Optional[datetime] = None,
    seen_max: int = 4096,
    max_failures_before_disable: int = 5,
) -> None:
    broker_proc: asyncio.subprocess.Process | None = None
    consecutive_failures = 0

    async def _start_broker_if_needed() -> None:
        nonlocal broker_proc
        if broker_proc is not None and broker_proc.returncode is None:
            return
        broker_proc = await asyncio.create_subprocess_exec(
            "kbs",
            "gossip",
            "broker",
            cwd=str(root),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        print(f"gossip: started local broker ({root})")
        await asyncio.sleep(0.25)

    try:
        while not stop_event.is_set():
            await _start_broker_if_needed()
            proc = await asyncio.create_subprocess_exec(
                "kbs",
                "gossip",
                "watch",
                "--print",
                cwd=str(root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            saw_connection_refused = False
            assert proc.stdout is not None
            while not stop_event.is_set():
                line = await proc.stdout.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").strip()
                if not text:
                    continue
                if "Connection refused" in text:
                    saw_connection_refused = True
                    print(f"gossip: {text}")
                    continue
                try:
                    envelope = json.loads(text)
                except Exception:
                    if _DEBUG_KBS:
                        print(f"gossip: non-json: {text}")
                    continue
                if not isinstance(envelope, dict):
                    continue
                envelope_id = str(envelope.get("id") or "").strip()
                if envelope_id and envelope_id in seen_ids:
                    continue
                if envelope_id:
                    seen_ids.add(envelope_id)
                    seen_order.append(envelope_id)
                    while len(seen_order) > seen_max:
                        old = seen_order.popleft()
                        seen_ids.discard(old)

                issue = envelope.get("issue")
                if isinstance(issue, dict):
                    issue_id = str(issue.get("id") or envelope.get("issue_id") or "").strip()
                    if issue_id:
                        _ISSUE_JSON_CACHE[issue_id] = dict(issue)
                        prior_issue = prior_issue_by_id.get(issue_id)
                        event = _event_from_gossip_envelope(
                            envelope,
                            prior_issue=prior_issue,
                            project_root=root,
                        )
                        prior_issue_by_id[issue_id] = dict(issue)
                    else:
                        event = None
                else:
                    event = None

                if event is None:
                    continue
                if (
                    startup_cutoff is not None
                    and event.occurred_at is not None
                    and event.occurred_at < startup_cutoff
                ):
                    if _DEBUG_KBS:
                        print(
                            f"gossip[{root.name}]: skip historical event "
                            f"{event.event_type} {event.issue_id} at {event.occurred_at.isoformat()}"
                        )
                    continue
                try:
                    notice = await asyncio.to_thread(summarize_event, event, kbs_root)
                except KbsShowAmbiguous:
                    print(f"gossip: ambiguous identifier for {event.issue_id}, skipping")
                    continue
                if notice is None:
                    continue
                await _enqueue_auto_notice(notices, notice)
                if _DEBUG_KBS:
                    print(f"gossip[{root.name}]: event {event.event_type} {event.issue_id}")

            try:
                returncode = await asyncio.wait_for(proc.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                proc.terminate()
                await proc.wait()
                returncode = -1
            if stop_event.is_set():
                break
            if saw_connection_refused:
                await _start_broker_if_needed()
            if returncode != 0:
                consecutive_failures += 1
                if consecutive_failures >= max_failures_before_disable:
                    print(
                        f"gossip[{root.name}]: disabled after "
                        f"{consecutive_failures} consecutive failures (rc={returncode})"
                    )
                    break
                delay = _gossip_restart_delay_seconds(consecutive_failures)
                print(
                    f"gossip[{root.name}]: watch exited rc={returncode}; "
                    f"retrying in {delay:.1f}s (failure {consecutive_failures})"
                )
            else:
                consecutive_failures = 0
                delay = 0.5
            await asyncio.sleep(delay)
    finally:
        if broker_proc is not None and broker_proc.returncode is None:
            broker_proc.terminate()
            try:
                await asyncio.wait_for(broker_proc.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                broker_proc.kill()
                await broker_proc.wait()


async def _watch_gossip_loop(
    *,
    roots: list[Path],
    notices: asyncio.Queue[AutoNotice],
    stop_event: asyncio.Event,
    kbs_root: Optional[Path] = None,
) -> None:
    seen_ids: set[str] = set()
    seen_order: deque[str] = deque()
    prior_issue_by_id: dict[str, dict[str, Any]] = {}
    startup_cutoff = datetime.now(timezone.utc)
    print(f"gossip: startup cutoff {startup_cutoff.isoformat()} (ignoring older events)")
    workers = [
        asyncio.create_task(
            _watch_gossip_worker(
                root=project_root,
                notices=notices,
                stop_event=stop_event,
                kbs_root=kbs_root or project_root,
                seen_ids=seen_ids,
                seen_order=seen_order,
                prior_issue_by_id=prior_issue_by_id,
                startup_cutoff=startup_cutoff,
            )
        )
        for project_root in roots
    ]
    try:
        await stop_event.wait()
    finally:
        for worker in workers:
            worker.cancel()
        await asyncio.gather(*workers, return_exceptions=True)


# --------------------------
# Runtime loops
# --------------------------


async def _enqueue_auto_notice(
    queue: asyncio.Queue[AutoNotice],
    notice: AutoNotice,
    *,
    high_watermark: int = 48,
) -> None:
    await queue.put(notice)
    if queue.qsize() >= high_watermark:
        print(f"watcher: auto notice backlog at {queue.qsize()} items")


async def _wait_for_queue_capacity(
    player: ScenePlayer,
    *,
    threshold: int = 28,
    sleep_seconds: float = 0.05,
) -> None:
    while player.queue_depth >= threshold:
        await asyncio.sleep(sleep_seconds)


async def _enqueue_player_item_with_retry(
    player: ScenePlayer,
    item: QueueItem,
    *,
    label: str,
    retry_sleep_seconds: float = 0.05,
    warn_every_attempts: int = 20,
) -> None:
    attempts = 0
    while True:
        await _wait_for_queue_capacity(player)
        try:
            await player.enqueue(item)
            return
        except ValueError as exc:
            if "queue is full" not in str(exc).lower():
                raise
            attempts += 1
            if attempts % warn_every_attempts == 0:
                print(
                    f"scene: enqueue retry for {label}; queue still full "
                    f"(attempt={attempts}, depth={player.queue_depth})"
                )
            await asyncio.sleep(retry_sleep_seconds)


async def _enqueue_message_transition(
    *,
    player: ScenePlayer,
    clock_scene: Any,
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

    await _enqueue_player_item_with_retry(
        player,
        QueueItem(
            scene=resolved_scene,
            transition=TransitionSpec(kind="push_left", duration_ms=duration_ms),
            hold_ms=hold_ms,
        ),
        label="notice-scene",
    )

    await _enqueue_player_item_with_retry(
        player,
        QueueItem(
            scene=clock_scene,
            transition=TransitionSpec(kind="push_left", duration_ms=duration_ms),
            hold_ms=0,
        ),
        label="clock-return",
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
    last_heartbeat = 0.0

    while not stop_event.is_set():
        now = time.monotonic()
        do_rescan = now >= next_rescan
        try:
            logs, discovered = await asyncio.to_thread(
                _watch_poll_step,
                root=root,
                tracked=tracked,
                failures=failures,
                do_rescan=do_rescan,
                max_failures=max_failures,
                kbs_root=kbs_root,
            )
        except Exception as exc:
            print(f"watcher: poll error: {exc}")
            await asyncio.sleep(max(0.1, poll_seconds))
            continue
        for line in logs:
            print(line)
        for notice in discovered:
            await _enqueue_auto_notice(notices, notice)
        if do_rescan:
            next_rescan = now + max(0.5, rescan_seconds)
        if _DEBUG_KBS and (now - last_heartbeat) >= 5.0:
            print(
                "watcher: heartbeat "
                f"tracked={len(tracked)} backlog={notices.qsize()} failures={len(failures)}"
            )
            last_heartbeat = now

        await asyncio.sleep(max(0.1, poll_seconds))


async def _auto_notice_consumer(
    *,
    notices: asyncio.Queue[AutoNotice],
    player: ScenePlayer,
    clock_scene: Any,
    stop_event: asyncio.Event,
    transition_ms: int,
    auto_info_seconds: float,
) -> None:
    while not stop_event.is_set():
        try:
            notice = await asyncio.wait_for(notices.get(), timeout=0.25)
        except asyncio.TimeoutError:
            continue
        try:
            if _DEBUG_KBS:
                print(
                    f"consumer: dequeued notice level={notice.level} header={notice.header!r} "
                    f"queue_depth={player.queue_depth}"
                )
            fg, bg = _level_colors(notice.level)
            if _DEBUG_KBS:
                print("consumer: enqueueing transition to notice")
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
        except Exception as exc:
            print(f"consumer: failed to enqueue notice transition: {exc}")
        finally:
            notices.task_done()


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
    clock_scene: Any,
    transition_ms: int,
) -> None:
    command_parsers = {
        "alert": _build_command_parser("alert"),
        "warn": _build_command_parser("warn"),
        "info": _build_command_parser("info"),
    }

    print("Kanbus clock ready. Type 'help' for commands.")
    while True:
        try:
            raw = await asyncio.to_thread(input, "kanbus-clock> ")
        except EOFError:
            break
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


def discover_kanbus_project_roots(root: Path) -> list[Path]:
    """Find descendant Kanbus project roots by `.kanbus.yml` files."""
    ignored_dirs = {
        ".git",
        ".kanbus",
        ".venv",
        "node_modules",
        "dist",
        "build",
        "cdk.out",
        "tmp",
        "target",
        "__pycache__",
        "project",
        "project-local",
        ".pytest_cache",
        ".mypy_cache",
    }
    roots: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            name
            for name in dirnames
            if name not in ignored_dirs and not name.startswith("asset.")
        ]
        if ".kanbus.yml" in filenames:
            roots.append(Path(dirpath).resolve())
    return sorted(dict.fromkeys(roots))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Kanbus clock REPL + Kanbus events watcher")
    parser.add_argument("--ip", default=DEFAULT_IP)
    parser.add_argument("--fps", type=int, default=5)
    parser.add_argument("--transition-ms", type=int, default=1200)
    parser.add_argument("--root", default=".")
    parser.add_argument("--auto-info-seconds", type=float, default=30.0)
    parser.add_argument("--history-file", default=str(DEFAULT_HISTORY_FILE))
    parser.add_argument(
        "--react-frame-workers",
        type=int,
        default=DEFAULT_FRAME_WORKERS,
        help="Number of parallel workers rendering React frames (default 2)",
    )
    parser.add_argument("--react-clock", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--theme",
        choices=("auto", "dark", "light"),
        default="auto",
        help="Color theme for clock and cards (default: auto)",
    )
    parser.add_argument(
        "--theme-check-seconds",
        type=float,
        default=DEFAULT_THEME_CHECK_SECONDS,
        help="How often auto theme mode re-checks system appearance (default: 5s)",
    )
    parser.add_argument(
        "--react-second-hand",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    parser.add_argument("--debug", action="store_true", help="print kbs commands and responses")
    parser.add_argument("--no-repl", action="store_true", help="disable interactive REPL")
    return parser


async def run(
    *,
    ip: str,
    fps: int,
    transition_ms: int,
    root: Path,
    auto_info_seconds: float,
    history_file: Path,
    theme: str,
    theme_check_seconds: float,
    react_clock: bool,
    react_second_hand: bool,
    react_frame_workers: int,
    debug: bool,
    no_repl: bool,
) -> None:
    global _DEBUG_KBS
    _DEBUG_KBS = debug
    selected_theme = _set_active_theme(theme)
    print(f"kanbus-watch theme: {theme} -> {selected_theme}")
    print(f"kanbus-watch root: {root}")
    print("kanbus-watch source: gossip")
    gossip_roots = discover_kanbus_project_roots(root.resolve())
    if not gossip_roots:
        raise SystemExit(
            f"No Kanbus projects found under {root.resolve()}.\n"
            "Initialize one with: `cd <root> && kbs init`."
        )
    print("kanbus-watch gossip mode: workspace descendants")
    print(f"kanbus-watch: found {len(gossip_roots)} Kanbus project root(s)")
    for project_root in gossip_roots:
        print(f" - gossip root: {project_root}")

    print(f"pixoo: connecting to {ip}")
    pixoo = Pixoo(ip)
    if not pixoo.connect():
        raise SystemExit(f"Failed to connect to Pixoo at {ip}")
    try:
        sink = PixooFrameSink(pixoo, reconnect=True)
        raster = AsyncRasterClient(sink)
        player = ScenePlayer(raster, fps=max(1, fps))
        player._debug = bool(debug)  # type: ignore[attr-defined]

        runtime_server: _RuntimeStaticServer | None = None
        if react_clock:
            runtime_server = _RuntimeStaticServer(DEFAULT_RUNTIME_ASSETS)
            runtime_server.start()
            clock_scene = ReactClockScene(
                runtime_base_url=runtime_server.base_url,
                show_second_hand=react_second_hand,
                theme=selected_theme,
                refresh_fps=max(1, fps),
                frame_workers=max(1, react_frame_workers),
            )
            await clock_scene.start()
            print(f"clock-source: react runtime {runtime_server.base_url}")
        else:
            style = clock._style_from_args(clock.build_parser(ip_default=ip).parse_args([]))
            clock_scene = ClockScene(render_frame=lambda ts: clock.render_clock_frame(ts, style), name="clock")
            print("clock-source: python pixooclock")
        notices: asyncio.Queue[AutoNotice] = asyncio.Queue(maxsize=64)
        stop_event = asyncio.Event()

        _setup_readline_history(history_file)

        await player.set_scene(clock_scene)
        runner = asyncio.create_task(player.run())
        on_theme_change = None
        if hasattr(clock_scene, "set_theme"):
            on_theme_change = clock_scene.set_theme
        theme_monitor = asyncio.create_task(
            _theme_monitor_loop(
                mode=theme,
                check_seconds=max(1.0, theme_check_seconds),
                stop_event=stop_event,
                on_theme_change=on_theme_change,
            )
        )
        watcher = asyncio.create_task(
            _watch_gossip_loop(
                roots=gossip_roots,
                notices=notices,
                stop_event=stop_event,
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
            repl_enabled = (not no_repl) and sys.stdin.isatty()
            if not repl_enabled:
                print("repl: disabled (no tty or --no-repl)")
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.add_signal_handler(sig, stop_event.set)
                except NotImplementedError:
                    pass
            if repl_enabled:
                await _run_repl(player=player, clock_scene=clock_scene, transition_ms=transition_ms)
            else:
                await stop_event.wait()
        finally:
            stop_event.set()
            for task in (watcher, consumer, theme_monitor):
                task.cancel()
            await asyncio.gather(watcher, consumer, theme_monitor, return_exceptions=True)
            if react_clock and hasattr(clock_scene, "stop"):
                await clock_scene.stop()
            if runtime_server is not None:
                runtime_server.stop()
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
                auto_info_seconds=max(0.1, args.auto_info_seconds),
                history_file=Path(args.history_file).expanduser(),
                theme=str(args.theme),
                theme_check_seconds=max(1.0, args.theme_check_seconds),
                react_clock=bool(args.react_clock),
                react_second_hand=bool(args.react_second_hand),
                react_frame_workers=max(1, args.react_frame_workers),
                debug=bool(args.debug),
                no_repl=bool(args.no_repl),
            )
        )
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
