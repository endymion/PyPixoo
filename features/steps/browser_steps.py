"""Step definitions for browser.feature."""

from behave import given, when, then

from pypixoo.browser import FrameRenderer, StaticFrameSource, WebFrameSource
from pypixoo.buffer import Buffer


def _solid_buffer(r: int, g: int, b: int) -> Buffer:
    data = [c for _ in range(64 * 64) for c in (r, g, b)]
    return Buffer.from_flat_list(data)


@given("a FrameRenderer with static sources only")
def step_static_only(context):
    buf = _solid_buffer(50, 50, 50)
    context.renderer = FrameRenderer(
        sources=[
            StaticFrameSource(buffer=buf, duration_ms=100),
            StaticFrameSource(buffer=buf, duration_ms=100),
        ]
    )


@given('a FrameRenderer with web source only at URL "{url}"')
def step_web_only(context, url):
    context.renderer = FrameRenderer(
        sources=[
            WebFrameSource(
                url=url,
                timestamps=[0.0],
                duration_per_frame_ms=100,
            )
        ]
    )
    context._web_url = url


@given("2 timestamps {ts1} {ts2}")
def step_timestamps_two(context, ts1, ts2):
    url = getattr(context, "_web_url", "http://example.com")
    context.renderer = FrameRenderer(
        sources=[
            WebFrameSource(
                url=url,
                timestamps=[float(ts1), float(ts2)],
                duration_per_frame_ms=100,
            )
        ]
    )


@given("3 timestamps {ts1} {ts2} {ts3}")
def step_timestamps_three(context, ts1, ts2, ts3):
    url = getattr(context, "_web_url", "http://example.com")
    context.renderer = FrameRenderer(
        sources=[
            WebFrameSource(
                url=url,
                timestamps=[float(ts1), float(ts2), float(ts3)],
                duration_per_frame_ms=100,
            )
        ]
    )


@given("duration per frame {ms}ms")
def step_duration_per_frame(context, ms):
    if not hasattr(context, "renderer") or not context.renderer.sources:
        return
    src = context.renderer.sources[0]
    if isinstance(src, WebFrameSource):
        context.renderer = FrameRenderer(
            sources=[
                WebFrameSource(
                    url=src.url,
                    timestamps=src.timestamps,
                    duration_per_frame_ms=int(ms),
                )
            ]
        )


@given("a FrameRenderer with mixed sources")
def step_mixed_sources(context):
    buf = _solid_buffer(80, 80, 80)
    context.renderer = FrameRenderer(
        sources=[
            StaticFrameSource(buffer=buf, duration_ms=100),
            WebFrameSource(
                url="http://placeholder",
                timestamps=[0.0],
                duration_per_frame_ms=200,
            ),
            StaticFrameSource(buffer=buf, duration_ms=100),
        ]
    )


@given('web URL "{url}" with {n} timestamp and {ms}ms duration')
def step_web_url_in_mixed(context, url, n, ms):
    buf = _solid_buffer(80, 80, 80)
    context.renderer = FrameRenderer(
        sources=[
            StaticFrameSource(buffer=buf, duration_ms=100),
            WebFrameSource(
                url=url,
                timestamps=[0.0],
                duration_per_frame_ms=int(ms),
            ),
            StaticFrameSource(buffer=buf, duration_ms=100),
        ]
    )


@given("a FrameRenderer with web source in persistent mode")
def step_web_persistent(context):
    context.renderer = FrameRenderer(
        sources=[
            WebFrameSource(
                url="http://example.com",
                timestamps=[0.0, 1.0],
                duration_per_frame_ms=100,
                browser_mode="persistent",
            )
        ]
    )


@given("a FrameRenderer with web source in per_frame mode")
def step_web_per_frame(context):
    context.renderer = FrameRenderer(
        sources=[
            WebFrameSource(
                url="http://example.com",
                timestamps=[0.0, 1.0],
                duration_per_frame_ms=100,
                browser_mode="per_frame",
            )
        ]
    )


@given('URL "{url}" and timestamps {ts1} {ts2}')
def step_url_and_timestamps(context, url, ts1, ts2):
    src = context.renderer.sources[0]
    mode = src.browser_mode if isinstance(src, WebFrameSource) else "persistent"
    context.renderer = FrameRenderer(
        sources=[
            WebFrameSource(
                url=url,
                timestamps=[float(ts1), float(ts2)],
                duration_per_frame_ms=100,
                browser_mode=mode,
            )
        ]
    )


@given("an on_first_frame callback")
def step_on_first_frame_callback(context):
    context.on_first_frame_called = []
    context._on_first_frame = lambda: context.on_first_frame_called.append(True)


@given("an on_all_frames callback")
def step_on_all_frames_callback(context):
    context.on_all_frames_called = []
    context._on_all_frames = lambda: context.on_all_frames_called.append(True)


@when("I precompute frames")
def step_precompute(context):
    on_first = context.__dict__.get("_on_first_frame")
    on_all = context.__dict__.get("_on_all_frames")
    context.sequence = context.renderer.precompute(
        on_first_frame=on_first,
        on_all_frames=on_all,
    )


@then("the sequence should have {n} frames")
def step_sequence_frame_count(context, n):
    assert len(context.sequence.frames) == int(n), (
        f"Expected {n} frames, got {len(context.sequence.frames)}"
    )


@then("each frame should have duration {ms}ms")
def step_frame_duration(context, ms):
    for f in context.sequence.frames:
        assert f.duration_ms == int(ms), (
            f"Expected duration {ms}ms, got {f.duration_ms}ms"
        )


@then("frame order should be static web static")
def step_frame_order(context):
    assert len(context.sequence.frames) >= 3
    # Static sources produce frames with our known buffer; web produces mocked gray
    # We can't easily distinguish static vs web from buffer content after mock.
    # Instead verify we have 3 frames and they're in the right structure:
    # frame 0 from static, frame 1 from web, frame 2 from static
    # Mock returns gray (100,100,100); our static is (80,80,80)
    f0 = context.sequence.frames[0]
    f1 = context.sequence.frames[1]
    f2 = context.sequence.frames[2]
    assert f0.image.get_pixel(0, 0) == (80, 80, 80)
    assert f1.image.get_pixel(0, 0) == (100, 100, 100)
    assert f2.image.get_pixel(0, 0) == (80, 80, 80)


@then("on_first_frame should have been called")
def step_on_first_frame_called(context):
    assert getattr(context, "on_first_frame_called", None) == [True]


@then("on_all_frames should have been called")
def step_on_all_frames_called(context):
    assert getattr(context, "on_all_frames_called", None) == [True]
