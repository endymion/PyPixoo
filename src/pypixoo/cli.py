"""CLI for PyPixoo native V2 workflows."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import List

from PIL import Image

from pypixoo import (
    CycleItem,
    GifFrame,
    GifSequence,
    GifSource,
    Pixoo,
    UploadMode,
    DeviceInUseError,
)
from pypixoo.buffer import Buffer
from pypixoo.color import parse_color


DEFAULT_IP = "192.168.0.37"


def _require_real_device() -> None:
    if os.environ.get("PIXOO_REAL_DEVICE") != "1":
        print("error: Set PIXOO_REAL_DEVICE=1 to send to a real device.", file=sys.stderr)
        sys.exit(1)


def _connect(ip: str) -> Pixoo:
    _require_real_device()
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
    parser = argparse.ArgumentParser(
        prog="pypixoo",
        description="PyPixoo CLI for Divoom Pixoo 64. Set PIXOO_REAL_DEVICE=1 to use a real device.",
    )
    parser.add_argument(
        "--ip",
        default=DEFAULT_IP,
        help=f"Device IP (default: {DEFAULT_IP})",
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
