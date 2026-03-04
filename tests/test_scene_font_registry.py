"""Tests for scene font registry behavior."""

from __future__ import annotations

from pypixoo.info_dsl import TableCell, TableRow, TextSpan, TextStyle
from pypixoo.scene_components import list_scene_fonts, register_scene_font


def test_scene_font_registry_has_defaults():
    fonts = list_scene_fonts()
    assert fonts
    assert "tiny5" in fonts


def test_register_scene_font_appears_in_registry_and_validation_path():
    register_scene_font("My-New_Font")
    assert "mynewfont" in list_scene_fonts()
    style = TextStyle(font="mynewfont")
    span = TextSpan(text="HELLO", font="mynewfont")
    row = TableRow(cells=[TableCell("X", font="mynewfont")], default_style=style)
    assert style.font == "mynewfont"
    assert span.font == "mynewfont"
    assert row.default_style.font == "mynewfont"
