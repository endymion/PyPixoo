"""Headless browser rendering for Pixoo 64 frame generation."""

import io
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable, Dict, List, Literal, Optional, Union

from PIL import Image
from pydantic import BaseModel, Field

from pypixoo.animation import AnimationSequence, Frame
from pypixoo.buffer import Buffer

SIZE = 64


class StaticFrameSource(BaseModel):
    """Pre-resolved frame; no rendering required."""

    buffer: Buffer
    duration_ms: int = Field(ge=0)


class WebFrameSource(BaseModel):
    """Frame source rendered via headless browser at given timestamps."""

    url: str
    timestamps: List[float]
    duration_per_frame_ms: int = Field(ge=0)
    browser_mode: Literal["persistent", "per_frame"] = "persistent"
    timestamp_param: str = "t"


def _url_with_timestamp(base_url: str, timestamp: float, param: str) -> str:
    sep = "&" if "?" in base_url else "?"
    return f"{base_url}{sep}{param}={timestamp}"


def _screenshot_to_buffer(screenshot_bytes: bytes) -> Buffer:
    """Convert Playwright screenshot bytes to 64×64 RGB Buffer."""
    img = Image.open(io.BytesIO(screenshot_bytes)).convert("RGB")
    if img.size != (SIZE, SIZE):
        img = img.resize((SIZE, SIZE), Image.Resampling.NEAREST)
    data = [c for pixel in img.getdata() for c in pixel]
    return Buffer.from_flat_list(data)


def _render_web_frame(url: str, timestamp: float, param: str) -> Buffer:
    """Render a single web frame using Playwright; returns Buffer."""
    from playwright.sync_api import sync_playwright

    full_url = _url_with_timestamp(url, timestamp, param)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_viewport_size({"width": SIZE, "height": SIZE})
        page.goto(full_url, wait_until="networkidle")
        screenshot_bytes = page.screenshot()
        browser.close()
    return _screenshot_to_buffer(screenshot_bytes)


def _render_web_frames_persistent(
    url: str,
    timestamps: List[float],
    param: str,
) -> List[Buffer]:
    """Render frames using one persistent page."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_viewport_size({"width": SIZE, "height": SIZE})
        buffers: List[Buffer] = []
        for ts in timestamps:
            full_url = _url_with_timestamp(url, ts, param)
            page.goto(full_url, wait_until="networkidle")
            screenshot_bytes = page.screenshot()
            buffers.append(_screenshot_to_buffer(screenshot_bytes))
        browser.close()
    return buffers


def _render_web_frames_per_frame(
    url: str,
    timestamps: List[float],
    param: str,
) -> List[Buffer]:
    """Render frames using a new page per frame."""
    return [_render_web_frame(url, ts, param) for ts in timestamps]


class FrameRenderer:
    """Pre-computes frames from static and web sources; fires on_first_frame and on_all_frames."""

    def __init__(
        self,
        sources: List[Union[StaticFrameSource, WebFrameSource]],
        *,
        background: Optional[Buffer] = None,
    ):
        self.sources = sources
        self.background = background
        self._sequence: Optional[AnimationSequence] = None

    def precompute(
        self,
        *,
        on_first_frame: Optional[Callable[[], None]] = None,
        on_all_frames: Optional[Callable[[], None]] = None,
    ) -> AnimationSequence:
        """Render web frames asynchronously; return AnimationSequence when done."""
        first_web_fired = [False]

        def _run_web(source: WebFrameSource) -> List[Frame]:
            if source.browser_mode == "persistent":
                bufs = _render_web_frames_persistent(
                    source.url,
                    source.timestamps,
                    source.timestamp_param,
                )
            else:
                bufs = _render_web_frames_per_frame(
                    source.url,
                    source.timestamps,
                    source.timestamp_param,
                )
            result = [
                Frame(image=buf, duration_ms=source.duration_per_frame_ms)
                for buf in bufs
            ]
            if on_first_frame is not None and not first_web_fired[0]:
                first_web_fired[0] = True
                on_first_frame()
            return result

        source_futures: Dict[int, Future] = {}
        with ThreadPoolExecutor(max_workers=4) as executor:
            for i, src in enumerate(self.sources):
                if isinstance(src, WebFrameSource):
                    source_futures[i] = executor.submit(_run_web, src)

            frames: List[Frame] = []
            for i, src in enumerate(self.sources):
                if isinstance(src, StaticFrameSource):
                    frames.append(
                        Frame(image=src.buffer, duration_ms=src.duration_ms)
                    )
                else:
                    frames.extend(source_futures[i].result())

        if on_all_frames is not None:
            on_all_frames()

        self._sequence = AnimationSequence(
            frames=frames,
            background=self.background,
        )
        return self._sequence
