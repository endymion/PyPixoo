"""Tests for canonical font profile registry."""

from __future__ import annotations

from pathlib import Path

from pypixoo.font_profiles import (
    FontProfile,
    get_font_profile,
    list_font_profiles,
    normalize_font_key,
    register_runtime_font_profile,
)


def test_list_font_profiles_contains_expected_defaults():
    keys = [p.key for p in list_font_profiles()]
    assert "tiny5" in keys
    assert "micro5" in keys
    assert "bytesized" in keys
    assert "jersey10" in keys
    assert "jersey15" in keys


def test_normalize_font_key():
    assert normalize_font_key("Tiny-5") == "tiny5"
    assert normalize_font_key("  Micro_5 ") == "micro5"


def test_get_font_profile_has_real_ttf_path():
    profile = get_font_profile("tiny5")
    assert isinstance(profile, FontProfile)
    assert profile.ttf_path.exists()


def test_register_runtime_font_profile():
    base = get_font_profile("tiny5")
    register_runtime_font_profile(
        "my_runtime",
        display_name="My Runtime",
        ttf_path=base.ttf_path,
        pixel_size=11,
        y_offset_px=-1,
        letter_spacing_px=2,
        alpha_threshold=90,
    )
    loaded = get_font_profile("my_runtime")
    assert loaded.display_name == "My Runtime"
    assert loaded.pixel_size_host == 11
    assert loaded.pixel_size_web == 11
    assert loaded.ttf_path == base.ttf_path
