"""CLI for PyPixoo layered v3 workflows."""

from __future__ import annotations

import asyncio
import argparse
import os
import sys
import time
from pathlib import Path
from typing import List, Optional

from PIL import Image
from dotenv import load_dotenv

from pypixoo import (
    CycleItem,
    InfoScene,
    ClockScene,
    GifFrame,
    GifSequence,
    GifSource,
    Pixoo,
    UploadMode,
    DeviceInUseError,
    InfoLayout,
    TableCell,
    TableRow,
    TextOverlay,
    TextRow,
    TextStyle,
    header_layout,
    info_layout_from_json,
    list_scene_fonts,
)
from pypixoo.fonts import BuiltinFont
from pypixoo.info_dsl import BorderConfig as InfoBorderConfig
from pypixoo.buffer import Buffer
from pypixoo.color import parse_color
from pypixoo.raster import AsyncRasterClient, PixooFrameSink, RasterClient
from pypixoo.scene import QueueItem, RenderContext, ScenePlayer
from pypixoo.transitions import TransitionSpec


DEFAULT_IP = "192.168.0.37"


def _resolve_default_ip() -> str:
    return os.environ.get("PIXOO_DEVICE_IP") or os.environ.get("PIXOO_IP") or DEFAULT_IP


def _buffer_from_color(color: tuple[int, int, int]) -> Buffer:
    return Buffer.from_flat_list([component for _ in range(64 * 64) for component in color])


def _dynamic_uptime(ctx: RenderContext) -> str:
    return f"UP {int(ctx.monotonic_s) % 100:02d}s"


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
            style=TextStyle(font=font, color=(150, 150, 150)),
            content="Scene runtime: host-raster",
        ),
        TextRow(
            height=10,
            align="center",
            style=TextStyle(font=font, color=(120, 120, 120)),
            content=_dynamic_clock,
        ),
        TableRow(
            height=10,
            default_style=TextStyle(font=font, color=(120, 120, 120)),
            cells=[TableCell("NET"), TableCell("OK", color=(150, 150, 150))],
            column_align=["left", "right"],
            block_align="center",
        ),
        TableRow(
            height=10,
            default_style=TextStyle(font=font, color=(120, 120, 120)),
            cells=[TableCell("UP"), TableCell(_dynamic_uptime, color=(150, 150, 150))],
            column_align=["left", "right"],
            block_align="center",
        ),
    ]
    return header_layout(
        title=title,
        font=font,
        height=header_height,
        border=InfoBorderConfig(
            enabled=header_border,
            thickness=max(1, header_border_thickness),
            color=header_border_color,
        ),
        body_rows=body_rows,
        body_background_color=(0, 0, 0),
    )


def _load_info_layout_json(raw: str) -> InfoLayout:
    candidate = Path(raw)
    if candidate.exists():
        return info_layout_from_json(candidate.read_text(encoding="utf-8"))
    return info_layout_from_json(raw)


def _build_clock_scene():
    from demos import pixooclock as pixooclock_demo

    parser = pixooclock_demo.build_parser(ip_default=_resolve_default_ip())
    style = pixooclock_demo._style_from_args(parser.parse_args([]))
    return ClockScene(
        name="clock",
        render_frame=lambda ts: pixooclock_demo.render_clock_frame(ts, style),
    )


def _build_info_scene(
    *,
    title: str,
    font: str,
    header_height: int,
    header_border: bool,
    header_border_thickness: int,
    header_border_color: tuple[int, int, int],
    info_layout_json: Optional[str] = None,
) -> InfoScene:
    layout = (
        _load_info_layout_json(info_layout_json)
        if info_layout_json
        else _default_info_layout(
            title=title,
            font=font,
            header_height=header_height,
            header_border=header_border,
            header_border_thickness=header_border_thickness,
            header_border_color=header_border_color,
        )
    )
    return InfoScene(name="info", layout=layout)


