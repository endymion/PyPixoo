"""First-class raster streaming APIs built on top of Pixoo transport."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import AsyncIterable, Callable, Iterable, Optional, Protocol, TypeVar, Union

import requests

from pypixoo.buffer import Buffer
from pypixoo.pixoo import Pixoo

_T = TypeVar("_T")


class FrameSink(Protocol):
    """Low-level output target for rendered frames."""

    def push(self, frame: Buffer) -> None:
        """Push a single frame synchronously."""

    async def push_async(self, frame: Buffer) -> None:
        """Push a single frame asynchronously."""

    def reconnect(self) -> None:
        """Restore output connectivity when possible."""


@dataclass(frozen=True)
class StreamStats:
    """Basic stream telemetry for pacing and health reporting."""

    frames_sent: int
    late_frames: int
    avg_push_ms: float


def _is_connection_loss(exc: Exception) -> bool:
    if isinstance(exc, requests.exceptions.RequestException):
        return True
    msg = str(exc).lower()
    return any(
        token in msg
        for token in (
            "failed to connect",
            "connection refused",
            "connection reset",
            "remote disconnected",
            "max retries exceeded",
            "timed out",
            "timeout",
            "connection aborted",
            "temporarily unavailable",
            "broken pipe",
        )
    )


class PixooFrameSink:
    """Frame sink that pushes buffers to a Pixoo device."""

    def __init__(
        self,
        pixoo: Pixoo,
        reconnect: bool = True,
        reconnect_delay_s: float = 1.0,
        on_reconnect: Optional[Callable[[], None]] = None,
    ):
        self._pixoo = pixoo
        self._reconnect_enabled = reconnect
        self._reconnect_delay_s = max(0.1, reconnect_delay_s)
        self._on_reconnect = on_reconnect

    def push(self, frame: Buffer) -> None:
        """Push frame to device, retrying once after reconnect on transport loss."""
        payload = list(frame.data)
        try:
            self._pixoo.push_buffer(payload)
            return
        except Exception as exc:
            if not self._reconnect_enabled or not _is_connection_loss(exc):
                raise

        self.reconnect()
        self._pixoo.push_buffer(payload)

    async def push_async(self, frame: Buffer) -> None:
        """Async wrapper around sync push for compatibility with async engines."""
        await asyncio.to_thread(self.push, frame)

    def reconnect(self) -> None:
        """Keep reconnecting until the device responds."""
        delay = self._reconnect_delay_s
        while True:
            try:
                self._pixoo.close()
            except Exception:
                pass
            try:
                if self._pixoo.connect():
                    if self._on_reconnect is not None:
                        try:
                            self._on_reconnect()
                        except Exception:
                            pass
                    return
            except Exception:
                pass
            time.sleep(delay)
            delay = min(10.0, delay * 1.5)


def _next_sync_frame(
    source: Union[Iterable[Buffer], Callable[[], Buffer]],
    state: dict,
) -> Buffer:
    if callable(source):
        return source()
    iterator = state.get("iterator")
    if iterator is None:
        iterator = iter(source)
        state["iterator"] = iterator
    return next(iterator)


async def _next_async_frame(
    source: Union[AsyncIterable[Buffer], Callable[[], Buffer]],
    state: dict,
) -> Buffer:
    if callable(source):
        return source()
    iterator = state.get("iterator")
    if iterator is None:
        iterator = source.__aiter__()
        state["iterator"] = iterator
    return await iterator.__anext__()


class RasterClient:
    """Synchronous frame pushing and paced streaming."""

    def __init__(self, sink: FrameSink):
        self._sink = sink

    def push_frame(self, frame: Buffer) -> None:
        """Push a single frame."""
        self._sink.push(frame)

    def stream_frames(
        self,
        frames: Union[Iterable[Buffer], Callable[[], Buffer]],
        *,
        fps: int,
        duration_s: Optional[float] = None,
    ) -> StreamStats:
        """Push a frame stream with wall-clock pacing."""
        if fps <= 0:
            raise ValueError("fps must be > 0")
        if callable(frames) and duration_s is None:
            raise ValueError("duration_s is required when frames is a callable source")
        if duration_s is not None and duration_s <= 0:
            raise ValueError("duration_s must be > 0")

        interval = 1.0 / fps
        state: dict = {}
        frames_sent = 0
        late_frames = 0
        total_push_ms = 0.0

        start = time.monotonic()
        target = start

        while True:
            now = time.monotonic()
            if duration_s is not None and (now - start) >= duration_s:
                break

            if now - target > 0.001:
                late_frames += 1

            try:
                frame = _next_sync_frame(frames, state)
            except StopIteration:
                break

            push_started = time.monotonic()
            self._sink.push(frame)
            total_push_ms += (time.monotonic() - push_started) * 1000.0
            frames_sent += 1

            target += interval
            sleep_for = target - time.monotonic()
            if sleep_for > 0:
                time.sleep(sleep_for)
            else:
                while target <= time.monotonic():
                    target += interval

        avg_push_ms = total_push_ms / frames_sent if frames_sent else 0.0
        return StreamStats(
            frames_sent=frames_sent,
            late_frames=late_frames,
            avg_push_ms=avg_push_ms,
        )


class AsyncRasterClient:
    """Async frame pushing and paced streaming."""

    def __init__(self, sink: FrameSink):
        self._sink = sink

    async def push_frame(self, frame: Buffer) -> None:
        """Push a single frame asynchronously."""
        await self._sink.push_async(frame)

    async def stream_frames(
        self,
        frames: Union[AsyncIterable[Buffer], Callable[[], Buffer]],
        *,
        fps: int,
        duration_s: Optional[float] = None,
    ) -> StreamStats:
        """Push a frame stream with wall-clock pacing."""
        if fps <= 0:
            raise ValueError("fps must be > 0")
        if callable(frames) and duration_s is None:
            raise ValueError("duration_s is required when frames is a callable source")
        if duration_s is not None and duration_s <= 0:
            raise ValueError("duration_s must be > 0")

        interval = 1.0 / fps
        state: dict = {}
        frames_sent = 0
        late_frames = 0
        total_push_ms = 0.0

        start = time.monotonic()
        target = start

        while True:
            now = time.monotonic()
            if duration_s is not None and (now - start) >= duration_s:
                break

            if now - target > 0.001:
                late_frames += 1

            try:
                frame = await _next_async_frame(frames, state)
            except StopAsyncIteration:
                break

            push_started = time.monotonic()
            await self._sink.push_async(frame)
            total_push_ms += (time.monotonic() - push_started) * 1000.0
            frames_sent += 1

            target += interval
            sleep_for = target - time.monotonic()
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)
            else:
                while target <= time.monotonic():
                    target += interval

        avg_push_ms = total_push_ms / frames_sent if frames_sent else 0.0
        return StreamStats(
            frames_sent=frames_sent,
            late_frames=late_frames,
            avg_push_ms=avg_push_ms,
        )
