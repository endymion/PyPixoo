"""Step definitions for animation.feature."""

import time

from behave import given, then, when

from pypixoo.buffer import Buffer
from pypixoo.native import CycleItem, GifFrame, GifSequence, GifSource, TextOverlay, UploadMode


def _solid_buffer(r: int, g: int, b: int) -> Buffer:
    data = [c for _ in range(64 * 64) for c in (r, g, b)]
    return Buffer.from_flat_list(data)


def _commands(context, command: str):
    return [c for c in context._command_history if c.get("Command") == command]


@given('a native GIF sequence with {n} frames and speed {speed}ms')
def step_native_sequence(context, n, speed):
    count = int(n)
    speed_ms = int(speed)
    frames = []
    for i in range(count):
        color = (i * 13) % 255
        frames.append(
            GifFrame(
                image=_solid_buffer(color, 0, 255 - color),
                duration_ms=speed_ms,
            )
        )
    context.native_sequence = GifSequence(frames=frames, speed_ms=speed_ms)


@given('I upload the native sequence in mode "{mode}"')
@when('I upload the native sequence in mode "{mode}"')
def step_upload_sequence_mode(context, mode):
    context.uploaded_pic_id = context.pixoo.upload_sequence(
        context.native_sequence,
        mode=UploadMode(mode),
    )


@when('I upload the native sequence in mode "{mode}" with chunk size {chunk_size}')
def step_upload_sequence_chunked(context, mode, chunk_size):
    context.uploaded_pic_id = context.pixoo.upload_sequence(
        context.native_sequence,
        mode=UploadMode(mode),
        chunk_size=int(chunk_size),
    )


@then('{n} Draw/SendHttpGif commands should be sent')
def step_send_httpgif_count(context, n):
    actual = len(_commands(context, "Draw/SendHttpGif"))
    assert actual == int(n), f"Expected {n} Draw/SendHttpGif commands, got {actual}"


@then('all uploaded frames should use the same PicID')
def step_all_uploaded_same_pic_id(context):
    cmds = _commands(context, "Draw/SendHttpGif")
    pic_ids = {c.get("PicID") for c in cmds}
    assert len(pic_ids) == 1, f"Expected one PicID, got {pic_ids}"


@then('uploaded frame offsets should be 0,1')
def step_offsets_two(context):
    cmds = _commands(context, "Draw/SendHttpGif")
    offsets = [c.get("PicOffset") for c in cmds]
    assert offsets == [0, 1], f"Expected offsets [0, 1], got {offsets}"


@then('all uploaded frames should have PicNum {pic_num}')
def step_pic_num(context, pic_num):
    expected = int(pic_num)
    cmds = _commands(context, "Draw/SendHttpGif")
    assert cmds, "No Draw/SendHttpGif commands recorded"
    for cmd in cmds:
        assert cmd.get("PicNum") == expected, f"Expected PicNum {expected}, got {cmd.get('PicNum')}"


@then('all uploaded frames should have PicSpeed {speed}')
def step_pic_speed(context, speed):
    expected = int(speed)
    cmds = _commands(context, "Draw/SendHttpGif")
    assert cmds, "No Draw/SendHttpGif commands recorded"
    for cmd in cmds:
        assert cmd.get("PicSpeed") == expected, f"Expected PicSpeed {expected}, got {cmd.get('PicSpeed')}"


@then('{n} Draw/CommandList commands should be sent')
def step_command_list_count(context, n):
    actual = len(_commands(context, "Draw/CommandList"))
    assert actual == int(n), f"Expected {n} Draw/CommandList commands, got {actual}"


@then('command list chunk sizes should be {a},{b},{c}')
def step_chunk_sizes(context, a, b, c):
    cmd_lists = _commands(context, "Draw/CommandList")
    sizes = [len(x.get("CommandList", [])) for x in cmd_lists]
    expected = [int(a), int(b), int(c)]
    assert sizes == expected, f"Expected chunk sizes {expected}, got {sizes}"


@then('nested uploaded frame offsets should span {start} through {end}')
def step_nested_offsets(context, start, end):
    cmd_lists = _commands(context, "Draw/CommandList")
    offsets = []
    for cmd in cmd_lists:
        for nested in cmd.get("CommandList", []):
            offsets.append(nested.get("PicOffset"))
    expected = list(range(int(start), int(end) + 1))
    assert offsets == expected, f"Expected offsets {expected[:5]}...{expected[-5:]}, got {offsets[:5]}...{offsets[-5:]}"


@then('all nested uploaded frames should use the same PicID')
def step_nested_same_pic_id(context):
    cmd_lists = _commands(context, "Draw/CommandList")
    pic_ids = set()
    for cmd in cmd_lists:
        for nested in cmd.get("CommandList", []):
            pic_ids.add(nested.get("PicID"))
    assert len(pic_ids) == 1, f"Expected one nested PicID, got {pic_ids}"


@when('I query the HTTP GIF ID')
def step_query_http_gif_id(context):
    context.returned_http_gif_id = context.pixoo.get_http_gif_id()


