"""Tests for InfoScene + InfoLayout rendering."""

from __future__ import annotations

from pypixoo.scene import RenderContext
from pypixoo.info_dsl import BorderConfig, InfoLayout, TableCell, TableRow, TextRow, TextStyle
from pypixoo.scenes import InfoScene, header_layout


def _ctx() -> RenderContext:
    return RenderContext(epoch_s=0.0, monotonic_s=0.0, dt_s=0.0, frame_index=0)


def _render_info(scene: InfoScene):
    layer = scene.layers(_ctx())[0].layer
    return layer.render(_ctx())


def test_info_scene_header_border_color_and_thickness():
    scene = InfoScene(
        layout=header_layout(
            title="INFO",
            font="tiny5",
            height=12,
            border=BorderConfig(enabled=True, thickness=2, color=(10, 20, 30)),
        ),
    )
    frame = _render_info(scene)
    assert frame.get_pixel(0, 10) == (10, 20, 30)
    assert frame.get_pixel(0, 11) == (10, 20, 30)


def test_info_scene_header_border_can_be_disabled():
    scene = InfoScene(
        layout=header_layout(
            title="INFO",
            font="tiny5",
            height=12,
            border=BorderConfig(enabled=False, thickness=3, color=(200, 100, 50)),
        ),
    )
    frame = _render_info(scene)
    assert frame.get_pixel(0, 11) != (200, 100, 50)


def test_info_scene_centered_title_differs_from_left_aligned():
    centered = InfoScene(
        layout=header_layout(title="HI", font="tiny5", height=12, center=True),
    )
    left = InfoScene(
        layout=header_layout(title="HI", font="tiny5", height=12, center=False),
    )
    centered_frame = _render_info(centered)
    left_frame = _render_info(left)
    left_has_near_left = any(
        left_frame.get_pixel(x, y) != (0, 0, 0) for y in range(0, 11) for x in range(0, 6)
    )
    center_has_near_left = any(
        centered_frame.get_pixel(x, y) != (0, 0, 0) for y in range(0, 11) for x in range(0, 6)
    )
    assert left_has_near_left is True
    assert center_has_near_left is False


def test_info_scene_layout_renders_table_rows_and_alignment_block():
    scene = InfoScene(
        layout=InfoLayout(
            rows=[
                TextRow(height=12, align="center", style=TextStyle(font="tiny5"), content="INFO"),
                TableRow(
                    height=10,
                    default_style=TextStyle(font="tiny5", color=(140, 140, 140)),
                    cells=[TableCell("A"), TableCell("123")],
                    column_align=["left", "right"],
                    block_align="center",
                ),
                TableRow(
                    height=10,
                    default_style=TextStyle(font="tiny5", color=(140, 140, 140)),
                    cells=[TableCell("LONG"), TableCell("9")],
                    column_align=["left", "right"],
                    block_align="center",
                ),
            ],
            background_color=(0, 0, 0),
        )
    )
    frame = _render_info(scene)
    assert frame.get_pixel(0, 0) == (0, 0, 0)
    body_has_text = any(
        frame.get_pixel(x, y) != (0, 0, 0) for y in range(12, 40) for x in range(0, 64)
    )
    assert body_has_text is True
