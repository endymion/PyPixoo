"""CLI for PyPixoo native V2 workflows."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import List

from PIL import Image
from dotenv import load_dotenv

from pypixoo import (
    CycleItem,
    GifFrame,
    GifSequence,
    GifSource,
    Pixoo,
    UploadMode,
    DeviceInUseError,
    TextOverlay,
)
from pypixoo.fonts import BuiltinFont
from pypixoo.buffer import Buffer
from pypixoo.color import parse_color


DEFAULT_IP = "192.168.0.37"


def _resolve_default_ip() -> str:
    return os.environ.get("PIXOO_DEVICE_IP") or os.environ.get("PIXOO_IP") or DEFAULT_IP


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


def main() -> None:
    load_dotenv()
    default_ip = _resolve_default_ip()
    parser = argparse.ArgumentParser(
        prog="pypixoo",
        description="PyPixoo CLI for Divoom Pixoo 64.",
    )
    parser.add_argument(
        "--ip",
        default=default_ip,
        help="Device IP (default: from PIXOO_DEVICE_IP, PIXOO_IP, or 192.168.0.37)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    fill_p = subparsers.add_parser("fill", help="Fill the display with a solid color")
    fill_p.add_argument("color", help="Color: hex (FF00FF, f0f, #f0f) or name (fuchsia, red)")
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
    text_p.add_argument("--color", default="#FFFF00", help="Font color hex")
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

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