def _build_scene(
    scene_name: str,
    accent: tuple[int, int, int],
    *,
    info_title: str = "INFO",
    info_font: str = "tiny5",
    info_header_height: int = 12,
    info_header_border: bool = True,
    info_header_border_thickness: int = 1,
    info_header_border_color: tuple[int, int, int] = (60, 60, 60),
    info_layout_json: Optional[str] = None,
):
    if scene_name == "clock":
        return _build_clock_scene()
    if scene_name == "info":
        return _build_info_scene(
            title=info_title,
            font=info_font,
            header_height=info_header_height,
            header_border=info_header_border,
            header_border_thickness=info_header_border_thickness,
            header_border_color=info_header_border_color,
            info_layout_json=info_layout_json,
        )
    if scene_name == "solid":
        return InfoScene(
            name="solid",
            layout=InfoLayout(rows=[], background_color=accent),
        )
    raise ValueError(f"unsupported scene name: {scene_name}")


def _connect(ip: str) -> Pixoo:
    pixoo = Pixoo(ip)
    try:
        if not pixoo.connect():
            print(f"error: Failed to connect to {ip}", file=sys.stderr)
            sys.exit(1)
        return pixoo
    except DeviceInUseError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


def _buffer_from_image(path: Path) -> Buffer:
    img = Image.open(path).convert("RGB")
    if img.size != (64, 64):
        img = img.resize((64, 64), Image.Resampling.NEAREST)
    data = [c for pixel in img.getdata() for c in pixel]
    return Buffer.from_flat_list(data)


def _sequence_from_image_paths(paths: List[Path], speed_ms: int) -> GifSequence:
    frames = [GifFrame(image=_buffer_from_image(path), duration_ms=speed_ms) for path in paths]
    return GifSequence(frames=frames, speed_ms=speed_ms)


def _parse_sequence_spec(spec: str, default_speed_ms: int) -> GifSequence:
    speed_ms = default_speed_ms
    csv = spec
    if ":" in spec:
        lhs, rhs = spec.split(":", 1)
        if lhs.strip().isdigit():
            speed_ms = int(lhs.strip())
            csv = rhs
    raw_paths = [p.strip() for p in csv.split(",") if p.strip()]
    if not raw_paths:
        raise ValueError("sequence spec requires at least one image path")
    paths = [Path(p) for p in raw_paths]
    for path in paths:
        if not path.exists():
            raise ValueError(f"sequence image not found: {path}")
    return _sequence_from_image_paths(paths, speed_ms)


def cmd_fill(ip: str, color: str) -> None:
    r, g, b = parse_color(color)
    pixoo = _connect(ip)
    try:
        pixoo.fill(r, g, b)
        pixoo.push()
    finally:
        pixoo.close()


def cmd_load_image(ip: str, path: Path) -> None:
    if not path.exists():
        print(f"error: File not found: {path}", file=sys.stderr)
        sys.exit(1)
    pixoo = _connect(ip)
    try:
        pixoo.load_image(path)
        pixoo.push()
    finally:
        pixoo.close()


def cmd_upload_sequence(
    ip: str,
    image_paths: List[Path],
    speed_ms: int,
    mode: str,
    chunk_size: int,
) -> None:
    for path in image_paths:
        if not path.exists():
            print(f"error: File not found: {path}", file=sys.stderr)
            sys.exit(1)
    sequence = _sequence_from_image_paths(image_paths, speed_ms)
    pixoo = _connect(ip)
    try:
        pixoo.upload_sequence(
            sequence,
            mode=UploadMode(mode),
            chunk_size=chunk_size,
        )
    finally:
        pixoo.close()


def cmd_play_gif_url(ip: str, url: str) -> None:
    pixoo = _connect(ip)
    try:
        pixoo.play_gif(GifSource.url(url))
    finally:
        pixoo.close()


def cmd_play_gif_file(ip: str, path: str) -> None:
    pixoo = _connect(ip)
    try:
        pixoo.play_gif(GifSource.tf_file(path))
    finally:
        pixoo.close()


def cmd_play_gif_dir(ip: str, path: str) -> None:
    pixoo = _connect(ip)
    try:
        pixoo.play_gif(GifSource.tf_directory(path))
    finally:
        pixoo.close()


