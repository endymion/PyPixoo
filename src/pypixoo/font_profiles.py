"""Canonical font profile registry for host-rendered scene text."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass(frozen=True)
class FontProfile:
    """Font profile used by host-side raster rendering."""

    key: str
    display_name: str
    ttf_path: Path
    pixel_size_web: int
    y_offset_px_web: int
    pixel_size_host: int
    y_offset_px_host: int
    letter_spacing_px: int
    alpha_threshold: int


def normalize_font_key(name: str) -> str:
    """Normalize user-facing font key/name."""
    return name.strip().lower().replace("-", "").replace("_", "")


_PROFILE_FILE = Path(__file__).resolve().parent / "data" / "font_profiles.json"
_FONTS_DIR = Path(__file__).resolve().parents[2] / "demos" / "fixtures" / "fonts"
_RUNTIME_OVERRIDES: Dict[str, FontProfile] = {}


def _load_profiles() -> Dict[str, FontProfile]:
    raw = json.loads(_PROFILE_FILE.read_text(encoding="utf-8"))
    profiles: Dict[str, FontProfile] = {}
    for key, payload in raw.items():
        normalized = normalize_font_key(key)
        ttf_file = str(payload["ttf_file"])
        profiles[normalized] = FontProfile(
            key=normalized,
            display_name=str(payload["display_name"]),
            ttf_path=(_FONTS_DIR / ttf_file).resolve(),
            pixel_size_web=int(payload["pixel_size_web"]),
            y_offset_px_web=int(payload["y_offset_px_web"]),
            pixel_size_host=int(payload["pixel_size_host"]),
            y_offset_px_host=int(payload["y_offset_px_host"]),
            letter_spacing_px=int(payload["letter_spacing_px"]),
            alpha_threshold=int(payload["alpha_threshold"]),
        )
    return profiles


_STATIC_PROFILES = _load_profiles()


def list_font_profiles() -> List[FontProfile]:
    """List canonical font profiles sorted by key."""
    merged = dict(_STATIC_PROFILES)
    merged.update(_RUNTIME_OVERRIDES)
    return [merged[k] for k in sorted(merged.keys())]


def get_font_profile(key: str) -> FontProfile:
    """Get one profile by key."""
    normalized = normalize_font_key(key)
    if normalized in _RUNTIME_OVERRIDES:
        return _RUNTIME_OVERRIDES[normalized]
    if normalized in _STATIC_PROFILES:
        return _STATIC_PROFILES[normalized]
    raise ValueError(
        f"Unsupported scene font '{key}'. Supported: {', '.join(p.key for p in list_font_profiles())}"
    )


def register_runtime_font_profile(
    key: str,
    *,
    display_name: Optional[str] = None,
    ttf_path: Optional[Path] = None,
    pixel_size: int = 23,
    y_offset_px: int = -3,
    letter_spacing_px: int = 1,
    alpha_threshold: int = 64,
) -> None:
    """Register a runtime font profile used by scene font APIs."""
    normalized = normalize_font_key(key)
    default_profile = _STATIC_PROFILES.get("tiny5")
    assert default_profile is not None
    _RUNTIME_OVERRIDES[normalized] = FontProfile(
        key=normalized,
        display_name=display_name or normalized,
        ttf_path=(ttf_path or default_profile.ttf_path).resolve(),
        pixel_size_web=max(1, int(pixel_size)),
        y_offset_px_web=int(y_offset_px),
        pixel_size_host=max(1, int(pixel_size)),
        y_offset_px_host=int(y_offset_px),
        letter_spacing_px=max(0, int(letter_spacing_px)),
        alpha_threshold=max(0, min(255, int(alpha_threshold))),
    )