@then('the returned HTTP GIF ID should be {value}')
def step_returned_http_gif_id(context, value):
    assert context.returned_http_gif_id == int(value), (
        f"Expected HTTP GIF ID {value}, got {context.returned_http_gif_id}"
    )


@when('I reset the HTTP GIF ID')
def step_reset_http_gif_id(context):
    context.pixoo.reset_http_gif_id()


@then('a Draw/ResetHttpGifId command should be sent')
def step_reset_command_sent(context):
    cmds = _commands(context, "Draw/ResetHttpGifId")
    assert len(cmds) == 1, f"Expected one Draw/ResetHttpGifId command, got {len(cmds)}"


@when('I play GIF source type "{source_type}" with value "{value}"')
@given('I play GIF source type "{source_type}" with value "{value}"')
def step_play_gif_source(context, source_type, value):
    source_factory = {
        "url": GifSource.url,
        "tf_file": GifSource.tf_file,
        "tf_directory": GifSource.tf_directory,
    }
    context.pixoo.play_gif(source_factory[source_type](value))


@then('the last Device/PlayTFGif command should use FileType {file_type}')
def step_last_play_file_type(context, file_type):
    cmds = _commands(context, "Device/PlayTFGif")
    assert cmds, "No Device/PlayTFGif commands were recorded"
    actual = cmds[-1].get("FileType")
    assert actual == int(file_type), f"Expected FileType {file_type}, got {actual}"


@when('I send text overlay "{text}"')
def step_send_text_overlay(context, text):
    context.native_error = None
    try:
        context.pixoo.send_text_overlay(
            TextOverlay(
                text=text,
                text_id=7,
                x=1,
                y=2,
                direction=0,
                font=4,
                text_width=56,
                speed=10,
                color="#FFFF00",
                align=1,
            )
        )
    except Exception as e:
        context.native_error = e


@then('a Draw/SendHttpText command should be sent')
def step_send_text_cmd(context):
    cmds = _commands(context, "Draw/SendHttpText")
    assert len(cmds) == 1, f"Expected one Draw/SendHttpText command, got {len(cmds)}"


@when('I clear the text overlay')
def step_clear_text_overlay(context):
    context.pixoo.clear_text_overlay()


@then('a Draw/ClearHttpText command should be sent')
def step_clear_text_cmd(context):
    cmds = _commands(context, "Draw/ClearHttpText")
    assert len(cmds) == 1, f"Expected one Draw/ClearHttpText command, got {len(cmds)}"


@then('a native ValueError should occur')
def step_native_value_error(context):
    assert context.native_error is not None, "Expected ValueError but no exception occurred"
    assert isinstance(context.native_error, ValueError), (
        f"Expected ValueError, got {type(context.native_error).__name__}: {context.native_error}"
    )


@given('cycle items of sequence, url gif, and tf file gif')
def step_cycle_items_three(context):
    seq = GifSequence(
        frames=[GifFrame(image=_solid_buffer(10, 20, 30), duration_ms=40)],
        speed_ms=40,
    )
    context.cycle_items = [
        CycleItem(sequence=seq, upload_mode=UploadMode.FRAME_BY_FRAME),
        CycleItem(source=GifSource.url("https://example.com/cycle.gif")),
        CycleItem(source=GifSource.tf_file("divoom_gif/2.gif")),
    ]


@given('cycle items containing one url gif')
def step_cycle_items_one(context):
    context.cycle_items = [CycleItem(source=GifSource.url("https://example.com/infinite.gif"))]


@given('cycle callbacks are registered')
def step_cycle_callbacks(context):
    context.cycle_on_item = []
    context.cycle_on_loop = []


@when('I start cycle with loop count {n}')
def step_start_cycle_n(context, n):
    context.cycle_handle = context.pixoo.start_cycle(
        context.cycle_items,
        loop=int(n),
        on_item=lambda idx, item: context.cycle_on_item.append(idx),
        on_loop=lambda count: context.cycle_on_loop.append(count),
    )


@when('I wait for cycle completion')
def step_wait_cycle(context):
    assert context.cycle_handle.wait(2.0), "Cycle did not complete in time"


@then('cycle on_item callback order should be 0,1,2')
def step_cycle_item_order(context):
    assert context.cycle_on_item == [0, 1, 2], (
        f"Expected on_item order [0, 1, 2], got {context.cycle_on_item}"
    )


@then('cycle on_loop callback counts should be 1')
def step_cycle_loop_counts(context):
    assert context.cycle_on_loop == [1], f"Expected on_loop [1], got {context.cycle_on_loop}"


@when('I start cycle with infinite loop')
def step_start_cycle_infinite(context):
    context.cycle_handle = context.pixoo.start_cycle(context.cycle_items, loop=None)


@when('I wait briefly')
def step_wait_briefly(context):
    time.sleep(0.1)


@when('I stop the running cycle')
def step_stop_cycle(context):
    context.cycle_handle.stop()
    context.cycle_handle.wait(2.0)


@then('the cycle should not be running')
def step_cycle_not_running(context):
    assert context.cycle_handle.is_running is False, "Expected cycle to be stopped"
