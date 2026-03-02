"""Extra CLI tests to cover environment and parser edge branches."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from pypixoo.cli import (
    _buffer_from_image,
    _connect,
    _parse_sequence_spec,
    _require_real_device,
    cmd_cycle,
    cmd_upload_sequence,
)
from pypixoo.pixoo import DeviceInUseError


class TestRequireRealDevice:
    def test_require_real_device_exits_without_env(self, monkeypatch):
        monkeypatch.delenv("PIXOO_REAL_DEVICE", raising=False)
        with pytest.raises(SystemExit):
            _require_real_device()


class TestConnectBranches:
    def test_connect_exits_when_pixoo_connect_false(self, monkeypatch):
        monkeypatch.setenv("PIXOO_REAL_DEVICE", "1")
        fake = MagicMock()
        fake.connect.return_value = False
        with patch("pypixoo.cli.Pixoo", return_value=fake):
            with pytest.raises(SystemExit):
                _connect("192.168.0.37")

    def test_connect_exits_on_device_in_use(self, monkeypatch):
        monkeypatch.setenv("PIXOO_REAL_DEVICE", "1")
        fake = MagicMock()
        fake.connect.side_effect = DeviceInUseError("192.168.0.37")
        with patch("pypixoo.cli.Pixoo", return_value=fake):
            with pytest.raises(SystemExit):
                _connect("192.168.0.37")


class TestSequenceParsing:
    def test_buffer_from_image_resizes(self, tmp_path):
        src = tmp_path / "small.png"
        img = Image.new("RGB", (32, 32), (11, 22, 33))
        img.save(src)

        buf = _buffer_from_image(src)
        assert buf.get_pixel(0, 0) == (11, 22, 33)

    def test_parse_sequence_spec_without_speed(self, tmp_path):
        one = tmp_path / "one.png"
        two = tmp_path / "two.png"
        Image.new("RGB", (64, 64), (1, 2, 3)).save(one)
        Image.new("RGB", (64, 64), (4, 5, 6)).save(two)

        seq = _parse_sequence_spec(f"{one},{two}", default_speed_ms=77)
        assert seq.speed_ms == 77
        assert len(seq.frames) == 2

    def test_parse_sequence_spec_with_explicit_speed(self, tmp_path):
        one = tmp_path / "one.png"
        Image.new("RGB", (64, 64), (7, 8, 9)).save(one)

        seq = _parse_sequence_spec(f"120:{one}", default_speed_ms=77)
        assert seq.speed_ms == 120

    def test_parse_sequence_spec_empty_raises(self):
        with pytest.raises(ValueError, match="at least one image path"):
            _parse_sequence_spec("", default_speed_ms=100)

    def test_parse_sequence_spec_missing_file_raises(self):
        with pytest.raises(ValueError, match="not found"):
            _parse_sequence_spec("missing.png", default_speed_ms=100)


class TestCommandBranches:
    def test_upload_sequence_missing_file_exits(self):
        with pytest.raises(SystemExit):
            cmd_upload_sequence(
                "192.168.0.37",
                image_paths=[Path("missing.png")],
                speed_ms=100,
                mode="command_list",
                chunk_size=40,
            )

    def test_cycle_sequence_parse_error_exits(self):
        with patch("pypixoo.cli._connect") as mock_connect, patch(
            "pypixoo.cli._parse_sequence_spec", side_effect=ValueError("bad spec")
        ):
            mock_connect.return_value = MagicMock()
            with pytest.raises(SystemExit):
                cmd_cycle(
                    "192.168.0.37",
                    item_specs=["sequence=bad"],
                    loop=1,
                    mode="command_list",
                    chunk_size=40,
                    default_speed_ms=100,
                )

    def test_cycle_infinite_keyboard_interrupt_stops_handle(self):
        fake_pixoo = MagicMock()
        fake_handle = MagicMock()
        fake_pixoo.start_cycle.return_value = fake_handle

        with patch("pypixoo.cli._connect", return_value=fake_pixoo), patch(
            "pypixoo.cli.time.sleep", side_effect=KeyboardInterrupt
        ):
            cmd_cycle(
                "192.168.0.37",
                item_specs=["url=https://example.com/a.gif"],
                loop=0,
                mode="command_list",
                chunk_size=40,
                default_speed_ms=100,
            )

        fake_handle.stop.assert_called_once()
        fake_handle.wait.assert_called_once_with(2.0)
