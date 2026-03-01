"""Parse color strings to (r, g, b). Supports hex (FF00FF, f0f, #f0f) and named colors (e.g. fuchsia)."""

import re
from typing import Tuple

from PIL import ImageColor


def parse_color(s: str) -> Tuple[int, int, int]:
    """Parse a color string to (r, g, b) in 0..255.

    Accepts:
    - 6-digit hex: FF00FF, ff00ff, #FF00FF
    - 3-digit hex: f0f, #f0f (expanded to ff00ff)
    - Named colors: fuchsia, red, etc. (PIL ImageColor names)
    """
    s = s.strip()
    if not s:
        raise ValueError("Empty color string")

    # Normalize hex: optional leading #, then 3 or 6 hex chars
    hex_match = re.match(r"^#?([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$", s)
    if hex_match:
        hex_part = hex_match.group(1)
        if len(hex_part) == 3:
            hex_part = "".join(c * 2 for c in hex_part)
        return ImageColor.getrgb("#" + hex_part)

    return ImageColor.getrgb(s)
