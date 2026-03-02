"""Headless browser rendering for Pixoo 64 frame generation."""

import io
from pathlib import Path
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable, Dict, List, Literal, Optional, Union

from PIL import Image
from pydantic import BaseModel, Field

from pypixoo.buffer import Buffer
from pypixoo.native import GifFrame, GifSequence

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
    device_scale_factor: Literal[1, 2, 3] = Field(
        default=3,
        description="1=64x64, 2=128x128 then 2x2 max-pool, 3=192x192 then 3x3 max-pool so 5px glyphs become 5 rows.",
    )
    viewport_size: Literal[64, 192] = Field(
        default=64,
        description="When 192, viewport 192x192 and scale 1; page uses 15px font so 3x3 downscale gives 5 rows.",
    )
    save_raw_screenshot_path: Optional[str] = Field(
        default=None,
        description="If set, write the full-resolution screenshot (e.g. 192x192) to this path before downsampling.",
    )
    downsample_mode: Literal["maxpool", "nearest"] = Field(
        default="maxpool",
        description="64x64 reduction mode for 2x/3x captures. maxpool preserves thin strokes; nearest preserves hard pixel grids.",
    )


def _url_with_timestamp(base_url: str, timestamp: float, param: str) -> str:
    sep = "&" if "?" in base_url else "?"
    return f"{base_url}{sep}{param}={timestamp}"


def _screenshot_to_buffer(
    screenshot_bytes: bytes,
    downsample_mode: Literal["maxpool", "nearest"] = "maxpool",
) -> Buffer:
    """Convert Playwright screenshot bytes to 64×64 RGB Buffer.

    Captures at 2× (128×128) with device_scale_factor and downsamples using
    BOX (2×2 block average) to fix pixel-grid alignment. A half-pixel shift
    or subpixel positioning in the browser would otherwise cause illegible
    text on the device.
    """
    img = Image.open(io.BytesIO(screenshot_bytes)).convert("RGB")
    if img.size == (SIZE * 3, SIZE * 3):
        if downsample_mode == "nearest":
            img = img.resize((SIZE, SIZE), Image.Resampling.NEAREST)
            data = [c for pixel in img.getdata() for c in pixel]
            return Buffer.from_flat_list(data)
        src = img.load()
        data = []
        for oy in range(SIZE):
            for ox in range(SIZE):
                r = g = b = 0
                for dy in range(3):
                    for dx in range(3):
                        px = src[ox * 3 + dx, oy * 3 + dy]
                        r, g, b = max(r, px[0]), max(g, px[1]), max(b, px[2])
                data.extend((r, g, b))
        return Buffer.from_flat_list(data)
    if img.size == (SIZE * 2, SIZE * 2):
        if downsample_mode == "nearest":
            img = img.resize((SIZE, SIZE), Image.Resampling.NEAREST)
            data = [c for pixel in img.getdata() for c in pixel]
            return Buffer.from_flat_list(data)
        src = img.load()
        data = []
        for oy in range(SIZE):
            for ox in range(SIZE):
                r = g = b = 0
                for dy in range(2):
                    for dx in range(2):
                        px = src[ox * 2 + dx, oy * 2 + dy]
                        r, g, b = max(r, px[0]), max(g, px[1]), max(b, px[2])
                data.extend((r, g, b))
        return Buffer.from_flat_list(data)
    if img.size != (SIZE, SIZE):
        img = img.resize((SIZE, SIZE), Image.Resampling.NEAREST)
    data = [c for pixel in img.getdata() for c in pixel]
    return Buffer.from_flat_list(data)


def _wait_for_page_fonts(page, timeout_ms: int = 8000) -> None:
    """Wait for the page's active font family/size instead of a fixed spec."""
    try:
        page.evaluate("() => document.fonts?.ready")
    except Exception:
        return
    try:
        page.wait_for_function(
            """() => {
                if (!document.fonts || !document.fonts.check) return true;
                const target = document.querySelector('.char') || document.body;
                const style = getComputedStyle(target);
                const size = style.fontSize || '16px';
                const familyRaw = style.fontFamily || '';
                const family = familyRaw.split(',')[0].trim().replace(/^['"]|['"]$/g, '');
                if (!family) return true;
                return (
                    document.fonts.check(`${size} "${family}"`) ||
                    document.fonts.check(`${size} ${family}`) ||
                    document.fonts.check(`16px "${family}"`) ||
                    document.fonts.check(`16px ${family}`)
                );
            }""",
            timeout=timeout_ms,
        )
    except Exception:
        pass


def _wait_for_page_render_ready(page, timeout_ms: int = 20000) -> None:
    """Wait for optional page-side render-complete marker."""
    try:
        has_ready_flag = bool(page.evaluate("() => ('__pixooReady' in window)"))
    except Exception:
        return
    if not has_ready_flag:
        return
    try:
        page.wait_for_function("() => window.__pixooReady === true", timeout=timeout_ms)
    except Exception:
        pass


