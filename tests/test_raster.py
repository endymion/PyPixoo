"""Tests for v3 raster streaming layer."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest
import requests

from pypixoo.buffer import Buffer
from pypixoo.raster import AsyncRasterClient, PixooFrameSink, RasterClient


def _frame(color: tuple[int, int, int]) -> Buffer:
    return Buffer.from_flat_list([component for _ in range(64 * 64) for component in color])


class _Sink:
    def __init__(self):
        self.frames = []
        self.reconnects = 0

    def push(self, frame: Buffer) -> None:
        self.frames.append(frame)

    async def push_async(self, frame: Buffer) -> None:
        self.frames.append(frame)

    def reconnect(self) -> None:
        self.reconnects += 1


def test_raster_push_frame_sends_single_frame():
    sink = _Sink()
    client = RasterClient(sink)
    frame = _frame((1, 2, 3))
    client.push_frame(frame)
    assert sink.frames == [frame]


def test_raster_stream_frames_iterable_collects_stats():
    sink = _Sink()
    client = RasterClient(sink)
    frames = [_frame((10, 10, 10)), _frame((20, 20, 20))]
    stats = client.stream_frames(frames, fps=30)
    assert stats.frames_sent == 2
    assert stats.avg_push_ms >= 0.0


def test_raster_stream_callable_requires_duration():
    sink = _Sink()
    client = RasterClient(sink)
    with pytest.raises(ValueError, match="duration_s is required"):
        client.stream_frames(lambda: _frame((1, 1, 1)), fps=2)


def test_pixoo_frame_sink_reconnects_on_connection_loss():
    pixoo = MagicMock()
    pixoo.push_buffer.side_effect = [requests.exceptions.ConnectionError("boom"), None]
    pixoo.connect.side_effect = [False, True]
    on_reconnect = MagicMock()

    sink = PixooFrameSink(
        pixoo,
        reconnect=True,
        reconnect_delay_s=0.001,
        on_reconnect=on_reconnect,
    )
    with patch("pypixoo.raster.time.sleep", return_value=None):
        sink.push(_frame((1, 1, 1)))

    assert pixoo.connect.call_count >= 1
    assert pixoo.push_buffer.call_count == 2
    on_reconnect.assert_called_once()


def test_async_raster_stream_parity():
    sink = _Sink()
    client = AsyncRasterClient(sink)

    async def _gen():
        yield _frame((5, 5, 5))
        yield _frame((6, 6, 6))

    async def _run():
        return await client.stream_frames(_gen(), fps=30)

    stats = asyncio.run(_run())
    assert stats.frames_sent == 2
    assert len(sink.frames) == 2
