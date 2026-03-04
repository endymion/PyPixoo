"""Transition definitions and planning for scene compositing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal, Optional

from pypixoo.buffer import Buffer


TransitionKind = Literal[
    "cut",
    "cross_fade",
    "push_left",
    "push_right",
    "push_up",
    "push_down",
    "slide_over_left",
    "slide_over_right",
    "slide_over_up",
    "slide_over_down",
    "wipe_left",
    "wipe_right",
    "wipe_up",
    "wipe_down",
    "custom",
]

EasingKind = Literal["linear", "ease_in", "ease_out", "ease_in_out"]


@dataclass(frozen=True)
class TransitionContext:
    """Progress metadata passed to custom compositors."""

    progress: float
    raw_progress: float
    width: int
    height: int


CustomCompositor = Callable[
    [Buffer, Buffer, Optional[Buffer], TransitionContext],
    Buffer,
]


@dataclass(frozen=True)
class TransitionSpec:
    """Transition behavior and timing contract."""

    kind: TransitionKind
    duration_ms: int = 500
    easing: EasingKind = "ease_in_out"
    scene_c: Optional[object] = None
    compositor: Optional[CustomCompositor] = None

    def __post_init__(self) -> None:
        if self.kind != "cut" and self.duration_ms <= 0:
            raise ValueError("duration_ms must be > 0 for animated transitions")
        if self.kind == "custom" and self.compositor is None:
            raise ValueError("custom transition requires compositor")


@dataclass(frozen=True)
class LayerTransform:
    """2D transform and visibility controls for one transition surface."""

    x: float = 0.0
    y: float = 0.0
    opacity: float = 1.0
    z: int = 0
    clip: Optional[tuple[int, int, int, int]] = None


@dataclass(frozen=True)
class TransitionFramePlan:
    """Per-frame transforms for scene A/B and optional scene C."""

    a: LayerTransform
    b: LayerTransform
    c: Optional[LayerTransform] = None


def clamp_progress(value: float) -> float:
    """Clamp floating point transition progress to [0, 1]."""
    return max(0.0, min(1.0, value))


def apply_easing(progress: float, easing: EasingKind) -> float:
    """Map linear progress into eased progress."""
    p = clamp_progress(progress)
    if easing == "linear":
        return p
    if easing == "ease_in":
        return p * p
    if easing == "ease_out":
        inv = 1.0 - p
        return 1.0 - (inv * inv)
    if easing == "ease_in_out":
        if p < 0.5:
            return 2.0 * p * p
        inv = -2.0 * p + 2.0
        return 1.0 - ((inv * inv) / 2.0)
    raise ValueError(f"Unsupported easing: {easing}")


def _wipe_clip(kind: TransitionKind, progress: float, width: int, height: int) -> tuple[int, int, int, int]:
    reveal_w = int(round(width * progress))
    reveal_h = int(round(height * progress))
    if kind == "wipe_left":
        return (max(0, width - reveal_w), 0, min(width, reveal_w), height)
    if kind == "wipe_right":
        return (0, 0, min(width, reveal_w), height)
    if kind == "wipe_up":
        return (0, max(0, height - reveal_h), width, min(height, reveal_h))
    return (0, 0, width, min(height, reveal_h))  # wipe_down


def build_transition_plan(
    kind: TransitionKind,
    *,
    progress: float,
    width: int,
    height: int,
) -> TransitionFramePlan:
    """Build layer transforms for the requested transition kind."""
    p = clamp_progress(progress)
    if kind == "cut":
        if p < 1.0:
            return TransitionFramePlan(a=LayerTransform(opacity=1.0, z=0), b=LayerTransform(opacity=0.0, z=1))
        return TransitionFramePlan(a=LayerTransform(opacity=0.0, z=0), b=LayerTransform(opacity=1.0, z=1))

    if kind == "cross_fade":
        return TransitionFramePlan(
            a=LayerTransform(opacity=1.0 - p, z=0),
            b=LayerTransform(opacity=p, z=1),
        )

    if kind == "push_left":
        return TransitionFramePlan(
            a=LayerTransform(x=-(p * width), z=0),
            b=LayerTransform(x=width - (p * width), z=1),
        )
    if kind == "push_right":
        return TransitionFramePlan(
            a=LayerTransform(x=p * width, z=0),
            b=LayerTransform(x=-width + (p * width), z=1),
        )
    if kind == "push_up":
        return TransitionFramePlan(
            a=LayerTransform(y=-(p * height), z=0),
            b=LayerTransform(y=height - (p * height), z=1),
        )
    if kind == "push_down":
        return TransitionFramePlan(
            a=LayerTransform(y=p * height, z=0),
            b=LayerTransform(y=-height + (p * height), z=1),
        )

    if kind == "slide_over_left":
        return TransitionFramePlan(
            a=LayerTransform(z=0),
            b=LayerTransform(x=width - (p * width), z=1),
        )
    if kind == "slide_over_right":
        return TransitionFramePlan(
            a=LayerTransform(z=0),
            b=LayerTransform(x=-width + (p * width), z=1),
        )
    if kind == "slide_over_up":
        return TransitionFramePlan(
            a=LayerTransform(z=0),
            b=LayerTransform(y=height - (p * height), z=1),
        )
    if kind == "slide_over_down":
        return TransitionFramePlan(
            a=LayerTransform(z=0),
            b=LayerTransform(y=-height + (p * height), z=1),
        )

    if kind in ("wipe_left", "wipe_right", "wipe_up", "wipe_down"):
        return TransitionFramePlan(
            a=LayerTransform(z=0),
            b=LayerTransform(z=1, clip=_wipe_clip(kind, p, width, height)),
        )

    if kind == "custom":
        # Custom compositor owns blending; default transforms are neutral.
        return TransitionFramePlan(
            a=LayerTransform(z=0),
            b=LayerTransform(z=1),
            c=LayerTransform(z=2),
        )

    raise ValueError(f"Unsupported transition kind: {kind}")
