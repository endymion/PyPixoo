"""Tests for scene compositor helpers."""

from __future__ import annotations

from pypixoo.buffer import Buffer
from pypixoo.compositor import RenderedLayer, compose_layers


def _solid(color: tuple[int, int, int]) -> Buffer:
    return Buffer.from_flat_list([component for _ in range(64 * 64) for component in color])


def test_compose_layers_uses_z_order():
    red = RenderedLayer(buffer=_solid((255, 0, 0)), z=0)
    blue = RenderedLayer(buffer=_solid((0, 0, 255)), z=1)
    out = compose_layers([blue, red], width=64, height=64)
    assert out.get_pixel(0, 0) == (0, 0, 255)


def test_compose_layers_clip_bounds():
    base = RenderedLayer(buffer=_solid((0, 0, 0)), z=0)
    top = RenderedLayer(buffer=_solid((255, 255, 255)), z=1, clip=(0, 0, 32, 64))
    out = compose_layers([base, top], width=64, height=64)
    assert out.get_pixel(10, 10) == (255, 255, 255)
    assert out.get_pixel(40, 10) == (0, 0, 0)


def test_compose_layers_opacity_blends():
    base = RenderedLayer(buffer=_solid((0, 0, 0)), z=0)
    top = RenderedLayer(buffer=_solid((200, 200, 200)), z=1, opacity=0.5)
    out = compose_layers([base, top], width=64, height=64)
    r, g, b = out.get_pixel(0, 0)
    assert 95 <= r <= 105
    assert (r, g, b) == (r, r, r)


def test_compose_layers_translation():
    base = RenderedLayer(buffer=_solid((0, 0, 0)), z=0)
    top = RenderedLayer(buffer=_solid((255, 0, 0)), z=1, x=10, y=10)
    out = compose_layers([base, top], width=64, height=64)
    assert out.get_pixel(0, 0) == (0, 0, 0)
    assert out.get_pixel(10, 10) == (255, 0, 0)
