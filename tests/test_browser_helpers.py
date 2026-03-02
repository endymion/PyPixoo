"""Unit tests for browser helper branches and save-path behavior."""

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image

from pypixoo.browser import (
    _render_web_frame,
    _render_web_frames_persistent,
    _screenshot_to_buffer,
    _wait_for_page_fonts,
    _wait_for_page_render_ready,
)


def _png_bytes(size, color=(255, 0, 0)):
    buf = io.BytesIO()
    img = Image.new("RGB", size, color)
    img.save(buf, format="PNG")
    return buf.getvalue()


def _fake_playwright_context(screenshot_bytes):
    class FakePage:
        def goto(self, url, wait_until=None):
            pass

        def wait_for_timeout(self, timeout_ms):
            pass

        def screenshot(self):
            return screenshot_bytes

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

        def close(self):
            pass

    class FakeChromium:
        def launch(self, headless=True):
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    class FakeManager:
        def __enter__(self):
            return FakePlaywright()

        def __exit__(self, exc_type, exc, tb):
            return False

    return FakeManager()


class TestScreenshotToBuffer:
    def test_downsample_3x_nearest(self):
        buf = _screenshot_to_buffer(_png_bytes((192, 192), (10, 20, 30)), downsample_mode="nearest")
        assert buf.get_pixel(0, 0) == (10, 20, 30)

    def test_downsample_3x_maxpool(self):
        img = Image.new("RGB", (192, 192), (0, 0, 0))
        px = img.load()
        px[0, 0] = (200, 100, 50)
        raw = io.BytesIO()
        img.save(raw, format="PNG")

        buf = _screenshot_to_buffer(raw.getvalue(), downsample_mode="maxpool")
        assert buf.get_pixel(0, 0) == (200, 100, 50)

    def test_downsample_2x_nearest(self):
        buf = _screenshot_to_buffer(_png_bytes((128, 128), (3, 4, 5)), downsample_mode="nearest")
        assert buf.get_pixel(0, 0) == (3, 4, 5)

    def test_downsample_2x_maxpool(self):
        img = Image.new("RGB", (128, 128), (0, 0, 0))
        px = img.load()
        px[1, 1] = (99, 88, 77)
        raw = io.BytesIO()
        img.save(raw, format="PNG")

        buf = _screenshot_to_buffer(raw.getvalue(), downsample_mode="maxpool")
        assert buf.get_pixel(0, 0) == (99, 88, 77)


class TestBrowserWaitHelpers:
    def test_wait_for_page_fonts_handles_evaluate_error(self):
        page = MagicMock()
        page.evaluate.side_effect = RuntimeError("boom")
        _wait_for_page_fonts(page)

    def test_wait_for_page_fonts_handles_wait_error(self):
        page = MagicMock()
        page.wait_for_function.side_effect = RuntimeError("boom")
        _wait_for_page_fonts(page)

    def test_wait_for_page_render_ready_handles_eval_error(self):
        page = MagicMock()
        page.evaluate.side_effect = RuntimeError("boom")
        _wait_for_page_render_ready(page)

    def test_wait_for_page_render_ready_handles_wait_error(self):
        page = MagicMock()
        page.evaluate.return_value = True
        page.wait_for_function.side_effect = RuntimeError("boom")
        _wait_for_page_render_ready(page)


class TestRenderSavePaths:
    def test_render_web_frame_saves_raw_screenshot(self, tmp_path):
        out = tmp_path / "raw.png"
        fake_manager = _fake_playwright_context(_png_bytes((64, 64), (1, 2, 3)))

        with patch("playwright.sync_api.sync_playwright", return_value=fake_manager):
            buf = _render_web_frame(
                "http://example.com",
                0.0,
                "t",
                save_raw_path=str(out),
            )

        assert out.exists()
        assert buf.get_pixel(0, 0) == (1, 2, 3)

    def test_render_web_frames_persistent_saves_first_raw_screenshot(self, tmp_path):
        out = tmp_path / "raw-first.png"
        fake_manager = _fake_playwright_context(_png_bytes((64, 64), (6, 7, 8)))

        with patch("playwright.sync_api.sync_playwright", return_value=fake_manager):
            bufs = _render_web_frames_persistent(
                "http://example.com",
                [0.0, 1.0],
                "t",
                save_raw_path=str(out),
            )

        assert out.exists()
        assert len(bufs) == 2
        assert bufs[0].get_pixel(0, 0) == (6, 7, 8)
