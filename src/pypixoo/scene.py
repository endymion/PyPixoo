"""Scene graph runtime built on top of the raster streaming layer."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Optional, Protocol, Sequence

from pypixoo.buffer import Buffer
from pypixoo.compositor import RenderedLayer, compose_layers
from pypixoo.raster import AsyncRasterClient
from pypixoo.transitions import (
    TransitionContext,
    TransitionSpec,
    apply_easing,
    build_transition_plan,
)


@dataclass(frozen=True)
class RenderContext:
    """Per-frame render metadata."""

    epoch_s: float
    monotonic_s: float
    dt_s: float
    frame_index: int
    width: int = 64
    height: int = 64


class Layer(Protocol):
    """Renderable layer contract."""

    name: str

    def render(self, ctx: RenderContext) -> Buffer:
        """Render one full frame."""


@dataclass(frozen=True)
class LayerNode:
    """Scene layer placement and blending properties."""

    id: str
    layer: Layer
    x: float = 0.0
    y: float = 0.0
    opacity: float = 1.0
    z: int = 0
    visible: bool = True


class Scene(Protocol):
    """Composable scene of one or more layers."""

    name: str

    def layers(self, ctx: RenderContext) -> list[LayerNode]:
        """Return layers for the current frame."""

    def on_enter(self) -> None:
        """Called when the scene becomes active."""

    def on_exit(self) -> None:
        """Called when the scene is deactivated."""


@dataclass(frozen=True)
class QueueItem:
    """Queued scene transition request."""

    scene: Scene
    transition: TransitionSpec
    hold_ms: int = 0


@dataclass
class _ActiveTransition:
    from_scene: Scene
    item: QueueItem
    started_mono_s: float


def _safe_scene_hook(scene: Scene, hook_name: str) -> None:
    hook = getattr(scene, hook_name, None)
    if callable(hook):
        hook()


class ScenePlayer:
    """Async scene runtime with deterministic queued transitions."""

    def __init__(
        self,
        raster: AsyncRasterClient,
        *,
        fps: int = 3,
        max_queue: int = 32,
        width: int = 64,
        height: int = 64,
    ):
        if fps <= 0:
            raise ValueError("fps must be > 0")
        if max_queue <= 0:
            raise ValueError("max_queue must be > 0")
        self._raster = raster
        self._fps = fps
        self._interval_s = 1.0 / fps
        self._max_queue = max_queue
        self._width = width
        self._height = height
        self._queue: Deque[QueueItem] = deque()
        self._current_scene: Optional[Scene] = None
        self._active_transition: Optional[_ActiveTransition] = None
        self._hold_until_mono_s: float = 0.0
        self._stop_event = asyncio.Event()
        self._frame_index = 0
        self._last_mono_s = 0.0
        self._debug = False

    async def set_scene(self, scene: Scene) -> None:
        """Set active scene immediately."""
        if self._current_scene is not None and self._current_scene is not scene:
            _safe_scene_hook(self._current_scene, "on_exit")
        self._current_scene = scene
        self._active_transition = None
        self._hold_until_mono_s = 0.0
        _safe_scene_hook(scene, "on_enter")
        if self._debug:
            name = getattr(scene, "name", scene.__class__.__name__)
            print(f"scene: set_scene -> {name}")

    async def enqueue(self, item: QueueItem) -> None:
        """Queue scene transition in FIFO order."""
        if len(self._queue) >= self._max_queue:
            raise ValueError("scene transition queue is full")
        self._queue.append(item)
        if self._debug:
            scene_name = getattr(item.scene, "name", item.scene.__class__.__name__)
            print(
                "scene: enqueue "
                f"{scene_name} transition={item.transition.kind} hold_ms={item.hold_ms} "
                f"queue_depth={len(self._queue)}"
            )

    async def clear_queue(self) -> None:
        """Drop pending transition requests."""
        self._queue.clear()

    async def stop(self) -> None:
        """Signal run loop to stop."""
        self._stop_event.set()

    @property
    def queue_depth(self) -> int:
        """Current number of pending queued transitions."""
        return len(self._queue)

    def _render_scene(self, scene: Scene, ctx: RenderContext) -> Buffer:
        layers: Sequence[LayerNode] = scene.layers(ctx)
        rendered_layers: list[RenderedLayer] = []
        for node in layers:
            if not node.visible:
                continue
            buffer = node.layer.render(ctx)
            rendered_layers.append(
                RenderedLayer(
                    buffer=buffer,
                    x=node.x,
                    y=node.y,
                    opacity=max(0.0, min(1.0, node.opacity)),
                    z=node.z,
                    visible=node.visible,
                )
            )
        return compose_layers(
            rendered_layers,
            width=self._width,
            height=self._height,
        )

    def _start_next_transition(self, now_mono_s: float) -> None:
        if self._active_transition is not None or not self._queue or self._current_scene is None:
            return
        if now_mono_s < self._hold_until_mono_s:
            return

        item = self._queue.popleft()
        _safe_scene_hook(item.scene, "on_enter")
        self._active_transition = _ActiveTransition(
            from_scene=self._current_scene,
            item=item,
            started_mono_s=now_mono_s,
        )
        if self._debug:
            from_name = getattr(self._current_scene, "name", self._current_scene.__class__.__name__)
            to_name = getattr(item.scene, "name", item.scene.__class__.__name__)
            print(
                "scene: transition start "
                f"{from_name} -> {to_name} "
                f"kind={item.transition.kind} duration_ms={item.transition.duration_ms}"
            )

    def _render_transition_frame(
        self,
        ctx: RenderContext,
        now_mono_s: float,
    ) -> Buffer:
        assert self._active_transition is not None
        active = self._active_transition
        spec = active.item.transition
        elapsed_s = max(0.0, now_mono_s - active.started_mono_s)
        if spec.kind == "cut":
            raw_progress = 1.0
        else:
            raw_progress = min(1.0, elapsed_s / (spec.duration_ms / 1000.0))
        eased_progress = apply_easing(raw_progress, spec.easing)

        from_buf = self._render_scene(active.from_scene, ctx)
        to_buf = self._render_scene(active.item.scene, ctx)

        if spec.kind == "custom":
            assert spec.compositor is not None
            scene_c_buf = None
            if spec.scene_c is not None:
                scene_c_buf = self._render_scene(spec.scene_c, ctx)
            output = spec.compositor(
                from_buf,
                to_buf,
                scene_c_buf,
                TransitionContext(
                    progress=eased_progress,
                    raw_progress=raw_progress,
                    width=self._width,
                    height=self._height,
                ),
            )
        else:
            plan = build_transition_plan(
                spec.kind,
                progress=eased_progress,
                width=self._width,
                height=self._height,
            )
            rendered = [
                RenderedLayer(
                    buffer=from_buf,
                    x=plan.a.x,
                    y=plan.a.y,
                    opacity=plan.a.opacity,
                    z=plan.a.z,
                    clip=plan.a.clip,
                ),
                RenderedLayer(
                    buffer=to_buf,
                    x=plan.b.x,
                    y=plan.b.y,
                    opacity=plan.b.opacity,
                    z=plan.b.z,
                    clip=plan.b.clip,
                ),
            ]
            if plan.c is not None and spec.scene_c is not None:
                rendered.append(
                    RenderedLayer(
                        buffer=self._render_scene(spec.scene_c, ctx),
                        x=plan.c.x,
                        y=plan.c.y,
                        opacity=plan.c.opacity,
                        z=plan.c.z,
                        clip=plan.c.clip,
                    )
                )
            output = compose_layers(
                rendered,
                width=self._width,
                height=self._height,
            )

        if raw_progress >= 1.0:
            _safe_scene_hook(active.from_scene, "on_exit")
            self._current_scene = active.item.scene
            self._active_transition = None
            hold_ms = max(0, active.item.hold_ms)
            self._hold_until_mono_s = now_mono_s + (hold_ms / 1000.0)
            if self._debug:
                to_name = getattr(active.item.scene, "name", active.item.scene.__class__.__name__)
                print(
                    "scene: transition end "
                    f"to={to_name} hold_ms={hold_ms}"
                )

        return output

    async def run(self) -> None:
        """Run rendering loop until stop() is called."""
        if self._current_scene is None:
            raise ValueError("set_scene() must be called before run()")

        self._stop_event.clear()
        self._frame_index = 0
        self._last_mono_s = time.monotonic()
        next_tick = self._last_mono_s

        while not self._stop_event.is_set():
            now_epoch = time.time()
            now_mono = time.monotonic()
            dt_s = max(0.0, now_mono - self._last_mono_s)
            self._last_mono_s = now_mono

            self._start_next_transition(now_mono)

            ctx = RenderContext(
                epoch_s=now_epoch,
                monotonic_s=now_mono,
                dt_s=dt_s,
                frame_index=self._frame_index,
                width=self._width,
                height=self._height,
            )
            if self._active_transition is not None:
                frame = self._render_transition_frame(ctx, now_mono)
            else:
                assert self._current_scene is not None
                frame = self._render_scene(self._current_scene, ctx)

            await self._raster.push_frame(frame)
            self._frame_index += 1

            next_tick += self._interval_s
            sleep_for = next_tick - time.monotonic()
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)
            else:
                while next_tick <= time.monotonic():
                    next_tick += self._interval_s
