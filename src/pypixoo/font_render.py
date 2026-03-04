"""Shared host-side font renderer for scene/layout text."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont

from pypixoo.font_profiles import FontProfile, get_font_profile


@dataclass(frozen=True)
class GlyphRun:
    """Rasterized glyph run with 1-bit alpha mask."""

    width: int
    height: int
    mask: bytes


@lru_cache(maxsize=1024)
def _render_cached(text_upper: str, font_key: str) -> GlyphRun:
    profile = get_font_profile(font_key)
    return _render_text_mask_uncached(text_upper, profile)


def _render_text_mask_uncached(text_upper: str, profile: FontProfile) -> GlyphRun:
    if not text_upper:
        return GlyphRun(width=0, height=0, mask=b"")
    # Use the same conceptual path as tinytext_192: render at 3x-oriented profile
    # then downsample by 3 with max pooling before thresholding.
    font = ImageFont.truetype(str(profile.ttf_path), size=profile.pixel_size_web)
    probe = Image.new("L", (2048, 512), 0)
    draw = ImageDraw.Draw(probe)
    draw.text((0, profile.y_offset_px_web), text_upper, font=font, fill=255)
    bbox = probe.getbbox()
    if not bbox:
        return GlyphRun(width=0, height=0, mask=b"")
    cropped = probe.crop(bbox).convert("L")
    hi_w, hi_h = cropped.size
    hi_px = cropped.load()

    factor = 3
    width = (hi_w + factor - 1) // factor
    height = (hi_h + factor - 1) // factor
    out = bytearray(width * height)
    threshold = profile.alpha_threshold

    for oy in range(height):
        base_y = oy * factor
        for ox in range(width):
            base_x = ox * factor
            max_alpha = 0
            for dy in range(factor):
                sy = base_y + dy
                if sy >= hi_h:
                    continue
                for dx in range(factor):
                    sx = base_x + dx
                    if sx >= hi_w:
                        continue
                    a = hi_px[sx, sy]
                    if a > max_alpha:
                        max_alpha = a
            out[oy * width + ox] = 1 if max_alpha >= threshold else 0

    _despeckle_in_place(out, width, height)
    return GlyphRun(width=width, height=height, mask=bytes(out))


def _despeckle_in_place(mask: bytearray, width: int, height: int) -> None:
    """Remove isolated 1px artifacts from thresholded glyph masks."""
    if width < 3 or height < 3:
        return
    original = bytes(mask)
    for y in range(1, height - 1):
        row = y * width
        for x in range(1, width - 1):
            idx = row + x
            if original[idx] == 0:
                continue
            neighbors = 0
            for ny in (y - 1, y, y + 1):
                nrow = ny * width
                for nx in (x - 1, x, x + 1):
                    if nx == x and ny == y:
                        continue
                    neighbors += 1 if original[nrow + nx] else 0
            if neighbors <= 1:
                mask[idx] = 0


def render_text_mask(text: str, font_key: str) -> GlyphRun:
    """Rasterize text to a thresholded glyph mask."""
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
    """Draw text into RGB canvas with clip rect."""
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
