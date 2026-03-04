#!/usr/bin/env python3
"""Transition showcase built on the v3 scene runtime."""

from __future__ import annotations

import argparse
import asyncio
import os
import time
from typing import Optional, Sequence

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
    TextStyle,
    header_layout,
    info_layout_from_json,
    list_scene_fonts,
)
from pypixoo.info_dsl import BorderConfig
from pypixoo.raster import AsyncRasterClient, PixooFrameSink
from pypixoo.scene import QueueItem, RenderContext, ScenePlayer
from pypixoo.transitions import TransitionSpec

load_dotenv()
DEFAULT_IP = os.environ.get("PIXOO_DEVICE_IP") or os.environ.get("PIXOO_IP") or "192.168.0.37"


def _dynamic_uptime(ctx: RenderContext) -> str:
    return f"{int(ctx.monotonic_s) % 100:02d}s"


def _dynamic_clock(ctx: RenderContext) -> str:
    return time.strftime("%H:%M:%S", time.localtime(ctx.epoch_s))


def _default_info_layout(
    *,
    title: str,
    font: str,
    header_height: int,
    header_border: bool,
    header_border_thickness: int,
    header_border_color: tuple[int, int, int],
) -> InfoLayout:
    body_rows = [
        TextRow(
            height=10,
            style=TextStyle(font=font, color=(145, 145, 145)),
            content="HOST-RASTER INFO DSL",
        ),
        TextRow(
            height=10,
            align="center",
            style=TextStyle(font=font, color=(120, 120, 120)),
            content=_dynamic_clock,
        ),
        TableRow(
            height=10,
            default_style=TextStyle(font=font, color=(110, 110, 110)),
            cells=[TableCell("STATE"), TableCell("OK", color=(160, 160, 160))],
            column_align=["left", "right"],
            block_align="center",
        ),
        TableRow(
            height=10,
            default_style=TextStyle(font=font, color=(110, 110, 110)),
            cells=[TableCell("UP"), TableCell(_dynamic_uptime, color=(160, 160, 160))],
            column_align=["left", "right"],
            block_align="center",
        ),
    ]
    return header_layout(
        title=title,
        font=font,
        height=header_height,
        border=BorderConfig(
            enabled=header_border,
            thickness=header_border_thickness,
            color=header_border_color,
        ),
        body_rows=body_rows,
        body_background_color=(0, 0, 0),
    )


def _load_info_layout_json(raw: str) -> InfoLayout:
    candidate = os.path.expanduser(raw)
    if os.path.exists(candidate):
        with open(candidate, "r", encoding="utf-8") as f:
            return info_layout_from_json(f.read())
    return info_layout_from_json(raw)


