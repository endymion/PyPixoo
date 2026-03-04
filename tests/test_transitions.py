"""Tests for transition planning semantics."""

from __future__ import annotations

import pytest

from pypixoo.transitions import (
    TransitionSpec,
    apply_easing,
    build_transition_plan,
)


def test_push_and_slide_have_distinct_semantics():
    push = build_transition_plan("push_left", progress=0.5, width=64, height=64)
    slide = build_transition_plan("slide_over_left", progress=0.5, width=64, height=64)
    assert push.a.x < 0
    assert slide.a.x == 0
    assert push.b.x == slide.b.x


def test_transition_endpoints_for_push_left():
    start = build_transition_plan("push_left", progress=0.0, width=64, height=64)
    end = build_transition_plan("push_left", progress=1.0, width=64, height=64)
    assert start.a.x == 0
    assert start.b.x == 64
    assert end.a.x == -64
    assert end.b.x == 0


def test_wipe_clip_fills_frame_at_completion():
    end = build_transition_plan("wipe_right", progress=1.0, width=64, height=64)
    assert end.b.clip == (0, 0, 64, 64)


def test_easing_is_monotonic():
    p0 = apply_easing(0.1, "ease_in_out")
    p1 = apply_easing(0.5, "ease_in_out")
    p2 = apply_easing(0.9, "ease_in_out")
    assert 0 <= p0 < p1 < p2 <= 1


def test_custom_transition_requires_compositor():
    with pytest.raises(ValueError, match="requires compositor"):
        TransitionSpec(kind="custom")
