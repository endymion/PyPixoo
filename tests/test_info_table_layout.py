"""Unit tests for table block metrics and rendering semantics."""

from __future__ import annotations

from pypixoo.info_dsl import (
    InfoLayout,
    TableCell,
    TableMetrics,
    TableRow,
    TextRow,
    TextStyle,
    build_table_block_metrics,
    render_info_layout,
)
from pypixoo.scene import RenderContext


def _ctx(epoch_s: float = 0.0) -> RenderContext:
    return RenderContext(epoch_s=epoch_s, monotonic_s=epoch_s, dt_s=0.0, frame_index=0)


def test_contiguous_table_block_uses_max_column_widths():
    rows = [
        TableRow(cells=[TableCell("A"), TableCell("12")], default_style=TextStyle(font="tiny5")),
        TableRow(cells=[TableCell("LONGER"), TableCell("3")], default_style=TextStyle(font="tiny5")),
    ]
    metrics = build_table_block_metrics(rows, _ctx())
    assert isinstance(metrics, TableMetrics)
    assert len(metrics.col_widths) == 2
    assert metrics.col_widths[0] > metrics.col_widths[1]


def test_non_contiguous_blocks_do_not_share_metrics():
    block1 = [TableRow(cells=[TableCell("A"), TableCell("1")])]
    block2 = [TableRow(cells=[TableCell("MUCHLONGER"), TableCell("2")])]
    m1 = build_table_block_metrics(block1, _ctx())
    m2 = build_table_block_metrics(block2, _ctx())
    assert m1.col_widths[0] < m2.col_widths[0]


def test_mismatched_cell_counts_render_without_error():
    layout = InfoLayout(
        rows=[
            TableRow(cells=[TableCell("A"), TableCell("B"), TableCell("C")]),
            TableRow(cells=[TableCell("X")]),
        ]
    )
    frame = render_info_layout(layout, _ctx())
    assert frame.get_pixel(0, 0) == (0, 0, 0)


def test_cell_level_style_override():
    layout = InfoLayout(
        rows=[
            TableRow(
                default_style=TextStyle(font="tiny5", color=(90, 90, 90)),
                cells=[TableCell("K"), TableCell("V", color=(200, 0, 0), font="tiny5")],
                column_align=["left", "right"],
            )
        ]
    )
    frame = render_info_layout(layout, _ctx())
    colored = 0
    for y in range(0, 12):
        for x in range(0, 64):
            if frame.get_pixel(x, y) == (200, 0, 0):
                colored += 1
    assert colored > 0


def test_table_blocks_split_by_text_row():
    layout = InfoLayout(
        rows=[
            TableRow(cells=[TableCell("A"), TableCell("1")]),
            TextRow(content="break"),
            TableRow(cells=[TableCell("VERY_LONG"), TableCell("2")]),
        ]
    )
    frame = render_info_layout(layout, _ctx())
    assert frame.get_pixel(0, 0) == (0, 0, 0)

