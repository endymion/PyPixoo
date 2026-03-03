"""Unit tests for native Pixoo V2 client internals and validation branches."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests
from pydantic import ValidationError

from pypixoo.buffer import Buffer
from pypixoo.fonts import BuiltinFont, FontRegistry
from pypixoo.native import (
    CycleHandle,
    CycleItem,
    DisplayItem,
    GifFrame,
    GifSequence,
    GifSource,
    UploadMode,
)
from pypixoo.pixoo import (
    DeviceInUseError,
    Pixoo,
    _acquire_device_lock,
    _device_lock_path,
)


def _response(payload):
    r = MagicMock()
    r.json.return_value = payload
    return r


def _frame(r=1, g=2, b=3):
    return GifFrame(image=Buffer.from_flat_list([r, g, b] * (64 * 64)), duration_ms=50)


class TestNativeModels:
    def test_cycle_item_requires_exactly_one_source(self):
        with pytest.raises(ValidationError):
            CycleItem()


class TestLockHelpers:
    def test_device_lock_path_uses_env_dir(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PYPIXOO_LOCK_DIR", str(tmp_path))
        path = _device_lock_path("192.168.0.37")
        assert str(path).startswith(str(tmp_path))

    def test_acquire_device_lock_returns_none_without_fcntl(self, monkeypatch):
        with patch("pypixoo.pixoo.fcntl", None):
            assert _acquire_device_lock("192.168.0.37") is None

    def test_acquire_device_lock_raises_when_open_fails(self, monkeypatch):
        fake_fcntl = MagicMock()
        fake_fcntl.LOCK_EX = 1
        fake_fcntl.LOCK_NB = 2
        with patch("pypixoo.pixoo.fcntl", fake_fcntl), patch("builtins.open", side_effect=OSError("nope")):
            with pytest.raises(DeviceInUseError):
                _acquire_device_lock("192.168.0.37")

    def test_acquire_device_lock_raises_when_already_locked(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PYPIXOO_LOCK_DIR", str(tmp_path))

        class FakeFcntl:
            LOCK_EX = 1
            LOCK_NB = 2

            @staticmethod
            def flock(fd, flags):
                raise BlockingIOError()

        with patch("pypixoo.pixoo.fcntl", FakeFcntl):
            with pytest.raises(DeviceInUseError):
                _acquire_device_lock("192.168.0.37")


class TestPixooV2:
    def test_connect_push_buffer_and_close(self):
        pixoo = Pixoo("192.168.0.37")
        data = [0, 0, 0] * (64 * 64)

        with patch("pypixoo.pixoo.requests.post") as mock_post, patch("pypixoo.pixoo._acquire_device_lock", return_value=None):
            mock_post.side_effect = [
                _response({"error_code": 0, "PicId": 1}),  # connect -> get id
                _response({"error_code": 0}),  # connect -> validate
                _response({"error_code": 0}),  # push_buffer upload
            ]
            assert pixoo.connect() is True
            pixoo.push_buffer(data)
            pixoo.close()

    def test_get_http_gif_id_missing_picid_raises(self):
        pixoo = Pixoo("192.168.0.37")
        with patch("pypixoo.pixoo.requests.post", return_value=_response({"error_code": 0})):
            with pytest.raises(RuntimeError, match="Missing PicId"):
                pixoo.get_http_gif_id()

    def test_upload_sequence_validation(self):
        pixoo = Pixoo("192.168.0.37")
        empty = GifSequence(frames=[], speed_ms=10)
        with pytest.raises(ValueError, match="at least one frame"):
            pixoo.upload_sequence(empty)

        seq = GifSequence(frames=[_frame()], speed_ms=10)
        with pytest.raises(ValueError, match="chunk_size"):
            pixoo.upload_sequence(seq, mode=UploadMode.COMMAND_LIST, chunk_size=0)

    def test_start_cycle_validation_and_active_guard(self):
        pixoo = Pixoo("192.168.0.37")
        with pytest.raises(ValueError, match="at least one CycleItem"):
            pixoo.start_cycle([])

        one_item = [CycleItem(source=GifSource.url("https://example.com/a.gif"))]
        with pytest.raises(ValueError, match="loop"):
            pixoo.start_cycle(one_item, loop=0)

        fake_handle = MagicMock(spec=CycleHandle)
        type(fake_handle).is_running = True
        pixoo._active_cycle = fake_handle
        with pytest.raises(RuntimeError, match="already running"):
            pixoo.start_cycle(one_item, loop=1)

    def test_post_command_error_raises(self):
        pixoo = Pixoo("192.168.0.37")
        with patch("pypixoo.pixoo.requests.post", return_value=_response({"error_code": 1})):
            with pytest.raises(RuntimeError, match="Command failed"):
                pixoo._post_command({"Command": "Draw/SendHttpGif"})

    def test_validate_connection_handles_request_exception(self):
        pixoo = Pixoo("192.168.0.37")
        with patch("pypixoo.pixoo.requests.post", side_effect=requests.exceptions.RequestException("boom")):
            assert pixoo._validate_connection() is False

    def test_release_device_lock_ignores_close_oserror(self):
        pixoo = Pixoo("192.168.0.37")
        fake_lock = MagicMock()
        fake_lock.close.side_effect = OSError("nope")
        pixoo._lock_file = fake_lock
        pixoo.close()
        assert pixoo._lock_file is None

    def test_send_text_overlay_after_play_gif_raises(self):
        pixoo = Pixoo("192.168.0.37")
        with patch("pypixoo.pixoo.requests.post") as mock_post:
            mock_post.return_value = _response({"error_code": 0})
            pixoo.play_gif(GifSource.url("https://example.com/a.gif"))
        with pytest.raises(ValueError):
            from pypixoo.native import TextOverlay

            pixoo.send_text_overlay(TextOverlay(text="blocked"))


class TestFontsAndOverlays:
    def test_text_overlay_font_range(self):
        from pypixoo.native import TextOverlay

        assert TextOverlay(text="ok", font=BuiltinFont.FONT_4)
        with pytest.raises(ValueError):
            TextOverlay(text="bad", font=8)

    def test_list_fonts_returns_registry(self):
        pixoo = Pixoo("192.168.0.37")
        with patch(
            "pypixoo.pixoo.requests.post",
            return_value=_response(
                {
                    "ReturnCode": 0,
                    "FontList": [
                        {"id": 4, "name": "font_4", "width": "8", "high": "8", "type": 0},
                        {"id": 7, "name": "font_7", "width": "8", "high": "8", "type": 0},
                    ],
                }
            ),
        ):
            registry = pixoo.list_fonts()
        assert isinstance(registry, FontRegistry)
        assert registry.find("font_4") is not None

    def test_upload_sequence_with_overlays_order(self):
        pixoo = Pixoo("192.168.0.37")
        calls = []

        def fake_post(payload):
            calls.append(payload)
            return {"error_code": 0}

        pixoo._post_command = fake_post  # type: ignore[method-assign]

        frame = _frame()
        seq = GifSequence(frames=[frame], speed_ms=100)
        from pypixoo.native import TextOverlay

        overlays = [
            TextOverlay(text="one", text_id=1, font=4, text_width=32),
            TextOverlay(text="two", text_id=2, font=4, text_width=32),
        ]
        pixoo.upload_sequence_with_overlays(seq, overlays, clear_before=False)

        commands = [c.get("Command") for c in calls]
        assert "Draw/SendHttpText" in commands
        upload_indices = [
            i for i, cmd in enumerate(commands) if cmd in ("Draw/SendHttpGif", "Draw/CommandList")
        ]
        assert upload_indices, "Expected upload commands before overlays"
        assert min(i for i, cmd in enumerate(commands) if cmd == "Draw/SendHttpText") > max(upload_indices)


class TestCommandWrappers:
    def test_basic_command_wrappers(self):
        pixoo = Pixoo("192.168.0.37")
        calls = []

        def fake_post(payload):
            calls.append(payload)
            return {"error_code": 0, "SelectIndex": 2}

        pixoo._post_command = fake_post  # type: ignore[method-assign]

        pixoo.set_brightness(80)
        pixoo.set_channel_index(2)
        pixoo.set_custom_page_index(1)
        pixoo.set_eq_position(0)
        pixoo.set_cloud_index(1)
        assert pixoo.get_channel_index() == 2

        assert calls[0] == {"Command": "Channel/SetBrightness", "Brightness": 80}
        assert calls[1] == {"Command": "Channel/SetIndex", "SelectIndex": 2}
        assert calls[2] == {"Command": "Channel/SetCustomPageIndex", "CustomPageIndex": 1}
        assert calls[3] == {"Command": "Channel/SetEqPosition", "EqPosition": 0}
        assert calls[4] == {"Command": "Channel/CloudIndex", "Index": 1}
        assert calls[5] == {"Command": "Channel/GetIndex"}

    def test_tools_and_display_list(self):
        pixoo = Pixoo("192.168.0.37")
        calls = []

        def fake_post(payload):
            calls.append(payload)
            return {"error_code": 0}

        pixoo._post_command = fake_post  # type: ignore[method-assign]

        pixoo.set_countdown_timer((1, 0, 1))
        pixoo.set_stopwatch(1)
        pixoo.set_scoreboard((3, 4))
        pixoo.set_noise_status(1)
        pixoo.play_buzzer(500, 500, 3000)

        item = DisplayItem(
            text_id=1,
            item_type=1,
            x=0,
            y=0,
            direction=0,
            font=4,
            text_width=32,
            text_height=16,
            text="TEST",
            speed=10,
            color="#FFFFFF",
            align=1,
        )
        pixoo.send_display_list([item])

        assert calls[0] == {"Command": "Tools/SetTimer", "Minute": 1, "Second": 0, "Status": 1}
        assert calls[1] == {"Command": "Tools/SetStopWatch", "Status": 1}
        assert calls[2] == {"Command": "Tools/SetScoreBoard", "BlueScore": 3, "RedScore": 4}
        assert calls[3] == {"Command": "Tools/SetNoiseStatus", "NoiseStatus": 1}
        assert calls[4] == {
            "Command": "Device/PlayBuzzer",
            "ActiveTimeInCycle": 500,
            "OffTimeInCycle": 500,
            "PlayTotalTime": 3000,
        }
        assert calls[5]["Command"] == "Draw/SendHttpItemList"
        assert calls[5]["ItemList"][0]["align"] == 1