async def run_demo(
    *,
    ip: str,
    fps: int,
    duration_ms: int,
    hold_ms: int,
    mode: str,
    switch_seconds: float,
    info_title: str,
    info_font: str,
    info_header_height: int,
    info_header_border: bool,
    info_header_border_thickness: int,
    info_header_border_color: tuple[int, int, int],
    info_layout_json: Optional[str],
    run_seconds: float,
    transitions: Sequence[str],
) -> None:
    pixoo = Pixoo(ip)
    if not pixoo.connect():
        raise SystemExit(f"Failed to connect to Pixoo at {ip}")

    try:
        sink = PixooFrameSink(pixoo, reconnect=True)
        raster = AsyncRasterClient(sink)
        player = ScenePlayer(raster, fps=max(1, fps))

        style = clock._style_from_args(clock.build_parser(ip_default=ip).parse_args([]))
        scene_clock = ClockScene(render_frame=lambda ts: clock.render_clock_frame(ts, style), name="clock")
        try:
            layout = (
                _load_info_layout_json(info_layout_json)
                if info_layout_json
                else _default_info_layout(
                    title=info_title,
                    font=info_font,
                    header_height=info_header_height,
                    header_border=info_header_border,
                    header_border_thickness=info_header_border_thickness,
                    header_border_color=info_header_border_color,
                )
            )
        except ValueError as e:
            raise SystemExit(f"Invalid --info-layout-json: {e}") from e
        scene_info = InfoScene(layout=layout, name="info")

        await player.set_scene(scene_clock)

        stop_event = asyncio.Event()

        async def _pingpong_producer() -> None:
            local_hold_ms = _derived_hold_ms(switch_seconds=switch_seconds, duration_ms=duration_ms)
            target = scene_info
            direction = "push_left"
            while not stop_event.is_set():
                if player.queue_depth < 2:
                    await player.enqueue(
                        QueueItem(
                            scene=target,
                            transition=TransitionSpec(kind=direction, duration_ms=duration_ms),
                            hold_ms=local_hold_ms,
                        )
                    )
                    if target is scene_info:
                        target = scene_clock
                        direction = "push_right"
                    else:
                        target = scene_info
                        direction = "push_left"
                await asyncio.sleep(0.05)

        producer_task = None
        if mode == "pingpong":
            producer_task = asyncio.create_task(_pingpong_producer())
        else:
            target = scene_info
            for kind in transitions:
                await player.enqueue(
                    QueueItem(
                        scene=target,
                        transition=TransitionSpec(kind=kind, duration_ms=duration_ms),
                        hold_ms=hold_ms,
                    )
                )
                target = scene_clock if target is scene_info else scene_info

        runner = asyncio.create_task(player.run())
        try:
            if run_seconds > 0:
                await asyncio.sleep(run_seconds)
            else:
                await asyncio.Event().wait()
        finally:
            stop_event.set()
            await player.stop()
            if producer_task is not None:
                producer_task.cancel()
                try:
                    await producer_task
                except asyncio.CancelledError:
                    pass
            await runner
    finally:
        pixoo.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scene transition demo")
    parser.add_argument("--ip", default=DEFAULT_IP)
    parser.add_argument("--mode", choices=["pingpong", "showcase"], default="pingpong")
    parser.add_argument("--fps", type=int, default=3)
    parser.add_argument("--duration-ms", type=int, default=600)
    parser.add_argument("--hold-ms", type=int, default=600)
    parser.add_argument("--switch-seconds", type=float, default=5.0)
    parser.add_argument("--info-title", default="INFO")
    parser.add_argument(
        "--info-font",
        default="tiny5",
        choices=list_scene_fonts(),
        help="Scene-render font for info header title",
    )
    parser.add_argument("--info-header-height", type=int, default=12)
    parser.add_argument(
        "--info-header-border",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--info-header-border-thickness", type=int, default=1)
    parser.add_argument("--info-header-border-color", default="#3c3c3c")
    parser.add_argument(
        "--info-layout-json",
        default=None,
        help="Info layout JSON string or path to JSON file.",
    )
    parser.add_argument("--run-seconds", type=float, default=0.0, help="0 means run until Ctrl+C")
    parser.add_argument("--all-transitions", action="store_true")
    return parser


def _derived_hold_ms(*, switch_seconds: float, duration_ms: int) -> int:
    target_ms = int(round(max(0.5, switch_seconds) * 1000.0))
    return max(0, target_ms - duration_ms)


def main() -> None:
    args = build_parser().parse_args()
    transitions = [
        "cross_fade",
        "push_left",
        "push_right",
        "push_up",
        "push_down",
        "slide_over_left",
        "slide_over_right",
        "slide_over_up",
        "slide_over_down",
        "wipe_left",
        "wipe_right",
        "wipe_up",
        "wipe_down",
    ]
    if not args.all_transitions:
        transitions = ["cross_fade", "push_left", "slide_over_left", "wipe_left"]

    asyncio.run(
        run_demo(
            ip=args.ip,
            fps=args.fps,
            duration_ms=args.duration_ms,
            hold_ms=args.hold_ms,
            mode=args.mode,
            switch_seconds=args.switch_seconds,
            info_title=args.info_title,
            info_font=args.info_font,
            info_header_height=max(1, args.info_header_height),
            info_header_border=args.info_header_border,
            info_header_border_thickness=max(1, args.info_header_border_thickness),
            info_header_border_color=clock.parse_color(args.info_header_border_color),
            info_layout_json=args.info_layout_json,
            run_seconds=args.run_seconds,
            transitions=transitions,
        )
    )


if __name__ == "__main__":
    main()
