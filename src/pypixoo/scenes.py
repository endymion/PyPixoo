"""General-purpose scene implementations built on ScenePlayer protocols."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

from pypixoo.buffer import Buffer
from pypixoo.scene import LayerNode, RenderContext, Scene
from pypixoo.info_dsl import (
    BorderConfig,
    InfoLayout,
    InfoRow,
    TextRow,
    TextStyle,
    render_info_layout,
)


@dataclass(frozen=True)
class _BufferLayer:
    name: str
    renderer: Callable[[RenderContext], Buffer]

    def render(self, ctx: RenderContext) -> Buffer:
        return self.renderer(ctx)


class ClockScene:
    """Explicit scene wrapper for host-rendered clock frames."""

    def __init__(
        self,
        *,
        render_frame: Callable[[float], Buffer],
        name: str = "clock",
    ):
        self.name = name
        self._render_frame = render_frame
        self._layer = _BufferLayer(name=f"{name}-layer", renderer=self._render)

    def _render(self, ctx: RenderContext) -> Buffer:
        return self._render_frame(ctx.epoch_s)

    def layers(self, ctx: RenderContext) -> list[LayerNode]:
        return [LayerNode(id=f"{self.name}-root", layer=self._layer, z=0)]

    def on_enter(self) -> None:
        return

    def on_exit(self) -> None:
        return


class InfoScene:
    """General-purpose information scene rendered from InfoLayout."""

    def __init__(
        self,
        *,
        layout: InfoLayout,
        name: str = "info",
    ):
        self.name = name
        self.layout = layout
        self._layer = _BufferLayer(name=f"{name}-layer", renderer=self._render)

    def _render(self, ctx: RenderContext) -> Buffer:
        return render_info_layout(self.layout, ctx)

    def layers(self, ctx: RenderContext) -> list[LayerNode]:
        return [LayerNode(id=f"{self.name}-root", layer=self._layer, z=0)]

    def on_enter(self) -> None:
        return

    def on_exit(self) -> None:
        return


def header_layout(
    *,
    title: str,
    font: str,
    height: int = 12,
    title_color: tuple[int, int, int] = (145, 145, 145),
    background_color: tuple[int, int, int] = (0, 0, 0),
    center: bool = True,
    border: BorderConfig = BorderConfig(enabled=True, thickness=1, color=(60, 60, 60)),
    body_rows: Optional[List[InfoRow]] = None,
    body_background_color: tuple[int, int, int] = (0, 0, 0),
) -> InfoLayout:
    """Build an InfoLayout with a header-like first row and optional body rows."""
    rows: List[InfoRow] = [
        TextRow(
            height=max(1, int(height)),
            background_color=background_color,
            border=border,
            align="center" if center else "left",
            style=TextStyle(font=font, color=title_color),
            content=title,
        )
    ]
    for row in body_rows or []:
        rows.append(row)
    return InfoLayout(rows=rows, background_color=body_background_color)