def cmd_list_fonts() -> None:
    registry = Pixoo("0.0.0.0").list_fonts()
    for font in registry.fonts:
        name = font.name or ""
        width = font.width or ""
        height = font.height or ""
        print(f"{font.id}\t{name}\t{width}x{height}")


def _parse_font(value: str) -> int:
    if value.isdigit():
        return int(value)
    return int(BuiltinFont.from_name(value))


def cmd_text_overlay(
    ip: str,
    text: str,
    x: int,
    y: int,
    font: str,
    width: int,
    speed: int,
    color: str,
    align: int,
    direction: int,
) -> None:
    pixoo = _connect(ip)
    try:
        overlay = TextOverlay(
            text=text,
            x=x,
            y=y,
            font=_parse_font(font),
            text_width=width,
            speed=speed,
            color=color,
            align=align,
            direction=direction,
        )
        pixoo.send_text_overlay(overlay)
    finally:
        pixoo.close()


def cmd_clear_text(ip: str) -> None:
    pixoo = _connect(ip)
    try:
        pixoo.clear_text_overlay()
    finally:
        pixoo.close()


def cmd_raw_command(ip: str, command: str, kv_pairs: List[str]) -> None:
    payload = {}
    for pair in kv_pairs:
        if "=" not in pair:
            print(f"error: raw command params must be key=value, got {pair}", file=sys.stderr)
            sys.exit(1)
        key, value = pair.split("=", 1)
        if value.isdigit():
            payload[key] = int(value)
        else:
            payload[key] = value
    pixoo = _connect(ip)
    try:
        pixoo.command(command, payload)
    finally:
        pixoo.close()


def cmd_cycle(
    ip: str,
    item_specs: List[str],
    loop: int,
    mode: str,
    chunk_size: int,
    default_speed_ms: int,
) -> None:
    if not item_specs:
        print("error: cycle requires at least one --item", file=sys.stderr)
        sys.exit(1)

    items: List[CycleItem] = []
    for spec in item_specs:
        if spec.startswith("url="):
            items.append(CycleItem(source=GifSource.url(spec[len("url=") :])))
        elif spec.startswith("file="):
            items.append(CycleItem(source=GifSource.tf_file(spec[len("file=") :])))
        elif spec.startswith("dir="):
            items.append(CycleItem(source=GifSource.tf_directory(spec[len("dir=") :])))
        elif spec.startswith("sequence="):
            sequence_spec = spec[len("sequence=") :]
            try:
                sequence = _parse_sequence_spec(sequence_spec, default_speed_ms)
            except ValueError as e:
                print(f"error: {e}", file=sys.stderr)
                sys.exit(1)
            items.append(
                CycleItem(
                    sequence=sequence,
                    upload_mode=UploadMode(mode),
                    chunk_size=chunk_size,
                )
            )
        else:
            print(
                "error: --item must start with one of url=, file=, dir=, sequence=",
                file=sys.stderr,
            )
            sys.exit(1)

    resolved_loop = None if loop == 0 else loop

    pixoo = _connect(ip)
    try:
        handle = pixoo.start_cycle(items, loop=resolved_loop)
        if resolved_loop is None:
            try:
                while True:
                    time.sleep(0.2)
            except KeyboardInterrupt:
                handle.stop()
                handle.wait(2.0)
        else:
            handle.wait()
    finally:
        pixoo.close()


def cmd_raster_push(ip: str, color: str) -> None:
    rgb = parse_color(color)
    pixoo = _connect(ip)
    try:
        sink = PixooFrameSink(pixoo, reconnect=True)
        client = RasterClient(sink)
        client.push_frame(_buffer_from_color(rgb))
    finally:
        pixoo.close()


def cmd_raster_stream(
    ip: str,
    fps: int,
    duration_s: float,
    primary_color: str,
    secondary_color: str,
) -> None:
    if duration_s <= 0:
        print("error: --duration must be > 0", file=sys.stderr)
        sys.exit(1)
    a = parse_color(primary_color)
    b = parse_color(secondary_color)
    frames = [_buffer_from_color(a), _buffer_from_color(b)]
    state = {"i": 0}

    def _next() -> Buffer:
        idx = state["i"] % len(frames)
        state["i"] += 1
        return frames[idx]

    pixoo = _connect(ip)
    try:
        sink = PixooFrameSink(pixoo, reconnect=True)
        client = RasterClient(sink)
        stats = client.stream_frames(_next, fps=fps, duration_s=duration_s)
        print(
            f"frames={stats.frames_sent} late={stats.late_frames} "
            f"avg_push_ms={stats.avg_push_ms:.2f}"
        )
    finally:
        pixoo.close()


