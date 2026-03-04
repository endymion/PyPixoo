"""Raster compositing helpers used by scene transitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from pypixoo.buffer import Buffer


ClipRect = tuple[int, int, int, int]


@dataclass(frozen=True)
class RenderedLayer:
    """Concrete layer sample ready for compositing."""

    buffer: Buffer
    x: float = 0.0
    y: float = 0.0
    opacity: float = 1.0
    z: int = 0
    visible: bool = True
    clip: Optional[ClipRect] = None


def blank_buffer(
    *,
    width: int = 64,
    height: int = 64,
    color: tuple[int, int, int] = (0, 0, 0),
) -> Buffer:
    """Create a solid RGB buffer."""
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be > 0")
    data = [component for _ in range(width * height) for component in color]
    return Buffer(width=width, height=height, data=tuple(data))


def _blend_channel(base: int, top: int, alpha: float) -> int:
    return int(round((base * (1.0 - alpha)) + (top * alpha)))


def _clip_contains(clip: Optional[ClipRect], x: int, y: int) -> bool:
    if clip is None:
        return True
    cx, cy, cw, ch = clip
    return cx <= x < (cx + cw) and cy <= y < (cy + ch)


def _composite_layer(
    canvas: list[int],
    layer: RenderedLayer,
    *,
    width: int,
    height: int,
) -> None:
    if not layer.visible:
        return
    opacity = max(0.0, min(1.0, layer.opacity))
    if opacity <= 0:
        return

    src = layer.buffer
    ox = int(round(layer.x))
    oy = int(round(layer.y))

    for sy in range(src.height):
        dy = oy + sy
        if dy < 0 or dy >= height:
            continue
        for sx in range(src.width):
            dx = ox + sx
            if dx < 0 or dx >= width:
                continue
            if not _clip_contains(layer.clip, dx, dy):
                continue

            src_idx = (sy * src.width + sx) * 3
            dst_idx = (dy * width + dx) * 3
            sr = src.data[src_idx]
            sg = src.data[src_idx + 1]
            sb = src.data[src_idx + 2]

            if opacity >= 1.0:
                canvas[dst_idx] = sr
                canvas[dst_idx + 1] = sg
                canvas[dst_idx + 2] = sb
                continue

            canvas[dst_idx] = _blend_channel(canvas[dst_idx], sr, opacity)
            canvas[dst_idx + 1] = _blend_channel(canvas[dst_idx + 1], sg, opacity)
            canvas[dst_idx + 2] = _blend_channel(canvas[dst_idx + 2], sb, opacity)


def compose_layers(
    layers: Sequence[RenderedLayer],
    *,
    width: int = 64,
    height: int = 64,
    background: tuple[int, int, int] = (0, 0, 0),
) -> Buffer:
    """Composite sorted layers into a single buffer."""
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be > 0")
    canvas = [component for _ in range(width * height) for component in background]
    for layer in sorted(layers, key=lambda item: item.z):
        _composite_layer(canvas, layer, width=width, height=height)
    return Buffer(width=width, height=height, data=tuple(canvas))


def flatten_scene_buffers(
    scene_buffers: Iterable[Buffer],
    *,
    width: int = 64,
    height: int = 64,
) -> Buffer:
    """Blend multiple full-screen buffers in order with full opacity."""
    return compose_layers(
        [RenderedLayer(buffer=buf, z=index) for index, buf in enumerate(scene_buffers)],
        width=width,
        height=height,
    )
