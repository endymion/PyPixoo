"""Behave hooks for PyPixoo specs."""

import base64
import json
import os
from unittest.mock import MagicMock, patch

import requests

# Patchers for browser feature (set in before_scenario when @mock_browser)
_browser_patchers = []


def _mock_response(json_data):
    resp = MagicMock()
    resp.json.return_value = json_data
    return resp


def _decode_push_frame(payload, history):
    pic_data = payload.get("PicData", "")
    if not pic_data:
        return
    raw = base64.b64decode(pic_data)
    history.append(list(raw))


def _parse_payload(data, kwargs):
    candidate = data
    if candidate is None and "json" in kwargs:
        candidate = kwargs["json"]

    if isinstance(candidate, dict):
        return candidate
    if isinstance(candidate, (bytes, bytearray)):
        candidate = candidate.decode()
    if isinstance(candidate, str):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            return {}
    return {}


def before_all(context):
    """Mock device HTTP so specs run without a real Pixoo on the network.
    Set PIXOO_REAL_DEVICE=1 to disable mocking for @real_device scenarios."""
    context._real_device = os.environ.get("PIXOO_REAL_DEVICE") == "1"
    context._push_history = []
    context._command_history = []
    context._mock_pic_id = 1
    if context._real_device:
        context._post_patcher = None
        return

    def fake_post(url, data=None, **kwargs):
        payload = _parse_payload(data, kwargs)
        command = payload.get("Command")
        mode = getattr(context, "mock_mode", "success")

        if mode == "validate_fail" and command == "Channel/GetAllConf":
            raise requests.exceptions.RequestException("mock network failure")
        if mode == "load_counter_fail" and command == "Draw/GetHttpGifId":
            return _mock_response({"error_code": 1})
        if mode == "push_fail" and command in ("Draw/SendHttpGif", "Draw/CommandList"):
            return _mock_response({"error_code": 1})

        if command == "Draw/GetHttpGifId":
            context._command_history.append(payload)
            return _mock_response({"error_code": 0, "PicId": context._mock_pic_id})

        if command == "Draw/ResetHttpGifId":
            context._mock_pic_id = 1
            context._command_history.append(payload)
            return _mock_response({"error_code": 0})

        if command == "Draw/SendHttpGif":
            context._command_history.append(payload)
            _decode_push_frame(payload, context._push_history)
            return _mock_response({"error_code": 0})

        if command == "Draw/CommandList":
            context._command_history.append(payload)
            for nested in payload.get("CommandList", []):
                if nested.get("Command") == "Draw/SendHttpGif":
                    _decode_push_frame(nested, context._push_history)
            return _mock_response({"error_code": 0})

        if command in (
            "Draw/SendHttpText",
            "Draw/ClearHttpText",
            "Device/PlayTFGif",
            "Channel/GetAllConf",
        ):
            context._command_history.append(payload)
            return _mock_response({"error_code": 0})

        return _mock_response({"error_code": 0})

    context._post_patcher = patch("pypixoo.pixoo.requests.post", side_effect=fake_post)
    context._post_patcher.start()


def _fake_png_bytes(size=(32, 32)):
    """Return bytes of a valid PNG (gray) for _screenshot_to_buffer.
    Non-64x64 size exercises the resize path in _screenshot_to_buffer."""
    import io

    from PIL import Image

    buf = io.BytesIO()
    img = Image.new("RGB", size, (100, 100, 100))
    img.save(buf, format="PNG")
    return buf.getvalue()


class _FakePlaywrightContextManager:
    """Fake Playwright context manager so real browser.py code runs."""

    def __enter__(self):
        class FakePage:
            def set_viewport_size(self, size):
                pass

            def goto(self, url, wait_until=None):
                pass

            def screenshot(self):
                return _fake_png_bytes()

            def wait_for_timeout(self, timeout_ms):
                pass

            def evaluate(self, script):
                return False

            def wait_for_function(self, script, timeout=None):
                pass

        class FakeContext:
            def new_page(self):
                return FakePage()

            def close(self):
                pass

        class FakeBrowser:
            def new_context(self, viewport=None, device_scale_factor=1):
                return FakeContext()

            def new_page(self):
                return FakePage()

            def close(self):
                pass

        class FakeChromium:
            def launch(self, headless=True):
                return FakeBrowser()

        class FakePlaywright:
            chromium = FakeChromium()

        self._playwright = FakePlaywright()
        return self._playwright

    def __exit__(self, *args):
        return False


def _fake_sync_playwright():
    """Return a fake Playwright context manager."""
    return _FakePlaywrightContextManager()


def before_scenario(context, scenario):
    """Set mock mode from scenario tags for failure-path coverage."""
    context.mock_mode = "success"
    if hasattr(context, "_push_history"):
        context._push_history.clear()
    if hasattr(context, "_command_history"):
        context._command_history.clear()
    context._mock_pic_id = 1

    if "mock_validate_fail" in scenario.tags:
        context.mock_mode = "validate_fail"
    elif "mock_load_counter_fail" in scenario.tags:
        context.mock_mode = "load_counter_fail"
    elif "mock_push_fail" in scenario.tags:
        context.mock_mode = "push_fail"

    if "mock_browser" in scenario.tags:
        try:
            p1 = patch(
                "playwright.sync_api.sync_playwright",
                return_value=_fake_sync_playwright(),
            )
            p1.start()
            _browser_patchers[:] = [p1]
        except (ImportError, ModuleNotFoundError):
            def _fake_persistent(url, timestamps, param, *args, **kwargs):
                from pypixoo.buffer import Buffer

                data = [100, 100, 100] * (64 * 64)
                buf = Buffer.from_flat_list(data)
                return [buf for _ in timestamps]

            def _fake_per_frame(url, timestamp, param, *args, **kwargs):
                from pypixoo.buffer import Buffer

                data = [100, 100, 100] * (64 * 64)
                return Buffer.from_flat_list(data)

            p1 = patch("pypixoo.browser._render_web_frames_persistent", side_effect=_fake_persistent)
            p2 = patch("pypixoo.browser._render_web_frame", side_effect=_fake_per_frame)
            p1.start()
            p2.start()
            _browser_patchers[:] = [p1, p2]
    else:
        for patcher in _browser_patchers:
            try:
                patcher.stop()
            except RuntimeError:
                pass
        _browser_patchers.clear()


def after_scenario(context, scenario):
    """Stop browser mocks after scenario."""
    if "mock_browser" in scenario.tags:
        for p in _browser_patchers:
            p.stop()
        _browser_patchers.clear()


def after_all(context):
    if context._post_patcher is not None:
        context._post_patcher.stop()
