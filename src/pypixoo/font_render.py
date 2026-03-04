"""Shared host-side font renderer for scene/layout text.

This module uses one canonical glyph-atlas strategy across all host-rendered scenes:
- Render one glyph at high resolution (192px wide canvas)
- Downsample to 64px domain with nearest-neighbor semantics
- Threshold alpha to a 1-bit mask
- Compose text from cached glyph masks

The flow intentionally mirrors the behavior used by the validated font showcase fixture.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Tuple

from PIL import Image, ImageDraw, ImageFont

from pypixoo.font_profiles import FontProfile, get_font_profile

_HI_WIDTH = 192
_LO_WIDTH = 64
_DOWNSAMPLE = 3


@dataclass(frozen=True)
class GlyphMask:
    """One glyph mask in low-resolution (64px-domain) coordinates."""

    width: int
    height: int
    offset_y: int
    draw_width: int
    mask: bytes


@dataclass(frozen=True)
class FontAtlas:
    """Cached glyph atlas for one font profile."""

    font_key: str
    space_advance_px: int
    glyph_gap_px: int


@dataclass(frozen=True)
class GlyphRun:
    """Rasterized text run with 1-bit alpha mask."""

    width: int
    height: int
    mask: bytes


def _mask_bbox(mask: bytes, width: int, height: int) -> tuple[int, int, int, int] | None:
    min_x = width
    min_y = height
    max_x = -1
    max_y = -1
    for y in range(height):
        row = y * width
        for x in range(width):
            if mask[row + x] == 0:
                continue
            if x < min_x:
                min_x = x
            if y < min_y:
                min_y = y
            if x > max_x:
                max_x = x
            if y > max_y:
                max_y = y
    if max_x < min_x or max_y < min_y:
        return None
    return (min_x, min_y, max_x, max_y)


def _threshold_alpha(alpha_image: Image.Image, threshold: int) -> tuple[int, int, bytes]:
    width, height = alpha_image.size
    alpha = alpha_image.tobytes()
    out = bytearray(width * height)
    for idx, value in enumerate(alpha):
        out[idx] = 1 if value >= threshold else 0
    return (width, height, bytes(out))


@lru_cache(maxsize=64)
def _atlas_for_font(font_key: str) -> FontAtlas:
    profile = get_font_profile(font_key)
    font = ImageFont.truetype(str(profile.ttf_path), size=profile.pixel_size_web)
    # Use width heuristic equivalent to browser measureText()/3 with integer rounding.
    try:
        space_hi = font.getlength(" ")
    except AttributeError:
        bbox = font.getbbox(" ")
        space_hi = 0 if bbox is None else float(max(0, bbox[2] - bbox[0]))
    space_advance = max(1, int(round(space_hi / _DOWNSAMPLE)))
    return FontAtlas(
        font_key=font_key,
        space_advance_px=space_advance,
        glyph_gap_px=max(0, int(profile.letter_spacing_px)),
    )


@lru_cache(maxsize=4096)
def _glyph_for_char(font_key: str, char_upper: str) -> GlyphMask:
    if not char_upper:
        return GlyphMask(width=0, height=0, offset_y=0, draw_width=0, mask=b"")

    profile = get_font_profile(font_key)
    font = ImageFont.truetype(str(profile.ttf_path), size=profile.pixel_size_web)

    hi_h = max(3, int(profile.sample_height_web) * _DOWNSAMPLE)
    lo_h = max(1, hi_h // _DOWNSAMPLE)

    hi = Image.new("L", (_HI_WIDTH, hi_h), 0)
    hdraw = ImageDraw.Draw(hi)
    hdraw.fontmode = "1"
    hdraw.text((0, profile.y_offset_px_web), char_upper, font=font, fill=255)

    lo = hi.resize((_LO_WIDTH, lo_h), resample=Image.Resampling.NEAREST)
    lo_w, lo_h2, lo_mask = _threshold_alpha(lo, profile.alpha_threshold)

    bbox = _mask_bbox(lo_mask, lo_w, lo_h2)
    if bbox is None:
        return GlyphMask(width=0, height=0, offset_y=0, draw_width=1, mask=b"")

    min_x, min_y, max_x, max_y = bbox
    out_w = max_x - min_x + 1
    out_h = max_y - min_y + 1

    out = bytearray(out_w * out_h)
    for y in range(out_h):
        src_row = (min_y + y) * lo_w
        dst_row = y * out_w
        start = src_row + min_x
        out[dst_row : dst_row + out_w] = lo_mask[start : start + out_w]

    return GlyphMask(
        width=out_w,
        height=out_h,
        offset_y=min_y,
        draw_width=max(1, out_w),
        mask=bytes(out),
    )


@lru_cache(maxsize=1024)
def _render_cached(text_upper: str, font_key: str) -> GlyphRun:
    if not text_upper:
        return GlyphRun(width=0, height=0, mask=b"")

    atlas = _atlas_for_font(font_key)
    glyphs: list[tuple[int, GlyphMask | None]] = []

    cursor_x = 0
    min_y = 10**9
    max_y = -(10**9)

    for idx, ch in enumerate(text_upper):
        if ch == " ":
            glyphs.append((cursor_x, None))
            cursor_x += atlas.space_advance_px
        else:
            glyph = _glyph_for_char(font_key, ch)
            glyphs.append((cursor_x, glyph))
            if glyph.width > 0 and glyph.height > 0:
                if glyph.offset_y < min_y:
                    min_y = glyph.offset_y
                bottom_y = glyph.offset_y + glyph.height - 1
                if bottom_y > max_y:
                    max_y = bottom_y
            cursor_x += glyph.draw_width
        if idx < len(text_upper) - 1:
            cursor_x += atlas.glyph_gap_px

    if min_y > max_y or cursor_x <= 0:
        return GlyphRun(width=0, height=0, mask=b"")

    run_w = max(1, cursor_x)
    run_h = max(1, max_y - min_y + 1)
    out = bytearray(run_w * run_h)

    for x_origin, glyph in glyphs:
        if glyph is None or glyph.width <= 0 or glyph.height <= 0:
            continue
        base_y = glyph.offset_y - min_y
        for gy in range(glyph.height):
            py = base_y + gy
            if py < 0 or py >= run_h:
                continue
            src_row = gy * glyph.width
            dst_row = py * run_w
            for gx in range(glyph.width):
                if glyph.mask[src_row + gx] == 0:
                    continue
                px = x_origin + gx
                if 0 <= px < run_w:
                    out[dst_row + px] = 1

    return GlyphRun(width=run_w, height=run_h, mask=bytes(out))


def render_text_mask(text: str, font_key: str) -> GlyphRun:
    """Rasterize text into a thresholded 1-bit glyph run mask."""
    return _render_cached(text.upper(), font_key)


def measure_text(text: str, font_key: str) -> Tuple[int, int]:
    """Measure rendered text width/height in pixels."""
    run = render_text_mask(text, font_key)
    return run.width, run.height


def draw_text_clipped(
    canvas: list[int],
    *,
    text: str,
    font_key: str,
    color: tuple[int, int, int],
    x: int,
    y: int,
    clip_rect: tuple[int, int, int, int],
    canvas_size: int,
) -> None:
    """Draw text into RGB canvas with clip-rect bounds."""
    run = render_text_mask(text, font_key)
    if run.width <= 0 or run.height <= 0:
        return

    clip_x, clip_y, clip_w, clip_h = clip_rect
    cr = max(0, min(255, int(color[0])))
    cg = max(0, min(255, int(color[1])))
    cb = max(0, min(255, int(color[2])))

    for yy in range(run.height):
        py = y + yy
        if py < clip_y or py >= clip_y + clip_h or py < 0 or py >= canvas_size:
            continue
        row_base = yy * run.width
        for xx in range(run.width):
            if run.mask[row_base + xx] == 0:
                continue
            px = x + xx
            if px < clip_x or px >= clip_x + clip_w or px < 0 or px >= canvas_size:
                continue
            idx = (py * canvas_size + px) * 3
            canvas[idx] = cr
            canvas[idx + 1] = cg
            canvas[idx + 2] = cb
