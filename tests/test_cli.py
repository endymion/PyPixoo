"""Tests for pypixoo CLI (fill and load-image subcommands)."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pypixoo.cli import cmd_fill, cmd_load_image, main


class TestCliFill:
    def test_parse_color_integration(self):
        """Fill uses parse_color; we test that fill receives correct RGB via mock."""
        with patch("pypixoo.cli._connect") as mock_connect:
            mock_pixoo = MagicMock()
            mock_connect.return_value = mock_pixoo
            os.environ["PIXOO_REAL_DEVICE"] = "1"

            cmd_fill("192.168.0.37", "FF00FF")
            mock_pixoo.fill.assert_called_once_with(255, 0, 255)
            mock_pixoo.push.assert_called_once()
            mock_pixoo.close.assert_called_once()

    def test_fill_named_color(self):
        with patch("pypixoo.cli._connect") as mock_connect:
            mock_pixoo = MagicMock()
            mock_connect.return_value = mock_pixoo
            os.environ["PIXOO_REAL_DEVICE"] = "1"

            cmd_fill("192.168.0.37", "fuchsia")
            mock_pixoo.fill.assert_called_once_with(255, 0, 255)

    def test_fill_hex_short(self):
        with patch("pypixoo.cli._connect") as mock_connect:
            mock_pixoo = MagicMock()
            mock_connect.return_value = mock_pixoo
            os.environ["PIXOO_REAL_DEVICE"] = "1"

            cmd_fill("192.168.0.37", "f0f")
            mock_pixoo.fill.assert_called_once_with(255, 0, 255)


class TestCliLoadImage:
    def test_load_image_calls_load_and_push(self, tmp_path):
        img = tmp_path / "test.png"
        img.write_bytes(b"fake png")  # PIL will fail on real load; we mock load_image
        with patch("pypixoo.cli._connect") as mock_connect:
            mock_pixoo = MagicMock()
            mock_connect.return_value = mock_pixoo
            os.environ["PIXOO_REAL_DEVICE"] = "1"

            cmd_load_image("192.168.0.37", img)
            mock_pixoo.load_image.assert_called_once_with(img)
            mock_pixoo.push.assert_called_once()
            mock_pixoo.close.assert_called_once()

    def test_load_image_missing_file_exits(self):
        with patch("pypixoo.cli._connect"):
            os.environ["PIXOO_REAL_DEVICE"] = "1"
            with pytest.raises(SystemExit):
                cmd_load_image("192.168.0.37", Path("/nonexistent/image.png"))


class TestCliMain:
    def test_fill_subcommand_parses_color(self):
        with patch("pypixoo.cli.cmd_fill") as mock_fill:
            with patch("sys.argv", ["pypixoo", "fill", "red"]):
                main()
            mock_fill.assert_called_once()
            # Called with (ip, color) from namespace
            assert mock_fill.call_args[0][1] == "red"

    def test_fill_subcommand_with_ip(self):
        with patch("pypixoo.cli.cmd_fill") as mock_fill:
            with patch("sys.argv", ["pypixoo", "--ip", "10.0.0.1", "fill", "blue"]):
                main()
            mock_fill.assert_called_once_with("10.0.0.1", "blue")

    def test_load_image_subcommand(self):
        with patch("pypixoo.cli.cmd_load_image") as mock_load:
            with patch("sys.argv", ["pypixoo", "load-image", "features/fixtures/gradient_magenta_to_black.png"]):
                main()
            mock_load.assert_called_once()
            assert "gradient_magenta_to_black.png" in str(mock_load.call_args[0][1])
