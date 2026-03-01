"""Step definitions for animation.feature."""

import time

from behave import given, when, then

from pypixoo import Pixoo
from pypixoo.animation import AnimationPlayer, AnimationSequence, Frame
from pypixoo.buffer import Buffer


def _solid_buffer(r: int, g: int, b: int) -> Buffer:
    data = [c for _ in range(64 * 64) for c in (r, g, b)]
    return Buffer.from_flat_list(data)


def _frame_transparent_center_magenta_edges() -> Buffer:
    """Frame: center (31,31) is black (transparent); rest magenta."""
    data = []
    for y in range(64):
        for x in range(64):
            if 30 <= x <= 33 and 30 <= y <= 33:
                data.extend([0, 0, 0])
            else:
                data.extend([255, 0, 255])
    return Buffer.from_flat_list(data)


@given('a 2-frame sequence with {duration}ms duration each')
def step_two_frame_sequence(context, duration):
    black = _solid_buffer(0, 0, 0)
    context.sequence = AnimationSequence(
        frames=[
            Frame(image=black, duration_ms=int(duration)),
            Frame(image=black, duration_ms=int(duration)),
        ]
    )
    context.player_kwargs = {}


@given('a 1-frame sequence with solid color {r} {g} {b} and duration {d}')
def step_one_frame_solid(context, r, g, b, d):
    buf = _solid_buffer(int(r), int(g), int(b))
    context.sequence = AnimationSequence(
        frames=[Frame(image=buf, duration_ms=int(d))]
    )
    context.player_kwargs = {}


@given('a 1-frame sequence with transparent center and magenta background')
def step_one_frame_transparent_center(context):
    frame_buf = _frame_transparent_center_magenta_edges()
    bg_buf = _solid_buffer(255, 0, 255)
    context.sequence = AnimationSequence(
        frames=[Frame(image=frame_buf, duration_ms=0)],
        background=bg_buf,
    )
    context.player_kwargs = {}


@given('a 2-frame sequence with different colors')
def step_two_frame_different_colors(context):
    red = _solid_buffer(255, 0, 0)
    blue = _solid_buffer(0, 0, 255)
    context.sequence = AnimationSequence(
        frames=[
            Frame(image=red, duration_ms=0),
            Frame(image=blue, duration_ms=0),
        ]
    )
    context.player_kwargs = {"end_on": "last_frame"}


@given('end on last frame')
def step_end_on_last_frame(context):
    context.player_kwargs["end_on"] = "last_frame"


@given('end on blank with background color {r} {g} {b}')
def step_end_on_blank(context, r, g, b):
    context.player_kwargs["end_on"] = "blank"
    context.player_kwargs["blank_background"] = _solid_buffer(int(r), int(g), int(b))


@given('blend mode opaque')
def step_blend_opaque(context):
    context.player_kwargs["blend_mode"] = "opaque"


@given('loop {n} times')
def step_loop_n(context, n):
    context.player_kwargs["loop"] = int(n)


@given('an on_finished callback')
def step_on_finished_callback(context):
    context.on_finished_called = []
    context.player_kwargs["on_finished"] = lambda: context.on_finished_called.append(True)


@given('an on_loop callback')
def step_on_loop_callback(context):
    context.on_loop_calls = []
    context.player_kwargs["on_loop"] = lambda n: context.on_loop_calls.append(n)


@given('a 1-frame sequence with {d}ms duration and loop forever')
def step_one_frame_loop_forever(context, d):
    black = _solid_buffer(0, 0, 0)
    context.sequence = AnimationSequence(
        frames=[Frame(image=black, duration_ms=int(d))]
    )
    context.player_kwargs = {"loop": None}


@when('I play the animation async')
def step_play_async(context):
    kwargs = getattr(context, "player_kwargs", {})
    context.player = AnimationPlayer(context.sequence, **kwargs)
    context.player.play_async(context.pixoo)


@when('I play the animation async with transparent blend')
def step_play_async_transparent(context):
    kwargs = getattr(context, "player_kwargs", {}).copy()
    kwargs["blend_mode"] = "transparent"
    context.player = AnimationPlayer(context.sequence, **kwargs)
    context.player.play_async(context.pixoo)


@when('I play the animation async with transparent blend and no background')
def step_play_async_transparent_no_bg(context):
    context.animation_error = None
    seq = AnimationSequence(
        frames=[Frame(image=_solid_buffer(255, 0, 0), duration_ms=0)],
        background=None,
    )
    try:
        player = AnimationPlayer(seq, blend_mode="transparent")
        player.play_async(context.pixoo)
    except Exception as e:
        context.animation_error = e


@when('I play the animation async again')
def step_play_async_again(context):
    context.animation_error = None
    try:
        context.player.play_async(context.pixoo)
    except Exception as e:
        context.animation_error = e


@when('I wait a short time')
def step_wait_short(context):
    time.sleep(0.1)


@when('I wait for the animation to complete')
def step_wait_animation(context):
    context.player.wait()


@then('the animation should have pushed {n} frames')
def step_assert_push_count(context, n):
    history = context._push_history
    assert len(history) == int(n), f"Expected {n} pushes, got {len(history)}"


@then('the first pushed frame should be solid RGB {r} {g} {b}')
def step_assert_first_frame_solid(context, r, g, b):
    history = context._push_history
    assert len(history) >= 1, "No pushes recorded"
    data = history[0]
    expected = (int(r), int(g), int(b))
    for i in range(0, len(data), 3):
        pixel = (data[i], data[i + 1], data[i + 2])
        assert pixel == expected, f"Expected {expected}, got {pixel} at index {i}"


@then('the first pushed frame should have magenta at center')
def step_assert_first_frame_magenta_center(context):
    history = context._push_history
    assert len(history) >= 1, "No pushes recorded"
    data = history[0]
    center_idx = (31 * 64 + 31) * 3
    pixel = (data[center_idx], data[center_idx + 1], data[center_idx + 2])
    assert pixel == (255, 0, 255), f"Expected magenta at center, got {pixel}"


@then('the last pushed frame should match the last frame of the sequence')
def step_assert_last_matches_last_frame(context):
    history = context._push_history
    assert len(history) >= 1, "No pushes recorded"
    last_frame = context.sequence.frames[-1]
    expected = list(last_frame.image.data)
    actual = history[-1]
    assert actual == expected, f"Last frame mismatch"


@then('the on_finished callback should have been called')
def step_assert_on_finished_called(context):
    assert getattr(context, "on_finished_called", []), "on_finished was not called"
    assert len(context.on_finished_called) >= 1, "on_finished should have been called at least once"


@then('the on_loop callback should have been called {n} times')
def step_assert_on_loop_called_n(context, n):
    calls = getattr(context, "on_loop_calls", [])
    assert len(calls) == int(n), f"Expected on_loop to be called {n} times, got {len(calls)}"


@then('an animation ValueError should occur')
def step_animation_value_error(context):
    assert getattr(context, "animation_error", None) is not None
    assert isinstance(context.animation_error, ValueError)


@then('an animation RuntimeError should occur')
def step_animation_runtime_error(context):
    assert getattr(context, "animation_error", None) is not None
    assert isinstance(context.animation_error, RuntimeError)


@then('the last pushed frame should be solid RGB {r} {g} {b}')
def step_assert_last_frame_solid(context, r, g, b):
    history = context._push_history
    assert len(history) >= 1, "No pushes recorded"
    data = history[-1]
    expected = (int(r), int(g), int(b))
    for i in range(0, len(data), 3):
        pixel = (data[i], data[i + 1], data[i + 2])
        assert pixel == expected, f"Expected {expected}, got {pixel} at index {i}"
