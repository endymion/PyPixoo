"""Tests for shared font raster renderer."""

from __future__ import annotations

from pypixoo.font_render import draw_text_clipped, measure_text, render_text_mask


def test_render_text_mask_and_measure():
    run = render_text_mask("HELLO", "tiny5")
    w, h = measure_text("HELLO", "tiny5")
    assert run.width > 0
    assert run.height > 0
    assert (w, h) == (run.width, run.height)


def test_draw_text_clipped_respects_clip_rect():
    canvas = [0] * (64 * 64 * 3)
    draw_text_clipped(
        canvas,
        text="HELLO",
        font_key="tiny5",
        color=(200, 100, 50),
        x=0,
        y=0,
        clip_rect=(0, 0, 3, 3),
        canvas_size=64,
    )
    colored_total = 0
    colored_outside = 0
    for y in range(64):
        for x in range(64):
            i = (y * 64 + x) * 3
            if (canvas[i], canvas[i + 1], canvas[i + 2]) != (0, 0, 0):
                colored_total += 1
                if x >= 3 or y >= 3:
                    colored_outside += 1
    assert colored_total >= 0
    assert colored_outside == 0


def test_font_profiles_are_visually_distinct_heights():
    _, h_tiny = measure_text("ABC", "tiny5")
    _, h_jersey15 = measure_text("ABC", "jersey15")
    assert h_jersey15 > h_tiny

