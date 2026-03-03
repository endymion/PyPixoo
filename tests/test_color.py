"""Tests for pypixoo.color.parse_color."""

import pytest

from pypixoo.color import parse_color
from pypixoo.radix_colors import RADIX_DARK_COLORS, RADIX_LIGHT_COLORS


class TestParseColorHex6:
    def test_uppercase(self):
        assert parse_color("FF00FF") == (255, 0, 255)

    def test_lowercase(self):
        assert parse_color("ff00ff") == (255, 0, 255)

    def test_with_hash(self):
        assert parse_color("#FF00FF") == (255, 0, 255)

    def test_black(self):
        assert parse_color("000000") == (0, 0, 0)

    def test_white(self):
        assert parse_color("FFFFFF") == (255, 255, 255)


class TestParseColorHex3:
    def test_f0f(self):
        assert parse_color("f0f") == (255, 0, 255)

    def test_f0f_with_hash(self):
        assert parse_color("#f0f") == (255, 0, 255)

    def test_fff(self):
        assert parse_color("fff") == (255, 255, 255)

    def test_000(self):
        assert parse_color("000") == (0, 0, 0)


class TestParseColorNamed:
    def test_fuchsia(self):
        assert parse_color("fuchsia") == (255, 0, 255)

    def test_red(self):
        assert parse_color("red") == (255, 0, 0)

    def test_white(self):
        assert parse_color("white") == (255, 255, 255)

    def test_black(self):
        assert parse_color("black") == (0, 0, 0)


class TestParseColorInvalid:
    def test_empty_raises(self):
        with pytest.raises(ValueError, match="Empty color"):
            parse_color("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="Empty color"):
            parse_color("   ")

    def test_invalid_hex_raises(self):
        with pytest.raises(ValueError):
            parse_color("gg0000")

    def test_unknown_name_raises(self):
        with pytest.raises(ValueError):
            parse_color("notacolor")


class TestParseColorRadix:
    def test_radix_light_token(self):
        expected = RADIX_LIGHT_COLORS["gray11"]
        assert parse_color("gray11") == parse_color(expected)

    def test_radix_light_token_with_dash(self):
        expected = RADIX_LIGHT_COLORS["tomato9"]
        assert parse_color("tomato-9") == parse_color(expected)

    def test_radix_dark_token_dot_prefix(self):
        expected = RADIX_DARK_COLORS["gray11"]
        assert parse_color("dark.gray11") == parse_color(expected)

    def test_radix_dark_token_inline_alias(self):
        expected = RADIX_DARK_COLORS["gray11"]
        assert parse_color("grayDark11") == parse_color(expected)


class TestParseColorAdditionalFormats:
    def test_csv_rgb(self):
        assert parse_color("153, 128, 102") == (153, 128, 102)

    def test_rgba_hex_composites_over_black(self):
        assert parse_color("#ffffff80") == (128, 128, 128)
