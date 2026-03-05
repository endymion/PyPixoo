"""InfoScene row DSL and host-raster layout/render helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Literal, Optional, Sequence, Tuple, Union

from pypixoo.font_render import draw_text_clipped as draw_text_clipped_shared
from pypixoo.scene import RenderContext
from pypixoo.scene_components import (
    CANVAS_SIZE,
    draw_rect,
    get_scene_font,
    measure_text,
    new_canvas,
    to_buffer,
)

Color = Tuple[int, int, int]
Align = Literal["left", "center"]
ColumnAlign = Literal["left", "center", "right"]
TextValue = Union[str, Callable[[RenderContext], str]]


@dataclass(frozen=True)
class BorderConfig:
    """Bottom border configuration for a row."""

    enabled: bool = False
    thickness: int = 1
    color: Color = (60, 60, 60)

    def __post_init__(self) -> None:
        if self.enabled and self.thickness < 1:
            raise ValueError("BorderConfig.thickness must be >= 1 when border is enabled")


@dataclass(frozen=True)
class TextStyle:
    """Default text style."""

    font: str = "tiny5"
    color: Color = (145, 145, 145)

    def __post_init__(self) -> None:
        _validate_font(self.font)


@dataclass(frozen=True)
class TextSpan:
    """One text fragment with optional style override."""

    text: TextValue
    font: Optional[str] = None
    color: Optional[Color] = None
    advance_px: Optional[int] = None

    def __post_init__(self) -> None:
        if self.font is not None:
            _validate_font(self.font)
        if self.advance_px is not None and self.advance_px < 0:
            raise ValueError("TextSpan.advance_px must be >= 0")


@dataclass(frozen=True)
class TextRow:
    """Single content row with left/center alignment."""

    kind: Literal["text"] = "text"
    height: int = 12
    y: Optional[int] = None
    background_color: Color = (0, 0, 0)
    border: BorderConfig = field(default_factory=BorderConfig)
    align: Align = "left"
    style: TextStyle = field(default_factory=TextStyle)
    content: Union[TextValue, List[TextSpan]] = ""

    def __post_init__(self) -> None:
        if self.height <= 0:
            raise ValueError("TextRow.height must be > 0")
        if self.align not in ("left", "center"):
            raise ValueError("TextRow.align must be 'left' or 'center'")
        if isinstance(self.content, list):
            for span in self.content:
                if not isinstance(span, TextSpan):
                    raise ValueError("TextRow.content list must contain TextSpan entries")


@dataclass(frozen=True)
class TableCell:
    """One table cell with optional style and alignment override."""

    value: TextValue
    font: Optional[str] = None
    color: Optional[Color] = None
    align: Optional[ColumnAlign] = None

    def __post_init__(self) -> None:
        if self.font is not None:
            _validate_font(self.font)
        if self.align is not None and self.align not in ("left", "center", "right"):
            raise ValueError("TableCell.align must be left/center/right")


@dataclass(frozen=True)
class TableRow:
    """Row with table cell alignment rules."""

    kind: Literal["table"] = "table"
    height: int = 12
    y: Optional[int] = None
    background_color: Color = (0, 0, 0)
    border: BorderConfig = field(default_factory=BorderConfig)
    default_style: TextStyle = field(default_factory=TextStyle)
    cells: List[TableCell] = field(default_factory=list)
    column_align: Optional[List[ColumnAlign]] = None
    gap_px: int = 2
    pad_x: int = 1
    block_align: Align = "left"

    def __post_init__(self) -> None:
        if self.height <= 0:
            raise ValueError("TableRow.height must be > 0")
        if self.gap_px < 0:
            raise ValueError("TableRow.gap_px must be >= 0")
        if self.pad_x < 0:
            raise ValueError("TableRow.pad_x must be >= 0")
        if self.block_align not in ("left", "center"):
            raise ValueError("TableRow.block_align must be 'left' or 'center'")
        if self.column_align is not None:
            for align in self.column_align:
                if align not in ("left", "center", "right"):
                    raise ValueError("TableRow.column_align entries must be left/center/right")


InfoRow = Union[TextRow, TableRow]


@dataclass(frozen=True)
class InfoLayout:
    """Top-level layout definition for InfoScene."""

    rows: List[InfoRow]
    background_color: Color = (0, 0, 0)


@dataclass(frozen=True)
class TableMetrics:
    """Column metrics for one contiguous table block."""

    col_widths: List[int]
    max_pad_x: int


def _validate_font(font: str) -> None:
    get_scene_font(font)


def resolve_text(value: TextValue, ctx: RenderContext) -> str:
    """Resolve static/callable text into a display string."""
    if callable(value):
        return str(value(ctx))
    return str(value)


def measure_spans(spans: Sequence[TextSpan], style: TextStyle, ctx: RenderContext) -> int:
    """Measure width in pixels for sequential spans with inherited/default style."""
    width = 0
    for span in spans:
        font = span.font or style.font
        span_text = resolve_text(span.text, ctx)
        span_w = 0
        if span_text:
            span_w, _ = measure_text(span_text, font=font)
        width += span_w + int(span.advance_px or 0)
    return width


def layout_rows(rows: Sequence[InfoRow]) -> List[Tuple[InfoRow, int]]:
    """Stack rows top-to-bottom, allowing optional explicit y overrides."""
    out: List[Tuple[InfoRow, int]] = []
    cursor = 0
    for row in rows:
        row_y = int(row.y) if row.y is not None else cursor
        out.append((row, row_y))
        cursor = max(cursor, row_y + row.height)
    return out


def build_table_block_metrics(
    block_rows: Sequence[TableRow], ctx: RenderContext
) -> TableMetrics:
    """Compute aligned column widths for one contiguous table block."""
    if not block_rows:
        return TableMetrics(col_widths=[], max_pad_x=0)
    num_cols = max(len(r.cells) for r in block_rows)
    max_pad_x = max(r.pad_x for r in block_rows)
    widths = [0] * num_cols
    for row in block_rows:
        for col in range(num_cols):
            if col < len(row.cells):
                cell = row.cells[col]
                text = resolve_text(cell.value, ctx)
                font = cell.font or row.default_style.font
                text_w, _ = measure_text(text, font=font)
            else:
                text_w = 0
            widths[col] = max(widths[col], text_w + (2 * max_pad_x))
    return TableMetrics(col_widths=widths, max_pad_x=max_pad_x)


def _draw_text_clipped(
    data: List[int],
    *,
    text: str,
    font: str,
    x: int,
    y: int,
    color: Color,
    clip_x: int,
    clip_y: int,
    clip_w: int,
    clip_h: int,
) -> None:
    draw_text_clipped_shared(
        data,
        text=text,
        font_key=font,
        color=color,
        x=x,
        y=y,
        clip_rect=(clip_x, clip_y, clip_w, clip_h),
        canvas_size=CANVAS_SIZE,
    )


def _draw_row_background(
    data: List[int], *, y: int, height: int, background_color: Color, border: BorderConfig
) -> None:
    draw_rect(
        data,
        x=0,
        y=y,
        width=CANVAS_SIZE,
        height=max(0, min(height, CANVAS_SIZE - y)),
        color=background_color,
    )
    if border.enabled and border.thickness > 0:
        thickness = max(1, min(height, border.thickness))
        draw_rect(
            data,
            x=0,
            y=y + height - thickness,
            width=CANVAS_SIZE,
            height=thickness,
            color=border.color,
        )


def draw_text_row(data: List[int], row: TextRow, ctx: RenderContext, y: int) -> None:
    """Render one text row with clipping and alignment."""
    if y >= CANVAS_SIZE or row.height <= 0:
        return
    row_h = min(row.height, CANVAS_SIZE - y)
    _draw_row_background(
        data, y=y, height=row_h, background_color=row.background_color, border=row.border
    )

    if isinstance(row.content, list):
        spans = row.content
        total_w = measure_spans(spans, row.style, ctx)
    else:
        text = resolve_text(row.content, ctx)
        total_w, _ = measure_text(text, font=row.style.font)
        spans = [TextSpan(text=text, font=row.style.font, color=row.style.color)]
    content_x = 1 if row.align == "left" else max(0, (CANVAS_SIZE - total_w) // 2)
    cursor_x = content_x
    for span in spans:
        span_text = resolve_text(span.text, ctx)
        span_font = span.font or row.style.font
        span_color = span.color or row.style.color
        span_w = 0
        if span_text:
            _, span_h = measure_text(span_text, font=span_font)
            span_y = y + max(0, (row_h - span_h) // 2)
            _draw_text_clipped(
                data,
                text=span_text,
                font=span_font,
                x=cursor_x,
                y=span_y,
                color=span_color,
                clip_x=0,
                clip_y=y,
                clip_w=CANVAS_SIZE,
                clip_h=row_h,
            )
            span_w, _ = measure_text(span_text, font=span_font)
        cursor_x += span_w + int(span.advance_px or 0)


def _effective_cell_align(row: TableRow, cell: TableCell, col_idx: int) -> ColumnAlign:
    if row.column_align and col_idx < len(row.column_align):
        return row.column_align[col_idx]
    if cell.align:
        return cell.align
    return "left"


def draw_table_row(
    data: List[int],
    row: TableRow,
    ctx: RenderContext,
    y: int,
    metrics: TableMetrics,
) -> None:
    """Render one table row using precomputed block column metrics."""
    if y >= CANVAS_SIZE or row.height <= 0:
        return
    row_h = min(row.height, CANVAS_SIZE - y)
    _draw_row_background(
        data, y=y, height=row_h, background_color=row.background_color, border=row.border
    )

    if not metrics.col_widths:
        return

    total_w = sum(metrics.col_widths)
    if len(metrics.col_widths) > 1:
        total_w += row.gap_px * (len(metrics.col_widths) - 1)
    block_x = 0 if row.block_align == "left" else max(0, (CANVAS_SIZE - total_w) // 2)

    cursor_x = block_x
    for col_idx, col_w in enumerate(metrics.col_widths):
        if col_idx < len(row.cells):
            cell = row.cells[col_idx]
            text = resolve_text(cell.value, ctx)
            font = cell.font or row.default_style.font
            color = cell.color or row.default_style.color
        else:
            cell = TableCell(value="")
            text = ""
            font = row.default_style.font
            color = row.default_style.color
        align = _effective_cell_align(row, cell, col_idx)
        text_w, text_h = measure_text(text, font=font)
        if align == "center":
            text_x = cursor_x + max(0, (col_w - text_w) // 2)
        elif align == "right":
            text_x = cursor_x + max(0, col_w - text_w - row.pad_x)
        else:
            text_x = cursor_x + row.pad_x
        text_y = y + max(0, (row_h - text_h) // 2)
        _draw_text_clipped(
            data,
            text=text,
            font=font,
            x=text_x,
            y=text_y,
            color=color,
            clip_x=cursor_x,
            clip_y=y,
            clip_w=col_w,
            clip_h=row_h,
        )
        cursor_x += col_w + row.gap_px


def render_info_layout(layout: InfoLayout, ctx: RenderContext):
    """Render InfoLayout to a 64x64 buffer."""
    data = new_canvas(layout.background_color)
    placed_rows = layout_rows(layout.rows)
    i = 0
    while i < len(placed_rows):
        row, y = placed_rows[i]
        if isinstance(row, TextRow):
            draw_text_row(data, row, ctx, y)
            i += 1
            continue
        block_rows: List[TableRow] = []
        block_positions: List[int] = []
        while i < len(placed_rows):
            candidate, candidate_y = placed_rows[i]
            if not isinstance(candidate, TableRow):
                break
            block_rows.append(candidate)
            block_positions.append(candidate_y)
            i += 1
        metrics = build_table_block_metrics(block_rows, ctx)
        for block_row, block_y in zip(block_rows, block_positions):
            draw_table_row(data, block_row, ctx, block_y, metrics)
    return to_buffer(data)


def _parse_color(value: object, default: Color = (0, 0, 0)) -> Color:
    if value is None:
        return default
    if isinstance(value, list) and len(value) == 3:
        return (int(value[0]), int(value[1]), int(value[2]))
    if isinstance(value, tuple) and len(value) == 3:
        return (int(value[0]), int(value[1]), int(value[2]))
    raise ValueError(f"Invalid color value: {value!r}")


def _parse_border(payload: Optional[Dict[str, object]], default_enabled: bool = False) -> BorderConfig:
    payload = payload or {}
    return BorderConfig(
        enabled=bool(payload.get("enabled", default_enabled)),
        thickness=int(payload.get("thickness", 1)),
        color=_parse_color(payload.get("color"), (60, 60, 60)),
    )


def _parse_text_style(payload: Optional[Dict[str, object]], default_font: str = "tiny5") -> TextStyle:
    payload = payload or {}
    return TextStyle(
        font=str(payload.get("font", default_font)),
        color=_parse_color(payload.get("color"), (145, 145, 145)),
    )


def _parse_text_row(payload: Dict[str, object]) -> TextRow:
    raw_content = payload.get("content", "")
    if isinstance(raw_content, list):
        spans: List[TextSpan] = []
        for span in raw_content:
            if not isinstance(span, dict):
                raise ValueError("TextRow span entries must be objects")
            advance_raw = span.get("advance_px")
            advance_px = int(advance_raw) if advance_raw is not None else None
            spans.append(
                TextSpan(
                    text=str(span.get("text", "")),
                    font=str(span["font"]) if "font" in span and span["font"] is not None else None,
                    color=_parse_color(span.get("color")) if "color" in span else None,
                    advance_px=advance_px,
                )
            )
        content: Union[str, List[TextSpan]] = spans
    else:
        content = str(raw_content)
    return TextRow(
        height=int(payload.get("height", 12)),
        y=int(payload["y"]) if payload.get("y") is not None else None,
        background_color=_parse_color(payload.get("background_color"), (0, 0, 0)),
        border=_parse_border(payload.get("border"), default_enabled=False),
        align=str(payload.get("align", "left")),  # validated by dataclass
        style=_parse_text_style(payload.get("style")),
        content=content,
    )


def _parse_table_row(payload: Dict[str, object]) -> TableRow:
    raw_cells = payload.get("cells", [])
    if not isinstance(raw_cells, list):
        raise ValueError("TableRow.cells must be a list")
    cells: List[TableCell] = []
    for raw_cell in raw_cells:
        if isinstance(raw_cell, dict):
            cells.append(
                TableCell(
                    value=str(raw_cell.get("value", "")),
                    font=(
                        str(raw_cell["font"])
                        if "font" in raw_cell and raw_cell["font"] is not None
                        else None
                    ),
                    color=_parse_color(raw_cell.get("color")) if "color" in raw_cell else None,
                    align=(
                        str(raw_cell["align"])
                        if "align" in raw_cell and raw_cell["align"] is not None
                        else None
                    ),
                )
            )
        else:
            cells.append(TableCell(value=str(raw_cell)))
    column_align = payload.get("column_align")
    if column_align is not None:
        if not isinstance(column_align, list):
            raise ValueError("TableRow.column_align must be a list")
        parsed_align = [str(x) for x in column_align]
    else:
        parsed_align = None
    return TableRow(
        height=int(payload.get("height", 12)),
        y=int(payload["y"]) if payload.get("y") is not None else None,
        background_color=_parse_color(payload.get("background_color"), (0, 0, 0)),
        border=_parse_border(payload.get("border"), default_enabled=False),
        default_style=_parse_text_style(payload.get("default_style")),
        cells=cells,
        column_align=parsed_align,
        gap_px=int(payload.get("gap_px", 2)),
        pad_x=int(payload.get("pad_x", 1)),
        block_align=str(payload.get("block_align", "left")),  # validated by dataclass
    )


def info_layout_from_dict(payload: Dict[str, object]) -> InfoLayout:
    """Parse InfoLayout from a plain dictionary (JSON-compatible)."""
    raw_rows = payload.get("rows")
    if not isinstance(raw_rows, list):
        raise ValueError("InfoLayout.rows must be a list")
    rows: List[InfoRow] = []
    for raw in raw_rows:
        if not isinstance(raw, dict):
            raise ValueError("Row entries must be objects")
        kind = str(raw.get("kind", "text"))
        if kind == "text":
            rows.append(_parse_text_row(raw))
        elif kind == "table":
            rows.append(_parse_table_row(raw))
        else:
            raise ValueError(f"Unsupported row kind: {kind}")
    return InfoLayout(
        rows=rows,
        background_color=_parse_color(payload.get("background_color"), (0, 0, 0)),
    )


def info_layout_from_json(raw_json: str) -> InfoLayout:
    """Parse InfoLayout from JSON string."""
    data = json.loads(raw_json)
    if not isinstance(data, dict):
        raise ValueError("Info layout JSON must parse to an object")
    return info_layout_from_dict(data)


def info_layout_to_dict(layout: InfoLayout) -> Dict[str, object]:
    """Serialize layout to a JSON-friendly dictionary (string-only values)."""
    rows: List[Dict[str, object]] = []
    for row in layout.rows:
        if isinstance(row, TextRow):
            if isinstance(row.content, list):
                content: Union[str, List[Dict[str, object]]] = [
                    {"text": "", "font": span.font, "color": list(span.color) if span.color else None}
                    if callable(span.text)
                    else {"text": str(span.text), "font": span.font, "color": list(span.color) if span.color else None}
                    for span in row.content
                ]
            else:
                content = "" if callable(row.content) else str(row.content)
            rows.append(
                {
                    "kind": "text",
                    "height": row.height,
                    "y": row.y,
                    "background_color": list(row.background_color),
                    "border": {
                        "enabled": row.border.enabled,
                        "thickness": row.border.thickness,
                        "color": list(row.border.color),
                    },
                    "align": row.align,
                    "style": {"font": row.style.font, "color": list(row.style.color)},
                    "content": content,
                }
            )
        else:
            rows.append(
                {
                    "kind": "table",
                    "height": row.height,
                    "y": row.y,
                    "background_color": list(row.background_color),
                    "border": {
                        "enabled": row.border.enabled,
                        "thickness": row.border.thickness,
                        "color": list(row.border.color),
                    },
                    "default_style": {
                        "font": row.default_style.font,
                        "color": list(row.default_style.color),
                    },
                    "cells": [
                        {
                            "value": "" if callable(cell.value) else str(cell.value),
                            "font": cell.font,
                            "color": list(cell.color) if cell.color else None,
                            "align": cell.align,
                        }
                        for cell in row.cells
                    ],
                    "column_align": row.column_align,
                    "gap_px": row.gap_px,
                    "pad_x": row.pad_x,
                    "block_align": row.block_align,
                }
            )
    return {"rows": rows, "background_color": list(layout.background_color)}
