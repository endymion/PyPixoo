#!/usr/bin/env python3
"""Experimental React-backed clock/info demo via Storybook iframe rendering.

This demo keeps the proven ScenePlayer transition runtime, but sources scene
pixels from Storybook React stories instead of host-raster Python drawing.
It is intentionally isolated from demos/kanbus_clock.py.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

from dotenv import load_dotenv

from pypixoo import FrameRenderer, Pixoo, WebFrameSource
from pypixoo.buffer import Buffer
from pypixoo.raster import AsyncRasterClient, PixooFrameSink
from pypixoo.scene import LayerNode, QueueItem, RenderContext, ScenePlayer
from pypixoo.transitions import TransitionSpec

load_dotenv()

DEFAULT_IP = os.environ.get("PIXOO_DEVICE_IP") or os.environ.get("PIXOO_IP") or "192.168.0.37"
DEFAULT_STORYBOOK = os.environ.get("PIXOO_STORYBOOK_URL") or "http://localhost:6006/iframe.html"
DEFAULT_COMMENT_STORY_IDS: tuple[str, ...] = (
    "pixoo-kanbusclockcards--comment-task-without-parent",
    "pixoo-kanbusclockcards--comment-task-with-parent",
    "pixoo-kanbusclockcards--comment-story-without-parent",
    "pixoo-kanbusclockcards--comment-story-with-parent",
    "pixoo-kanbusclockcards--comment-bug-without-parent",
    "pixoo-kanbusclockcards--comment-bug-with-parent",
    "pixoo-kanbusclockcards--comment-epic-without-parent",
    "pixoo-kanbusclockcards--comment-epic-with-parent",
)


def _log(message: str) -> None:
    now = datetime.now().strftime("%H:%M:%S")
    print(f"{now} {message}", flush=True)


def _storybook_url(base_iframe: str, story_id: str, args: dict[str, Any]) -> str:
    pairs: list[str] = []
    for key, value in args.items():
        if isinstance(value, bool):
            rendered = "true" if value else "false"
        else:
            rendered = str(value)
        pairs.append(f"{key}:{rendered}")
    query = {"id": story_id}
    if pairs:
        query["args"] = ";".join(pairs)
    return f"{base_iframe}?{urlencode(query)}"


def _threshold_buffer(buf: Buffer, *, threshold: int) -> Buffer:
    """Convert a frame to hard on/off luminance to remove edge blur."""
    value = max(0, min(255, int(threshold)))
    out = list(buf.data)
    for i in range(0, len(out), 3):
        lum = (out[i] + out[i + 1] + out[i + 2]) / 3
        v = 255 if lum >= value else 0
        out[i] = v
        out[i + 1] = v
        out[i + 2] = v
    return Buffer.from_flat_list(out)


def _render_story_frame(
    url: str,
    *,
    t: float = 0.0,
    browser_mode: str = "per_frame",
    device_scale_factor: int = 3,
    downsample_mode: str = "nearest",
    threshold: int | None = None,
) -> Buffer:
    source = WebFrameSource(
        url=url,
        timestamps=[t],
        duration_per_frame_ms=100,
        browser_mode=browser_mode,
        timestamp_param="t",
        viewport_size=64,
        device_scale_factor=device_scale_factor,
        downsample_mode=downsample_mode,
    )
    sequence = FrameRenderer([source]).precompute()
    frame = sequence.frames[0].image
    if threshold is not None:
        frame = _threshold_buffer(frame, threshold=threshold)
    return frame


@dataclass
class _CachedFrame:
    key: str
    buffer: Buffer


class StorybookClockScene:
    name = "react-clock"

    def __init__(
        self,
        *,
        storybook_iframe: str,
        story_id: str,
        browser_mode: str,
        show_second_hand: bool,
    ) -> None:
        self._storybook_iframe = storybook_iframe
        self._story_id = story_id
        self._browser_mode = browser_mode
        self._show_second_hand = show_second_hand
        self._cache: _CachedFrame | None = None
        self._refresh_task: asyncio.Task | None = None
        self._stop_refresh = asyncio.Event()

    def _render_clock_sync(self, epoch_s: float) -> Buffer:
        local = time.localtime(epoch_s)
        second_bucket = int(epoch_s)
        key = f"{local.tm_hour}:{local.tm_min}:{local.tm_sec}:{second_bucket}"
        url = _storybook_url(
            self._storybook_iframe,
            self._story_id,
            {
                "hour": local.tm_hour % 12,
                "minute": local.tm_min,
                "second": local.tm_sec,
                "showSecondHand": self._show_second_hand,
            },
        )
        buf = _render_story_frame(
            url,
            t=(local.tm_sec % 60) / 60.0,
            browser_mode=self._browser_mode,
            device_scale_factor=3,
            downsample_mode="box",
        )
        self._cache = _CachedFrame(key=key, buffer=buf)
        return buf

    def _render_clock_cached(self) -> Buffer:
        if self._cache is None:
            return Buffer(width=64, height=64, data=tuple([0] * (64 * 64 * 3)))
        return self._cache.buffer

    async def _refresh_loop(self) -> None:
        """Refresh cached clock frame out-of-band so render() stays cheap."""
        while not self._stop_refresh.is_set():
            now = time.time()
            local = time.localtime(now)
            key = f"{local.tm_hour}:{local.tm_min}:{local.tm_sec}:{int(now)}"
            if self._cache is None or self._cache.key != key:
                try:
                    await asyncio.to_thread(self._render_clock_sync, now)
                except Exception as exc:  # pragma: no cover - runtime/device timing
                    _log(f"clock refresh skipped: {exc}")
            await asyncio.sleep(0.2)

    async def start(self) -> None:
        if self._refresh_task is not None and not self._refresh_task.done():
            return
        self._stop_refresh.clear()
        if self._cache is None:
            try:
                await asyncio.to_thread(self._render_clock_sync, time.time())
            except Exception as exc:  # pragma: no cover - runtime/device timing
                _log(f"clock warmup skipped: {exc}")
        self._refresh_task = asyncio.create_task(self._refresh_loop())

    async def stop(self) -> None:
        self._stop_refresh.set()
        if self._refresh_task is not None:
            self._refresh_task.cancel()
            await asyncio.gather(self._refresh_task, return_exceptions=True)
            self._refresh_task = None

    def layers(self, ctx: RenderContext) -> list[LayerNode]:
        scene = self

        class _Layer:
            name = "react-clock-layer"

            def render(self, render_ctx: RenderContext) -> Buffer:
                return scene._render_clock_cached()

        return [LayerNode(id="react-clock-root", layer=_Layer(), z=0)]

    def on_enter(self) -> None:
        _log("entered React clock scene")

    def on_exit(self) -> None:
        return


class StorybookInfoScene:
    def __init__(
        self,
        *,
        storybook_iframe: str,
        story_id: str,
        browser_mode: str,
        threshold: int | None,
    ) -> None:
        self.name = f"react-info:{story_id}"
        self._storybook_iframe = storybook_iframe
        self._story_id = story_id
        self._browser_mode = browser_mode
        self._threshold = threshold
        self._cache: Buffer | None = None

    def _render_info(self) -> Buffer:
        if self._cache is not None:
            return self._cache
        url = _storybook_url(self._storybook_iframe, self._story_id, {})
        self._cache = _render_story_frame(
            url,
            t=0.0,
            browser_mode=self._browser_mode,
            device_scale_factor=1,
            downsample_mode="nearest",
            threshold=self._threshold,
        )
        return self._cache

    def layers(self, ctx: RenderContext) -> list[LayerNode]:
        scene = self

        class _Layer:
            name = "react-info-layer"

            def render(self, render_ctx: RenderContext) -> Buffer:
                return scene._render_info()

        return [LayerNode(id="react-info-root", layer=_Layer(), z=0)]

    def on_enter(self) -> None:
        _log(f"entered React info scene ({self._story_id})")

    def on_exit(self) -> None:
        return


async def run(args: argparse.Namespace) -> None:
    pixoo = Pixoo(args.ip)
    if not pixoo.connect():
        raise SystemExit(f"Failed to connect to Pixoo at {args.ip}")

    try:
        sink = PixooFrameSink(pixoo, reconnect=True)
        raster = AsyncRasterClient(sink)
        player = ScenePlayer(raster, fps=max(1, args.fps))

        scene_clock = StorybookClockScene(
            storybook_iframe=args.storybook_iframe,
            story_id=args.clock_story_id,
            browser_mode=args.browser_mode,
            show_second_hand=args.second_hand,
        )
        info_story_ids = [s.strip() for s in args.info_story_ids.split(",") if s.strip()]
        if not info_story_ids:
            raise SystemExit("No info story ids configured. Pass --info-story-ids.")
        info_scenes = [
            StorybookInfoScene(
                storybook_iframe=args.storybook_iframe,
                story_id=story_id,
                browser_mode=args.browser_mode,
                threshold=(None if args.info_threshold < 0 else args.info_threshold),
            )
            for story_id in info_story_ids
        ]

        await scene_clock.start()
        await player.set_scene(scene_clock)
        runner = asyncio.create_task(player.run())
        try:
            hold_ms = max(0, int(round(args.switch_seconds * 1000)) - args.transition_ms)
            sequence: list[object] = [*info_scenes, scene_clock]
            cursor = 0
            while True:
                if player.queue_depth < 2:
                    target = sequence[cursor]
                    cursor = (cursor + 1) % len(sequence)
                    await player.enqueue(
                        QueueItem(
                            scene=target,
                            transition=TransitionSpec(kind="push_left", duration_ms=args.transition_ms),
                            hold_ms=hold_ms,
                        )
                    )
                await asyncio.sleep(0.1)
        finally:
            await scene_clock.stop()
            await player.stop()
            await runner
    finally:
        pixoo.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Experimental React-backed clock/info transitions via Storybook."
    )
    parser.add_argument("--ip", default=DEFAULT_IP, help=f"Pixoo IP (default: {DEFAULT_IP})")
    parser.add_argument(
        "--storybook-iframe",
        default=DEFAULT_STORYBOOK,
        help=f"Storybook iframe base URL (default: {DEFAULT_STORYBOOK})",
    )
    parser.add_argument(
        "--clock-story-id",
        default="pixoo-clock--pixooclock-default",
        help="Story ID for clock scene.",
    )
    parser.add_argument(
        "--info-story-ids",
        default=",".join(DEFAULT_COMMENT_STORY_IDS),
        help="Comma-separated Story IDs for info scenes; cycled in order between clock appearances.",
    )
    parser.add_argument("--fps", type=int, default=6, help="ScenePlayer output FPS.")
    parser.add_argument("--switch-seconds", type=float, default=5.0, help="Seconds between scene swaps.")
    parser.add_argument("--transition-ms", type=int, default=1200, help="Transition duration.")
    parser.add_argument(
        "--browser-mode",
        choices=["persistent", "per_frame"],
        default="per_frame",
        help="WebFrameSource browser mode.",
    )
    parser.add_argument(
        "--info-threshold",
        type=int,
        default=-1,
        help="Luminance threshold for info scene text hardening. Set -1 to disable.",
    )
    parser.add_argument(
        "--second-hand",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Enable second hand in clock story args. Default: disabled.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    info_count = len([s for s in args.info_story_ids.split(",") if s.strip()])
    _log(
        "Starting React experiment (clock story=%s info scenes=%d)"
        % (args.clock_story_id, info_count)
    )
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
