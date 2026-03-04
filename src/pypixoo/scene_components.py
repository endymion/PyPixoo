"""Composable scene UI primitives and scene font registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Optional

from pypixoo.buffer import Buffer
from pypixoo.font_profiles import (
    FontProfile,
    get_font_profile,
    list_font_profiles,
    normalize_font_key,
    register_runtime_font_profile,
)
from pypixoo.font_render import draw_text_clipped as draw_text_clipped_shared
from pypixoo.font_render import measure_text as measure_text_shared

CANVAS_SIZE = 64


@dataclass(frozen=True)
class BorderConfig:
    """Bottom border configuration for row-like primitives."""

    enabled: bool = True
    thickness: int = 1
    color: tuple[int, int, int] = (60, 60, 60)


@dataclass(frozen=True)
class HeaderConfig:
    """High-level header parameters for InfoScene."""

    title: str
    font: str
    height: int = 12
    title_color: tuple[int, int, int] = (145, 145, 145)
    background_color: tuple[int, int, int] = (0, 0, 0)
    center: bool = True
    border: BorderConfig = field(default_factory=BorderConfig)

    def __post_init__(self) -> None:
        if self.height <= 0:
            raise ValueError("HeaderConfig.height must be > 0")
        if normalize_scene_font_name(self.font) not in _SCENE_FONTS:
            raise ValueError(
                f"Unsupported scene font '{self.font}'. "
                f"Supported: {', '.join(list_scene_fonts())}"
            )


@dataclass(frozen=True)
class RowConfig:
    """Simple row area with optional bottom border."""

    y: int
    height: int
    background_color: tuple[int, int, int] = (0, 0, 0)
    bottom_border: BorderConfig = field(default_factory=lambda: BorderConfig(enabled=False))

    def __post_init__(self) -> None:
        if self.height <= 0:
            raise ValueError("RowConfig.height must be > 0")


@dataclass(frozen=True)
class SceneFont:
    """Host-raster scene font metadata."""

    name: str
    display_name: str
    ttf_path: Path
    pixel_size_host: int
    y_offset_px_host: int
    letter_spacing: int
    alpha_threshold: int


def _normalize_color(color: tuple[int, int, int]) -> tuple[int, int, int]:
    return (
        max(0, min(255, int(color[0]))),
        max(0, min(255, int(color[1]))),
        max(0, min(255, int(color[2]))),
    )


def normalize_scene_font_name(name: str) -> str:
    """Normalize user-provided scene font names to registry keys."""
    return normalize_font_key(name)


def _profile_to_scene_font(profile: FontProfile) -> SceneFont:
    return SceneFont(
        name=profile.key,
        display_name=profile.display_name,
        ttf_path=profile.ttf_path,
        pixel_size_host=profile.pixel_size_host,
        y_offset_px_host=profile.y_offset_px_host,
        letter_spacing=profile.letter_spacing_px,
        alpha_threshold=profile.alpha_threshold,
    )


def _base_glyphs() -> Dict[str, list[str]]:
    # 5x7 bitmap set used for deterministic host-side scene text.
    return {
        " ": ["00000"] * 7,
        "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
        ".": ["00000", "00000", "00000", "00000", "00000", "00110", "00110"],
        ":": ["00000", "00110", "00110", "00000", "00110", "00110", "00000"],
        "/": ["00001", "00010", "00100", "01000", "10000", "00000", "00000"],
        "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
        "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
        "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
        "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
        "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
        "5": ["11111", "10000", "10000", "11110", "00001", "00001", "11110"],
        "6": ["01110", "10000", "10000", "11110", "10001", "10001", "01110"],
        "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
        "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
        "9": ["01110", "10001", "10001", "01111", "00001", "00001", "01110"],
        "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
        "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
        "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
        "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
        "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
        "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
        "G": ["01110", "10001", "10000", "10111", "10001", "10001", "01110"],
        "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
        "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
        "J": ["00001", "00001", "00001", "00001", "10001", "10001", "01110"],
        "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
        "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
        "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
        "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
        "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
        "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
        "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
        "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
        "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
        "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
        "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
        "V": ["10001", "10001", "10001", "10001", "01010", "01010", "00100"],
        "W": ["10001", "10001", "10001", "10101", "10101", "11011", "10001"],
        "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
        "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
        "Z": ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
    }


_SCENE_FONTS: Dict[str, SceneFont] = {
    p.key: _profile_to_scene_font(p) for p in list_font_profiles()
}


def register_scene_font(
    name: str,
    *,
    display_name: Optional[str] = None,
    glyphs: Optional[Dict[str, list[str]]] = None,
    letter_spacing: int = 1,
    scale: int = 1,
    ttf_path: Optional[Path] = None,
    pixel_size: int = 23,
) -> None:
    """Register or replace a scene-render font profile."""
    _ = glyphs
    _ = scale
    normalized = normalize_scene_font_name(name)
    if not normalized:
        raise ValueError("font name cannot be empty")
    register_runtime_font_profile(
        normalized,
        display_name=display_name or normalized,
        ttf_path=ttf_path,
        pixel_size=max(1, int(pixel_size)),
        letter_spacing_px=max(0, int(letter_spacing)),
    )
    _SCENE_FONTS[normalized] = _profile_to_scene_font(get_font_profile(normalized))


def get_scene_font(name: str) -> SceneFont:
    """Resolve a registered scene font by name."""
    normalized = normalize_scene_font_name(name)
    if normalized not in _SCENE_FONTS:
        raise ValueError(
            f"Unsupported scene font '{name}'. Supported: {', '.join(list_scene_fonts())}"
        )
    return _SCENE_FONTS[normalized]


def list_scene_fonts() -> list[str]:
    """List supported host-raster scene font keys."""
    return [p.key for p in list_font_profiles()]


def new_canvas(color: tuple[int, int, int]) -> list[int]:
    """Allocate a 64x64 RGB canvas filled with color."""
    rgb = _normalize_color(color)
    return [component for _ in range(CANVAS_SIZE * CANVAS_SIZE) for component in rgb]


def set_px(data: list[int], x: int, y: int, color: tuple[int, int, int]) -> None:
    """Set one pixel if inside canvas bounds."""
    if x < 0 or y < 0 or x >= CANVAS_SIZE or y >= CANVAS_SIZE:
        return
    rgb = _normalize_color(color)
    idx = (y * CANVAS_SIZE + x) * 3
    data[idx] = rgb[0]
    data[idx + 1] = rgb[1]
    data[idx + 2] = rgb[2]


def draw_rect(
    data: list[int],
    *,
    x: int,
    y: int,
    width: int,
    height: int,
    color: tuple[int, int, int],
) -> None:
    """Draw a filled rectangle clipped to canvas."""
    if width <= 0 or height <= 0:
        return
    for yy in range(y, y + height):
        for xx in range(x, x + width):
            set_px(data, xx, yy, color)


def draw_row(data: list[int], row: RowConfig) -> None:
    """Draw row background and optional bottom border."""
    y = max(0, row.y)
    height = max(0, min(row.height, CANVAS_SIZE - y))
    if height <= 0:
        return
    draw_rect(
        data,
        x=0,
        y=y,
        width=CANVAS_SIZE,
        height=height,
        color=row.background_color,
    )

    border = row.bottom_border
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


def measure_text(text: str, *, font: str) -> tuple[int, int]:
    """Return rendered width/height in pixels for the given scene font."""
    return measure_text_shared(text, font)


def draw_text(
    data: list[int],
    *,
    text: str,
    font: str,
    x: int,
    y: int,
    color: tuple[int, int, int],
) -> None:
    """Draw text using a registered scene font."""
    draw_text_clipped_shared(
        data,
        text=text,
        font_key=font,
        color=_normalize_color(color),
        x=x,
        y=y,
        clip_rect=(0, 0, CANVAS_SIZE, CANVAS_SIZE),
        canvas_size=CANVAS_SIZE,
    )


def to_buffer(data: Iterable[int]) -> Buffer:
    """Convert mutable canvas list to immutable Buffer."""
    return Buffer.from_flat_list(list(data))