async def _run_scene_player_for_duration(player: ScenePlayer, duration_s: float) -> None:
    runner = asyncio.create_task(player.run())
    try:
        await asyncio.sleep(duration_s)
    finally:
        await player.stop()
        await runner


def cmd_scene_run(
    ip: str,
    scene_name: str,
    fps: int,
    duration_s: float,
    accent_color: str,
    info_title: str,
    info_font: str,
    info_header_height: int,
    info_header_border: bool,
    info_header_border_thickness: int,
    info_header_border_color: str,
    info_layout_json: Optional[str],
) -> None:
    if duration_s <= 0:
        print("error: --duration must be > 0", file=sys.stderr)
        sys.exit(1)

    accent = parse_color(accent_color)
    border_color = parse_color(info_header_border_color)
    pixoo = _connect(ip)
    try:
        sink = PixooFrameSink(pixoo, reconnect=True)
        raster = AsyncRasterClient(sink)
        player = ScenePlayer(raster, fps=fps)
        try:
            scene = _build_scene(
                scene_name,
                accent,
                info_title=info_title,
                info_font=info_font,
                info_header_height=info_header_height,
                info_header_border=info_header_border,
                info_header_border_thickness=info_header_border_thickness,
                info_header_border_color=border_color,
                info_layout_json=info_layout_json,
            )
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            sys.exit(1)
        asyncio.run(player.set_scene(scene))
        asyncio.run(_run_scene_player_for_duration(player, duration_s))
    finally:
        pixoo.close()


def cmd_scene_enqueue(
    ip: str,
    from_scene: str,
    to_scene: str,
    transition: str,
    duration_ms: int,
    hold_ms: int,
    fps: int,
    run_seconds: float,
    accent_color: str,
    info_title: str,
    info_font: str,
    info_header_height: int,
    info_header_border: bool,
    info_header_border_thickness: int,
    info_header_border_color: str,
    info_layout_json: Optional[str],
) -> None:
    if run_seconds <= 0:
        print("error: --run-seconds must be > 0", file=sys.stderr)
        sys.exit(1)
    accent = parse_color(accent_color)
    border_color = parse_color(info_header_border_color)
    pixoo = _connect(ip)
    try:
        sink = PixooFrameSink(pixoo, reconnect=True)
        raster = AsyncRasterClient(sink)
        player = ScenePlayer(raster, fps=fps)

        try:
            base_scene = _build_scene(
                from_scene,
                accent,
                info_title=info_title,
                info_font=info_font,
                info_header_height=info_header_height,
                info_header_border=info_header_border,
                info_header_border_thickness=info_header_border_thickness,
                info_header_border_color=border_color,
                info_layout_json=info_layout_json,
            )
            target_scene = _build_scene(
                to_scene,
                accent,
                info_title=info_title,
                info_font=info_font,
                info_header_height=info_header_height,
                info_header_border=info_header_border,
                info_header_border_thickness=info_header_border_thickness,
                info_header_border_color=border_color,
                info_layout_json=info_layout_json,
            )
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            sys.exit(1)
        spec = TransitionSpec(kind=transition, duration_ms=duration_ms)
        queue_item = QueueItem(scene=target_scene, transition=spec, hold_ms=hold_ms)

        async def _run() -> None:
            await player.set_scene(base_scene)
            await player.enqueue(queue_item)
            await _run_scene_player_for_duration(player, run_seconds)

        asyncio.run(_run())
    finally:
        pixoo.close()


