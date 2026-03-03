"""Tests for pypixoo CLI native V2 subcommands."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pypixoo.cli import (
    cmd_cycle,
    cmd_fill,
    cmd_list_fonts,
    cmd_load_image,
    cmd_play_gif_dir,
    cmd_play_gif_file,
    cmd_play_gif_url,
    cmd_raw_command,
    cmd_text_overlay,
    cmd_clear_text,
    cmd_upload_sequence,
    main,
)
from pypixoo.fonts import FontInfo, FontRegistry
from pypixoo.native import GifFrame, GifSequence, UploadMode, TextOverlay
from pypixoo.buffer import Buffer


class TestCliFill:
    def test_parse_color_integration(self):
        with patch("pypixoo.cli._connect") as mock_connect:
            mock_pixoo = MagicMock()
            mock_connect.return_value = mock_pixoo

            cmd_fill("192.168.0.37", "FF00FF")
            mock_pixoo.fill.assert_called_once_with(255, 0, 255)
            mock_pixoo.push.assert_called_once()
            mock_pixoo.close.assert_called_once()


class TestCliLoadImage:
    def test_load_image_calls_load_and_push(self, tmp_path):
        img = tmp_path / "test.png"
        img.write_bytes(b"fake png")
        with patch("pypixoo.cli._connect") as mock_connect:
            mock_pixoo = MagicMock()
            mock_connect.return_value = mock_pixoo

            cmd_load_image("192.168.0.37", img)
            mock_pixoo.load_image.assert_called_once_with(img)
            mock_pixoo.push.assert_called_once()
            mock_pixoo.close.assert_called_once()

    def test_load_image_missing_file_exits(self):
        with patch("pypixoo.cli._connect"):
            with pytest.raises(SystemExit):
                cmd_load_image("192.168.0.37", Path("/nonexistent/image.png"))


class TestCliNativeCommands:
    def _sequence(self):
        frame = GifFrame(image=Buffer.from_flat_list([0, 0, 0] * (64 * 64)), duration_ms=100)
        return GifSequence(frames=[frame], speed_ms=100)

    def test_upload_sequence_calls_native_upload(self, tmp_path):
        p1 = tmp_path / "f1.png"
        p2 = tmp_path / "f2.png"
        p1.write_text("x")
        p2.write_text("y")

        with patch("pypixoo.cli._connect") as mock_connect, patch(
            "pypixoo.cli._sequence_from_image_paths"
        ) as mock_sequence:
            mock_pixoo = MagicMock()
            mock_connect.return_value = mock_pixoo
            mock_sequence.return_value = self._sequence()

            cmd_upload_sequence(
                "192.168.0.37",
                [p1, p2],
                speed_ms=120,
                mode="command_list",
                chunk_size=40,
            )

            mock_pixoo.upload_sequence.assert_called_once_with(
                mock_sequence.return_value,
                mode=UploadMode.COMMAND_LIST,
                chunk_size=40,
            )

    def test_play_gif_url_calls_pixoo(self):
        with patch("pypixoo.cli._connect") as mock_connect:
            mock_pixoo = MagicMock()
            mock_connect.return_value = mock_pixoo
            cmd_play_gif_url("192.168.0.37", "https://example.com/a.gif")
            call = mock_pixoo.play_gif.call_args[0][0]
            assert call.source_type == "url"
            assert call.value == "https://example.com/a.gif"

    def test_play_gif_file_calls_pixoo(self):
        with patch("pypixoo.cli._connect") as mock_connect:
            mock_pixoo = MagicMock()
            mock_connect.return_value = mock_pixoo
            cmd_play_gif_file("192.168.0.37", "divoom_gif/1.gif")
            call = mock_pixoo.play_gif.call_args[0][0]
            assert call.source_type == "tf_file"

    def test_play_gif_dir_calls_pixoo(self):
        with patch("pypixoo.cli._connect") as mock_connect:
            mock_pixoo = MagicMock()
            mock_connect.return_value = mock_pixoo
            cmd_play_gif_dir("192.168.0.37", "divoom_gif/")
            call = mock_pixoo.play_gif.call_args[0][0]
            assert call.source_type == "tf_directory"

    def test_cycle_parses_items_and_waits(self):
        with patch("pypixoo.cli._connect") as mock_connect, patch(
            "pypixoo.cli._parse_sequence_spec"
        ) as mock_parse:
            mock_pixoo = MagicMock()
            mock_handle = MagicMock()
            mock_handle.wait.return_value = True
            mock_pixoo.start_cycle.return_value = mock_handle
            mock_connect.return_value = mock_pixoo
            mock_parse.return_value = self._sequence()

            cmd_cycle(
                "192.168.0.37",
                item_specs=[
                    "url=https://example.com/a.gif",
                    "file=divoom_gif/1.gif",
                    "dir=divoom_gif/",
                    "sequence=100:one.png,two.png",
                ],
                loop=1,
                mode="frame_by_frame",
                chunk_size=22,
                default_speed_ms=90,
            )

            items = mock_pixoo.start_cycle.call_args[0][0]
            assert items[0].source.source_type == "url"
            assert items[1].source.source_type == "tf_file"
            assert items[2].source.source_type == "tf_directory"
            assert items[3].sequence == mock_parse.return_value
            assert items[3].upload_mode == UploadMode.FRAME_BY_FRAME
            assert items[3].chunk_size == 22

    def test_cycle_invalid_item_exits(self):
        with pytest.raises(SystemExit):
            cmd_cycle(
                "192.168.0.37",
                item_specs=["bogus=value"],
                loop=1,
                mode="command_list",
                chunk_size=40,
                default_speed_ms=100,
            )

    def test_list_fonts_calls_registry(self):
        with patch(
            "pypixoo.cli.Pixoo.list_fonts",
            return_value=FontRegistry(fonts=[FontInfo(id=4, name="font_4")]),
        ):
            cmd_list_fonts()

    def test_text_overlay_calls_pixoo(self):
        with patch("pypixoo.cli._connect") as mock_connect:
            mock_pixoo = MagicMock()
            mock_connect.return_value = mock_pixoo
            cmd_text_overlay(
                "192.168.0.37",
                "hello",
                x=1,
                y=2,
                font="font_4",
                width=56,
                speed=10,
                color="#FFFF00",
                align=1,
                direction=0,
            )
            overlay = mock_pixoo.send_text_overlay.call_args[0][0]
            assert isinstance(overlay, TextOverlay)
            assert int(overlay.font) == 4
            mock_pixoo.close.assert_called_once()

    def test_clear_text_calls_pixoo(self):
        with patch("pypixoo.cli._connect") as mock_connect:
            mock_pixoo = MagicMock()
            mock_connect.return_value = mock_pixoo
            cmd_clear_text("192.168.0.37")
            mock_pixoo.clear_text_overlay.assert_called_once()
            mock_pixoo.close.assert_called_once()

    def test_raw_command_parses_payload(self):
        with patch("pypixoo.cli._connect") as mock_connect:
            mock_pixoo = MagicMock()
            mock_connect.return_value = mock_pixoo
            cmd_raw_command("192.168.0.37", "Device/SetHighLightMode", ["Mode=1", "Flag=on"])
            mock_pixoo.command.assert_called_once_with(
                "Device/SetHighLightMode",
                {"Mode": 1, "Flag": "on"},
            )


class TestCliMain:
    def test_fill_subcommand_parses_color(self):
        with patch("pypixoo.cli.cmd_fill") as mock_fill:
            with patch("sys.argv", ["pypixoo", "fill", "red"]):
                main()
            mock_fill.assert_called_once()
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

    def test_upload_sequence_subcommand(self):
        with patch("pypixoo.cli.cmd_upload_sequence") as mock_cmd:
            with patch(
                "sys.argv",
                [
                    "pypixoo",
                    "upload-sequence",
                    "one.png",
                    "two.png",
                    "--speed-ms",
                    "80",
                    "--mode",
                    "command_list",
                    "--chunk-size",
                    "16",
                ],
            ):
                main()
            mock_cmd.assert_called_once()

    def test_play_gif_url_subcommand(self):
        with patch("pypixoo.cli.cmd_play_gif_url") as mock_cmd:
            with patch("sys.argv", ["pypixoo", "play-gif-url", "https://example.com/a.gif"]):
                main()
            mock_cmd.assert_called_once_with("192.168.0.37", "https://example.com/a.gif")

    def test_cycle_subcommand(self):
        with patch("pypixoo.cli.cmd_cycle") as mock_cmd:
            with patch(
                "sys.argv",
                [
                    "pypixoo",
                    "cycle",
                    "--item",
                    "url=https://example.com/a.gif",
                    "--loop",
                    "2",
                ],
            ):
                main()
            mock_cmd.assert_called_once()
            args = mock_cmd.call_args[0]
            assert args[1] == ["url=https://example.com/a.gif"]
            assert args[2] == 2

    def test_list_fonts_subcommand(self):
        with patch("pypixoo.cli.cmd_list_fonts") as mock_cmd:
            with patch("sys.argv", ["pypixoo", "list-fonts"]):
                main()
            mock_cmd.assert_called_once()

    def test_text_overlay_subcommand(self):
        with patch("pypixoo.cli.cmd_text_overlay") as mock_cmd:
            with patch("sys.argv", ["pypixoo", "text-overlay", "hello", "--x", "1", "--y", "2"]):
                main()
            mock_cmd.assert_called_once()

    def test_raw_command_subcommand(self):
        with patch("pypixoo.cli.cmd_raw_command") as mock_cmd:
            with patch("sys.argv", ["pypixoo", "raw-command", "Device/SetHighLightMode", "Mode=1"]):
                main()
            mock_cmd.assert_called_once()
