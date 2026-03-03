"""Parse color strings to (r, g, b).

Supported inputs:
- Hex: RGB/RGBA (`#f0f`, `#ff00ff`, `#ff00ffcc`, with or without `#`)
- CSV RGB: `r,g,b` (e.g. `128,64,32`)
- Named colors: PIL/ImageColor names (e.g. `fuchsia`, `red`)
- Radix tokens: `gray11`, `gray-11`, `dark.gray11`, `grayDark11`
"""

import re
from typing import Tuple

from PIL import ImageColor

from pypixoo.radix_colors import (
    RADIX_DARK_COLORS,
    RADIX_DARK_TOKENS,
    RADIX_LIGHT_COLORS,
    RADIX_LIGHT_TOKENS,
)


def _normalize_token(token: str) -> str:
    lowered = token.strip().lower()
    if lowered.startswith("--"):
        lowered = lowered[2:]
    return re.sub(r"[^a-z0-9]", "", lowered)


def _rgba_over_black(r: int, g: int, b: int, a: int) -> Tuple[int, int, int]:
    alpha = max(0, min(255, a)) / 255.0
    return (
        int(round(r * alpha)),
        int(round(g * alpha)),
        int(round(b * alpha)),
    )


def _hex_to_rgb(hex_part: str) -> Tuple[int, int, int]:
    if len(hex_part) in (3, 4):
        hex_part = "".join(ch * 2 for ch in hex_part)
    if len(hex_part) == 6:
        rgb = ImageColor.getrgb("#" + hex_part)
        return int(rgb[0]), int(rgb[1]), int(rgb[2])
    if len(hex_part) == 8:
        r = int(hex_part[0:2], 16)
        g = int(hex_part[2:4], 16)
        b = int(hex_part[4:6], 16)
        a = int(hex_part[6:8], 16)
        return _rgba_over_black(r, g, b, a)
    raise ValueError(f"Invalid hex color length ({len(hex_part)}): {hex_part}")


def _resolve_radix_hex(token: str) -> str | None:
    compact = _normalize_token(token)
    if compact in RADIX_LIGHT_COLORS:
        return RADIX_LIGHT_COLORS[compact]

    if compact.startswith("dark"):
        dark_key = compact[4:]
        if dark_key in RADIX_DARK_COLORS:
            return RADIX_DARK_COLORS[dark_key]

    dark_alias_match = re.match(r"^([a-z]+)dark(a?\d+)$", compact)
    if dark_alias_match:
        palette, suffix = dark_alias_match.groups()
        dark_key = f"{palette}{suffix}"
        if dark_key in RADIX_DARK_COLORS:
            return RADIX_DARK_COLORS[dark_key]

    return None


def list_radix_tokens(dark: bool = False) -> tuple[str, ...]:
    """List supported Radix token names.

    Args:
        dark: When True, return dark-scale tokens (`gray11` means dark gray 11
            in this context). When False, return light-scale tokens.
    """
    if dark:
        return tuple(f"dark.{token}" for token in RADIX_DARK_TOKENS)
    return RADIX_LIGHT_TOKENS


def parse_color(s: str) -> Tuple[int, int, int]:
    """Parse a color string to (r, g, b) in 0..255.

    Accepts:
    - 6-digit hex: FF00FF, ff00ff, #FF00FF
    - 3-digit hex: f0f, #f0f (expanded to ff00ff)
    - 8-digit/4-digit hex with alpha (composited over black)
    - CSV RGB: r,g,b
    - Named colors: fuchsia, red, etc. (PIL ImageColor names)
    - Radix tokens: gray11, gray-11, dark.gray11, grayDark11
    """
    s = s.strip()
    if not s:
        raise ValueError("Empty color string")

    # Normalize hex: optional leading #, then 3/4/6/8 hex chars.
    hex_match = re.match(r"^#?([0-9A-Fa-f]{3}|[0-9A-Fa-f]{4}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$", s)
    if hex_match:
        return _hex_to_rgb(hex_match.group(1))

    rgb_match = re.match(r"^\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*$", s)
    if rgb_match:
        r, g, b = (int(rgb_match.group(i)) for i in range(1, 4))
        if any(channel < 0 or channel > 255 for channel in (r, g, b)):
            raise ValueError(f"RGB channels must be in 0..255: {s}")
        return r, g, b

    radix_hex = _resolve_radix_hex(s)
    if radix_hex:
        return _hex_to_rgb(radix_hex.lstrip("#"))

    parsed = ImageColor.getrgb(s)
    if len(parsed) == 4:
        return _rgba_over_black(parsed[0], parsed[1], parsed[2], parsed[3])
    return int(parsed[0]), int(parsed[1]), int(parsed[2])
