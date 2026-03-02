"""Unit tests for native Pixoo V2 client internals and validation branches."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests
from pydantic import ValidationError

from pypixoo.buffer import Buffer
from pypixoo.native import CycleHandle, CycleItem, GifFrame, GifSequence, GifSource, UploadMode
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

    def test_acquire_device_lock_returns_none_when_not_real_device(self, monkeypatch):
        monkeypatch.delenv("PIXOO_REAL_DEVICE", raising=False)
        assert _acquire_device_lock("192.168.0.37") is None

    def test_acquire_device_lock_returns_none_without_fcntl(self, monkeypatch):
        monkeypatch.setenv("PIXOO_REAL_DEVICE", "1")
        with patch("pypixoo.pixoo.fcntl", None):
            assert _acquire_device_lock("192.168.0.37") is None

    def test_acquire_device_lock_raises_when_open_fails(self, monkeypatch):
        monkeypatch.setenv("PIXOO_REAL_DEVICE", "1")
        fake_fcntl = MagicMock()
        fake_fcntl.LOCK_EX = 1
        fake_fcntl.LOCK_NB = 2
        with patch("pypixoo.pixoo.fcntl", fake_fcntl), patch("builtins.open", side_effect=OSError("nope")):
            with pytest.raises(DeviceInUseError):
                _acquire_device_lock("192.168.0.37")

    def test_acquire_device_lock_raises_when_already_locked(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PIXOO_REAL_DEVICE", "1")
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
