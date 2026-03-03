"""Font registry for Pixoo built-in and dial fonts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Iterable, Optional

import requests
from pydantic import BaseModel, Field

FONT_LIST_URL_V1 = "https://app.divoom-gz.com/Device/GetTimeDialFontList"
FONT_LIST_URL_V2 = "https://appin.divoom-gz.com/Device/GetTimeDialFontV2"
DEFAULT_FONT_LIST_URL = FONT_LIST_URL_V2


class BuiltinFont(IntEnum):
    """Built-in animation fonts for Draw/SendHttpText (0-7).

    These are device-side fonts used only by overlay text commands.
    """

    FONT_0 = 0
    FONT_1 = 1
    FONT_2 = 2
    FONT_3 = 3
    FONT_4 = 4
    FONT_5 = 5
    FONT_6 = 6
    FONT_7 = 7

    @classmethod
    def from_name(cls, name: str) -> "BuiltinFont":
        key = name.strip().lower().replace(" ", "_")
        aliases = {
            "0": cls.FONT_0,
            "font0": cls.FONT_0,
            "font_0": cls.FONT_0,
            "1": cls.FONT_1,
            "font1": cls.FONT_1,
            "font_1": cls.FONT_1,
            "2": cls.FONT_2,
            "font2": cls.FONT_2,
            "font_2": cls.FONT_2,
            "3": cls.FONT_3,
            "font3": cls.FONT_3,
            "font_3": cls.FONT_3,
            "4": cls.FONT_4,
            "font4": cls.FONT_4,
            "font_4": cls.FONT_4,
            "5": cls.FONT_5,
            "font5": cls.FONT_5,
            "font_5": cls.FONT_5,
            "6": cls.FONT_6,
            "font6": cls.FONT_6,
            "font_6": cls.FONT_6,
            "7": cls.FONT_7,
            "font7": cls.FONT_7,
            "font_7": cls.FONT_7,
        }
        if key not in aliases:
            raise ValueError(f"Unknown built-in font name: {name}")
        return aliases[key]


class FontInfo(BaseModel):
    """Font metadata from Device/GetTimeDialFontList or GetTimeDialFontV2.

    These fonts are used by Draw/SendHttpItemList display lists, not overlays.
    """

    id: int
    name: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    charset: Optional[str] = None
    type: Optional[int] = None
    url: Optional[str] = None
    encryption: Optional[str] = None


class FontRegistry(BaseModel):
    """Collection of fonts for Draw/SendHttpItemList display items."""

    fonts: list[FontInfo] = Field(default_factory=list)

    def find(self, name: str) -> Optional[FontInfo]:
        key = name.strip().lower()
        for font in self.fonts:
            if (font.name or "").strip().lower() == key:
                return font
        return None

    def get(self, font_id: int) -> Optional[FontInfo]:
        for font in self.fonts:
            if font.id == font_id:
                return font
        return None

    @classmethod
    def from_api_list(cls, font_list: Iterable[dict]) -> "FontRegistry":
        fonts: list[FontInfo] = []
        for raw in font_list:
            fonts.append(
                FontInfo(
                    id=int(raw.get("id", 0)),
                    name=raw.get("name") or raw.get("Name"),
                    width=_coerce_int(raw.get("width") or raw.get("Width")),
                    height=_coerce_int(raw.get("high") or raw.get("height") or raw.get("Height")),
                    charset=raw.get("charset") or raw.get("charSet"),
                    type=_coerce_int(raw.get("type")),
                    url=raw.get("url"),
                    encryption=raw.get("Encryption"),
                )
            )
        return cls(fonts=fonts)

    @classmethod
    def default(cls) -> "FontRegistry":
        return cls(fonts=[])


@dataclass(frozen=True)
class FontFetchResult:
    registry: FontRegistry
    source_url: str


def fetch_font_registry(url: str = DEFAULT_FONT_LIST_URL, timeout: int = 8) -> FontFetchResult:
    """Fetch the time dial font list from the official service.

    This hits a Divoom cloud endpoint, not the device.
    """
    try:
        response = requests.post(url, timeout=timeout)
        data = response.json()
    except Exception:
        return FontFetchResult(registry=FontRegistry.default(), source_url=url)

    font_list = data.get("FontList") or []
    if not isinstance(font_list, list):
        return FontFetchResult(registry=FontRegistry.default(), source_url=url)
    registry = FontRegistry.from_api_list(font_list)
    return FontFetchResult(registry=registry, source_url=url)


def load_registry_from_json(path: Path) -> FontRegistry:
    data = json.loads(path.read_text())
    if isinstance(data, dict) and "FontList" in data:
        return FontRegistry.from_api_list(data.get("FontList") or [])
    if isinstance(data, dict) and "fonts" in data:
        return FontRegistry.model_validate(data)
    raise ValueError("Unrecognized font registry JSON format")


def _coerce_int(value) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