def _render_web_frame(
    url: str,
    timestamp: float,
    param: str,
    device_scale_factor: int = 2,
    viewport_size: int = 64,
    save_raw_path: Optional[str] = None,
    downsample_mode: Literal["maxpool", "nearest"] = "maxpool",
) -> Buffer:
    """Render a single web frame using Playwright; returns Buffer."""
    from playwright.sync_api import sync_playwright

    full_url = _url_with_timestamp(url, timestamp, param)
    vw = viewport_size if viewport_size == 192 else SIZE
    vh = viewport_size if viewport_size == 192 else SIZE
    scale = 1 if viewport_size == 192 else device_scale_factor
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": vw, "height": vh},
            device_scale_factor=scale,
        )
        page = context.new_page()
        page.goto(full_url, wait_until="networkidle")
        page.wait_for_timeout(600)
        _wait_for_page_fonts(page)
        _wait_for_page_render_ready(page)
        page.wait_for_timeout(300)
        screenshot_bytes = page.screenshot()
        if save_raw_path:
            p = Path(save_raw_path).resolve()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(screenshot_bytes)
        context.close()
        browser.close()
    return _screenshot_to_buffer(screenshot_bytes, downsample_mode)


def _render_web_frames_persistent(
    url: str,
    timestamps: List[float],
    param: str,
    device_scale_factor: int = 2,
    viewport_size: int = 64,
    save_raw_path: Optional[str] = None,
    downsample_mode: Literal["maxpool", "nearest"] = "maxpool",
) -> List[Buffer]:
    """Render frames using one persistent page."""
    from playwright.sync_api import sync_playwright

    vw = viewport_size if viewport_size == 192 else SIZE
    vh = viewport_size if viewport_size == 192 else SIZE
    scale = 1 if viewport_size == 192 else device_scale_factor
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": vw, "height": vh},
            device_scale_factor=scale,
        )
        page = context.new_page()
        buffers: List[Buffer] = []
        for idx, ts in enumerate(timestamps):
            full_url = _url_with_timestamp(url, ts, param)
            page.goto(full_url, wait_until="networkidle")
            page.wait_for_timeout(600)
            _wait_for_page_fonts(page)
            _wait_for_page_render_ready(page)
            page.wait_for_timeout(300)
            screenshot_bytes = page.screenshot()
            if save_raw_path and idx == 0:
                p = Path(save_raw_path).resolve()
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(screenshot_bytes)
            buffers.append(_screenshot_to_buffer(screenshot_bytes, downsample_mode))
        context.close()
        browser.close()
    return buffers


def _render_web_frames_per_frame(
    url: str,
    timestamps: List[float],
    param: str,
    device_scale_factor: int = 2,
    viewport_size: int = 64,
    save_raw_path: Optional[str] = None,
    downsample_mode: Literal["maxpool", "nearest"] = "maxpool",
) -> List[Buffer]:
    """Render frames using a new page per frame."""
    return [
        _render_web_frame(
            url,
            ts,
            param,
            device_scale_factor,
            viewport_size,
            save_raw_path if i == 0 else None,
            downsample_mode,
        )
        for i, ts in enumerate(timestamps)
    ]


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
        self._sequence: Optional[GifSequence] = None

    def precompute(
        self,
        *,
        on_first_frame: Optional[Callable[[], None]] = None,
        on_all_frames: Optional[Callable[[], None]] = None,
    ) -> GifSequence:
        """Render web frames asynchronously; return GifSequence when done."""
        first_web_fired = [False]

        def _run_web(source: WebFrameSource) -> List[GifFrame]:
            scale = source.device_scale_factor
            vp = source.viewport_size
            raw_path = source.save_raw_screenshot_path
            downsample_mode = source.downsample_mode
            if source.browser_mode == "persistent":
                bufs = _render_web_frames_persistent(
                    source.url,
                    source.timestamps,
                    source.timestamp_param,
                    scale,
                    vp,
                    raw_path,
                    downsample_mode,
                )
            else:
                bufs = _render_web_frames_per_frame(
                    source.url,
                    source.timestamps,
                    source.timestamp_param,
                    scale,
                    vp,
                    raw_path,
                    downsample_mode,
                )
            result = [
                GifFrame(image=buf, duration_ms=source.duration_per_frame_ms)
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

            frames: List[GifFrame] = []
            for i, src in enumerate(self.sources):
                if isinstance(src, StaticFrameSource):
                    frames.append(
                        GifFrame(image=src.buffer, duration_ms=src.duration_ms)
                    )
                else:
                    frames.extend(source_futures[i].result())

        if on_all_frames is not None:
            on_all_frames()

        speed_ms = frames[0].duration_ms if frames else 100
        self._sequence = GifSequence(frames=frames, speed_ms=speed_ms)
        return self._sequence
