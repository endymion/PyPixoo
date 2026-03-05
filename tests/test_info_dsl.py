"""Unit tests for Info DSL row behavior."""

from __future__ import annotations

from pypixoo.info_dsl import (
    BorderConfig,
    InfoLayout,
    TextRow,
    TextSpan,
    TextStyle,
    layout_rows,
    measure_spans,
    render_info_layout,
    resolve_text,
)
from pypixoo.scene import RenderContext


def _ctx(epoch_s: float = 0.0) -> RenderContext:
    return RenderContext(epoch_s=epoch_s, monotonic_s=epoch_s, dt_s=0.0, frame_index=0)


def test_resolve_text_callable():
    assert resolve_text(lambda ctx: f"T{int(ctx.epoch_s)}", _ctx(7.0)) == "T7"


def test_textrow_left_vs_center_differs():
    left = InfoLayout(rows=[TextRow(height=12, align="left", style=TextStyle(font="tiny5"), content="HI")])
    center = InfoLayout(rows=[TextRow(height=12, align="center", style=TextStyle(font="tiny5"), content="HI")])
    left_frame = render_info_layout(left, _ctx())
    center_frame = render_info_layout(center, _ctx())
    left_has_near_left = any(
        left_frame.get_pixel(x, y) != (0, 0, 0) for y in range(0, 12) for x in range(0, 6)
    )
    center_has_near_left = any(
        center_frame.get_pixel(x, y) != (0, 0, 0) for y in range(0, 12) for x in range(0, 6)
    )
    assert left_has_near_left is True
    assert center_has_near_left is False


def test_layout_rows_stacks_and_honors_explicit_y():
    rows = [
        TextRow(height=10, content="A"),
        TextRow(height=8, y=30, content="B"),
        TextRow(height=5, content="C"),
    ]
    positioned = layout_rows(rows)
    assert positioned[0][1] == 0
    assert positioned[1][1] == 30
    assert positioned[2][1] == 38


def test_border_render_and_overflow_clipping():
    layout = InfoLayout(
        rows=[
            TextRow(
                height=6,
                border=BorderConfig(enabled=True, thickness=2, color=(9, 8, 7)),
                content="THIS TEXT IS VERY LONG AND SHOULD CLIP",
            )
        ]
    )
    frame = render_info_layout(layout, _ctx())
    assert frame.get_pixel(0, 4) == (9, 8, 7)
    assert frame.get_pixel(0, 5) == (9, 8, 7)
    assert frame.get_pixel(63, 0) in {(0, 0, 0), (145, 145, 145)}


def test_font_validation_row_and_span():
    try:
        TextStyle(font="no_such_font")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for invalid row font")
    try:
        TextSpan(text="X", font="no_such_font")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for invalid span font")


def test_measure_spans_uses_style_fallback():
    spans = [TextSpan(text="A"), TextSpan(text="B")]
    assert measure_spans(spans, TextStyle(font="tiny5"), _ctx()) > 0


def test_measure_spans_accounts_for_advance_px():
    base = [TextSpan(text="A"), TextSpan(text="B")]
    with_advance = [TextSpan(text="A", advance_px=3), TextSpan(text="B")]
    base_width = measure_spans(base, TextStyle(font="tiny5"), _ctx())
    advance_width = measure_spans(with_advance, TextStyle(font="tiny5"), _ctx())
    assert advance_width >= base_width + 3
