"""Behave hooks for PyPixoo specs."""

import base64
import json
import os

import requests
from unittest.mock import MagicMock, patch

# Patchers for browser feature (set in before_scenario when @mock_browser)
_browser_patchers = []


def _mock_response(json_data):
    resp = MagicMock()
    resp.json.return_value = json_data
    return resp


def before_all(context):
    """Mock device HTTP so specs run without a real Pixoo on the network.
    Set PIXOO_REAL_DEVICE=1 to disable mocking for @real_device scenarios."""
    context._real_device = os.environ.get("PIXOO_REAL_DEVICE") == "1"
    if context._real_device:
        context._post_patcher = None
        return

    def fake_post(url, data=None, **kwargs):
        mode = getattr(context, "mock_mode", "success")
        if mode == "validate_fail" and data and "Channel/GetAllConf" in str(data):
            raise requests.exceptions.RequestException("mock network failure")
        if mode == "load_counter_fail" and data and "GetHttpGifId" in str(data):
            return _mock_response({"error_code": 1})
        if mode == "push_fail" and data and "SendHttpGif" in str(data):
            return _mock_response({"error_code": 1})
        if "SendHttpGif" in str(data):
            try:
                payload = json.loads(data) if isinstance(data, str) else data
                pic_data = payload.get("PicData", "")
                raw = base64.b64decode(pic_data)
                history = getattr(context, "_push_history", None)
                if history is not None:
                    history.append(list(raw))
            except (json.JSONDecodeError, TypeError, KeyError):
                pass
        return _mock_response({"error_code": 0, "PicId": 1})

    context._push_history: list = []
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
            def set_viewport_size(self, size): pass
            def goto(self, url, wait_until=None): pass
            def screenshot(self): return _fake_png_bytes()

        class FakeBrowser:
            def new_page(self): return FakePage()
            def close(self): pass

        class FakeChromium:
            def launch(self, headless=True): return FakeBrowser()

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
    if "mock_validate_fail" in scenario.tags:
        context.mock_mode = "validate_fail"
    elif "mock_load_counter_fail" in scenario.tags:
        context.mock_mode = "load_counter_fail"
    elif "mock_push_fail" in scenario.tags:
        context.mock_mode = "push_fail"

    # Mock Playwright for browser feature so CI doesn't need real browser.
    # Patch sync_playwright so real _render_web_*, _screenshot_to_buffer run.
    # If playwright isn't installed, patch high-level functions instead.
    if "mock_browser" in scenario.tags:
        try:
            p1 = patch(
                "playwright.sync_api.sync_playwright",
                return_value=_fake_sync_playwright(),
            )
            p1.start()
            _browser_patchers[:] = [p1]
        except (ImportError, ModuleNotFoundError):
            # Fallback: mock high-level functions (lower coverage, no playwright needed)
            def _fake_persistent(url, timestamps, param):
                from pypixoo.buffer import Buffer
                data = [100, 100, 100] * (64 * 64)
                buf = Buffer.from_flat_list(data)
                return [buf for _ in timestamps]

            def _fake_per_frame(url, timestamp, param):
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
