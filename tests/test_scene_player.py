"""Tests for scene runtime queueing and timing behavior."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from pypixoo.buffer import Buffer
from pypixoo.raster import AsyncRasterClient
from pypixoo.scene import LayerNode, QueueItem, RenderContext, ScenePlayer
from pypixoo.transitions import TransitionSpec


def _solid(color: tuple[int, int, int]) -> Buffer:
    return Buffer.from_flat_list([component for _ in range(64 * 64) for component in color])


class _Sink:
    def __init__(self, push_delay_s: float = 0.0):
        self.frames = []
        self.push_delay_s = push_delay_s

    def push(self, frame: Buffer) -> None:
        self.frames.append(frame)

    async def push_async(self, frame: Buffer) -> None:
        if self.push_delay_s > 0:
            await asyncio.sleep(self.push_delay_s)
        self.frames.append(frame)

    def reconnect(self) -> None:
        return


@dataclass
class _Layer:
    name: str
    color: tuple[int, int, int]

    def render(self, ctx: RenderContext) -> Buffer:
        return _solid(self.color)


class _Scene:
    def __init__(self, name: str, color: tuple[int, int, int]):
        self.name = name
        self._layer = _Layer(name=f"{name}-layer", color=color)
        self.entered = 0
        self.exited = 0

    def layers(self, ctx: RenderContext) -> list[LayerNode]:
        return [LayerNode(id=f"{self.name}-node", layer=self._layer)]

    def on_enter(self) -> None:
        self.entered += 1

    def on_exit(self) -> None:
        self.exited += 1


async def _run_for(player: ScenePlayer, duration_s: float) -> None:
    task = asyncio.create_task(player.run())
    try:
        await asyncio.sleep(duration_s)
    finally:
        await player.stop()
        await task


def test_scene_player_queue_fifo_and_lifecycle():
    async def _run() -> None:
        sink = _Sink()
        raster = AsyncRasterClient(sink)
        player = ScenePlayer(raster, fps=30, max_queue=8)
        scene_a = _Scene("a", (10, 10, 10))
        scene_b = _Scene("b", (20, 20, 20))
        scene_c = _Scene("c", (30, 30, 30))

        await player.set_scene(scene_a)
        await player.enqueue(QueueItem(scene=scene_b, transition=TransitionSpec(kind="cross_fade", duration_ms=20)))
        await player.enqueue(QueueItem(scene=scene_c, transition=TransitionSpec(kind="cut", duration_ms=1)))
        await _run_for(player, 0.25)

        assert len(sink.frames) > 0
        assert scene_b.entered >= 1
        assert scene_a.exited >= 1
        assert player._current_scene is scene_c

    asyncio.run(_run())


def test_scene_player_clear_queue_keeps_current_scene():
    async def _run() -> None:
        sink = _Sink()
        raster = AsyncRasterClient(sink)
        player = ScenePlayer(raster, fps=20)
        scene_a = _Scene("a", (1, 1, 1))
        scene_b = _Scene("b", (2, 2, 2))

        await player.set_scene(scene_a)
        await player.enqueue(QueueItem(scene=scene_b, transition=TransitionSpec(kind="push_left", duration_ms=100)))
        await player.clear_queue()
        await _run_for(player, 0.12)
        assert player._current_scene is scene_a

    asyncio.run(_run())


def test_scene_player_late_frame_path_still_runs():
    async def _run() -> None:
        sink = _Sink(push_delay_s=0.05)
        raster = AsyncRasterClient(sink)
        player = ScenePlayer(raster, fps=30)
        scene = _Scene("slow", (80, 80, 80))
        await player.set_scene(scene)
        await _run_for(player, 0.2)
        assert len(sink.frames) > 0

    asyncio.run(_run())


def test_scene_player_requires_scene_before_run():
    async def _run() -> None:
        sink = _Sink()
        player = ScenePlayer(AsyncRasterClient(sink), fps=5)
        try:
            await player.run()
        except ValueError as exc:
            assert "set_scene" in str(exc)
        else:
            raise AssertionError("Expected ValueError when run() called without set_scene")

    asyncio.run(_run())