def cmd_scene_demo(
    ip: str,
    fps: int,
    duration_ms: int,
    hold_ms: int,
    all_transitions: bool,
    run_seconds: float,
    accent_color: str,
    info_title: str,
    info_font: str,
    info_header_height: int,
    info_header_border: bool,
    info_header_border_thickness: int,
    info_header_border_color: str,
    info_layout_json: Optional[str],
) -> None:
    if run_seconds <= 0:
        print("error: --run-seconds must be > 0", file=sys.stderr)
        sys.exit(1)
    accent = parse_color(accent_color)
    border_color = parse_color(info_header_border_color)
    transition_kinds = [
        "cut",
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
    if not all_transitions:
        transition_kinds = ["cross_fade", "push_left", "slide_over_left", "wipe_left"]

    pixoo = _connect(ip)
    try:
        sink = PixooFrameSink(pixoo, reconnect=True)
        raster = AsyncRasterClient(sink)
        player = ScenePlayer(raster, fps=fps)
        scene_a = _build_scene("clock", accent)
        try:
            scene_b = _build_scene(
                "info",
                accent,
                info_title=info_title,
                info_font=info_font,
                info_header_height=info_header_height,
                info_header_border=info_header_border,
                info_header_border_thickness=info_header_border_thickness,
                info_header_border_color=border_color,
                info_layout_json=info_layout_json,
            )
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            sys.exit(1)

        async def _run() -> None:
            await player.set_scene(scene_a)
            current = scene_b
            for kind in transition_kinds:
                await player.enqueue(
                    QueueItem(
                        scene=current,
                        transition=TransitionSpec(kind=kind, duration_ms=duration_ms),
                        hold_ms=hold_ms,
                    )
                )
                current = scene_a if current is scene_b else scene_b
            await _run_scene_player_for_duration(player, run_seconds)

        asyncio.run(_run())
    finally:
        pixoo.close()


def main() -> None:
    load_dotenv()
    default_ip = _resolve_default_ip()
    parser = argparse.ArgumentParser(
        prog="pixoo",
        description="PyPixoo CLI (L0 transport, L1 raster, L2 scene) for Divoom Pixoo 64.",
    )
    parser.add_argument(
        "--ip",
        default=default_ip,
        help="Device IP (default: from PIXOO_DEVICE_IP, PIXOO_IP, or 192.168.0.37)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    fill_p = subparsers.add_parser("fill", help="Fill the display with a solid color")
    fill_p.add_argument(
        "color",
        help=(
            "Color: hex/rgb/name or Radix token "
            "(e.g. gray11, dark.gray11, grayDark11)"
        ),
    )
    fill_p.set_defaults(func=lambda ns: cmd_fill(ns.ip, ns.color))

    load_p = subparsers.add_parser("load-image", help="Load an image file (resized to 64x64) and push")
    load_p.add_argument("path", type=Path, help="Path to image file")
    load_p.set_defaults(func=lambda ns: cmd_load_image(ns.ip, ns.path))

    upload_p = subparsers.add_parser("upload-sequence", help="Upload a native HttpGif sequence")
    upload_p.add_argument("images", nargs="+", type=Path, help="Frame image paths in playback order")
    upload_p.add_argument("--speed-ms", type=int, default=100, help="PicSpeed in milliseconds")
    upload_p.add_argument(
        "--mode",
        choices=[UploadMode.FRAME_BY_FRAME.value, UploadMode.COMMAND_LIST.value],
        default=UploadMode.COMMAND_LIST.value,
        help="Upload transport mode",
    )
    upload_p.add_argument("--chunk-size", type=int, default=40, help="CommandList chunk size")
    upload_p.set_defaults(
        func=lambda ns: cmd_upload_sequence(ns.ip, ns.images, ns.speed_ms, ns.mode, ns.chunk_size)
    )

    play_url_p = subparsers.add_parser("play-gif-url", help="Play a GIF from a URL")
    play_url_p.add_argument("url", help="GIF URL")
    play_url_p.set_defaults(func=lambda ns: cmd_play_gif_url(ns.ip, ns.url))

    play_file_p = subparsers.add_parser("play-gif-file", help="Play a GIF from TF card file path")
    play_file_p.add_argument("path", help="TF path, e.g. divoom_gif/1.gif")
    play_file_p.set_defaults(func=lambda ns: cmd_play_gif_file(ns.ip, ns.path))

    play_dir_p = subparsers.add_parser("play-gif-dir", help="Play GIF directory from TF card")
    play_dir_p.add_argument("path", help="TF directory path, e.g. divoom_gif/")
    play_dir_p.set_defaults(func=lambda ns: cmd_play_gif_dir(ns.ip, ns.path))

    list_fonts_p = subparsers.add_parser("list-fonts", help="List built-in display list fonts")
    list_fonts_p.set_defaults(func=lambda ns: cmd_list_fonts())

    text_p = subparsers.add_parser("text-overlay", help="Send native text overlay")
    text_p.add_argument("text", help="Text to display")
    text_p.add_argument("--x", type=int, default=0, help="X position")
    text_p.add_argument("--y", type=int, default=0, help="Y position")
    text_p.add_argument("--font", default="font_4", help="Font id (0-7) or name (font_4)")
    text_p.add_argument("--width", type=int, default=64, help="Text width")
    text_p.add_argument("--speed", type=int, default=10, help="Scroll speed")
    text_p.add_argument(
        "--color",
        default="#FFFF00",
        help="Font color: hex/rgb/name or Radix token (e.g. gray11, dark.gray11)",
    )
    text_p.add_argument("--align", type=int, default=1, help="Align mode")
    text_p.add_argument("--direction", type=int, default=0, help="Scroll direction")
    text_p.set_defaults(
        func=lambda ns: cmd_text_overlay(
            ns.ip,
            ns.text,
            ns.x,
            ns.y,
            ns.font,
            ns.width,
            ns.speed,
            ns.color,
            ns.align,
            ns.direction,
        )
    )

    clear_text_p = subparsers.add_parser("clear-text", help="Clear text overlays")
    clear_text_p.set_defaults(func=lambda ns: cmd_clear_text(ns.ip))

    raw_p = subparsers.add_parser("raw-command", help="Send raw command payload")
    raw_p.add_argument("command", help="Command string, e.g. Device/SetHighLightMode")
    raw_p.add_argument("params", nargs="*", help="Key=value payload entries")
    raw_p.set_defaults(func=lambda ns: cmd_raw_command(ns.ip, ns.command, ns.params))

    cycle_p = subparsers.add_parser("cycle", help="Cycle native GIF items asynchronously")
    cycle_p.add_argument(
        "--item",
        action="append",
        default=[],
        help="Ordered item: url=<url> | file=<tf_file> | dir=<tf_dir> | sequence=<speed:path1,path2>",
    )
    cycle_p.add_argument("--loop", type=int, default=1, help="Loop count (0 means infinite)")
    cycle_p.add_argument(
        "--mode",
        choices=[UploadMode.FRAME_BY_FRAME.value, UploadMode.COMMAND_LIST.value],
        default=UploadMode.COMMAND_LIST.value,
        help="Upload transport for sequence cycle items",
    )
    cycle_p.add_argument("--chunk-size", type=int, default=40, help="CommandList chunk size")
    cycle_p.add_argument("--speed-ms", type=int, default=100, help="Default speed for sequence items")
    cycle_p.set_defaults(
        func=lambda ns: cmd_cycle(ns.ip, ns.item, ns.loop, ns.mode, ns.chunk_size, ns.speed_ms)
    )

    raster_p = subparsers.add_parser("raster", help="Low-level raster operations")
    raster_sub = raster_p.add_subparsers(dest="raster_command", required=True)

    raster_push_p = raster_sub.add_parser("push", help="Push a single solid-color frame")
    raster_push_p.add_argument(
        "--color",
        default="black",
        help="Frame color: hex/rgb/name or Radix token",
    )
    raster_push_p.set_defaults(func=lambda ns: cmd_raster_push(ns.ip, ns.color))

    raster_stream_p = raster_sub.add_parser("stream", help="Stream alternating color frames")
    raster_stream_p.add_argument("--fps", type=int, default=2, help="Stream frames per second")
    raster_stream_p.add_argument("--duration", type=float, default=5.0, help="Stream duration seconds")
    raster_stream_p.add_argument("--primary-color", default="black", help="Primary frame color")
    raster_stream_p.add_argument("--secondary-color", default="dark.gray8", help="Secondary frame color")
    raster_stream_p.set_defaults(
        func=lambda ns: cmd_raster_stream(
            ns.ip,
            ns.fps,
            ns.duration,
            ns.primary_color,
            ns.secondary_color,
        )
    )

    scene_p = subparsers.add_parser("scene", help="High-level scene runtime commands")
    scene_sub = scene_p.add_subparsers(dest="scene_command", required=True)

    def _add_info_scene_args(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--info-title", default="INFO")
        parser.add_argument(
            "--info-font",
            default="tiny5",
            choices=list_scene_fonts(),
            help="Scene-render font for InfoScene header title",
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
            help="Info layout JSON string or path to JSON file. Overrides --info-title/* layout sugar.",
        )

    scene_run_p = scene_sub.add_parser("run", help="Run a single scene")
    scene_run_p.add_argument("--scene", default="clock", choices=["clock", "info", "solid"])
    scene_run_p.add_argument("--fps", type=int, default=3)
    scene_run_p.add_argument("--duration", type=float, default=15.0, help="Run duration in seconds")
    scene_run_p.add_argument("--accent-color", default="dark.amber10")
    _add_info_scene_args(scene_run_p)
    scene_run_p.set_defaults(
        func=lambda ns: cmd_scene_run(
            ns.ip,
            ns.scene,
            ns.fps,
            ns.duration,
            ns.accent_color,
            ns.info_title,
            ns.info_font,
            ns.info_header_height,
            ns.info_header_border,
            ns.info_header_border_thickness,
            ns.info_header_border_color,
            ns.info_layout_json,
        )
    )

    scene_enqueue_p = scene_sub.add_parser("enqueue", help="Run one queued scene transition")
    scene_enqueue_p.add_argument("--from-scene", default="clock", choices=["clock", "info", "solid"])
    scene_enqueue_p.add_argument("--to-scene", default="info", choices=["clock", "info", "solid"])
    scene_enqueue_p.add_argument(
        "--transition",
        default="cross_fade",
        choices=[
            "cut",
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
        ],
    )
    scene_enqueue_p.add_argument("--duration-ms", type=int, default=600)
    scene_enqueue_p.add_argument("--hold-ms", type=int, default=500)
    scene_enqueue_p.add_argument("--fps", type=int, default=3)
    scene_enqueue_p.add_argument("--run-seconds", type=float, default=12.0)
    scene_enqueue_p.add_argument("--accent-color", default="dark.amber10")
    _add_info_scene_args(scene_enqueue_p)
    scene_enqueue_p.set_defaults(
        func=lambda ns: cmd_scene_enqueue(
            ns.ip,
            ns.from_scene,
            ns.to_scene,
            ns.transition,
            ns.duration_ms,
            ns.hold_ms,
            ns.fps,
            ns.run_seconds,
            ns.accent_color,
            ns.info_title,
            ns.info_font,
            ns.info_header_height,
            ns.info_header_border,
            ns.info_header_border_thickness,
            ns.info_header_border_color,
            ns.info_layout_json,
        )
    )

    scene_demo_p = scene_sub.add_parser("demo", help="Run transition showcase")
    scene_demo_p.add_argument("--fps", type=int, default=3)
    scene_demo_p.add_argument("--duration-ms", type=int, default=600)
    scene_demo_p.add_argument("--hold-ms", type=int, default=500)
    scene_demo_p.add_argument("--run-seconds", type=float, default=30.0)
    scene_demo_p.add_argument("--all-transitions", action="store_true")
    scene_demo_p.add_argument("--accent-color", default="dark.amber10")
    _add_info_scene_args(scene_demo_p)
    scene_demo_p.set_defaults(
        func=lambda ns: cmd_scene_demo(
            ns.ip,
            ns.fps,
            ns.duration_ms,
            ns.hold_ms,
            ns.all_transitions,
            ns.run_seconds,
            ns.accent_color,
            ns.info_title,
            ns.info_font,
            ns.info_header_height,
            ns.info_header_border,
            ns.info_header_border_thickness,
            ns.info_header_border_color,
            ns.info_layout_json,
        )
    )

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
