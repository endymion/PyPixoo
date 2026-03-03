"""Step definitions for text.feature."""

from behave import then, when

from pypixoo.fonts import BuiltinFont
from pypixoo.native import TextOverlay


def _commands(context, command: str):
    return [c for c in context._command_history if c.get("Command") == command]


@when('I send text overlay "{text}" using built-in font "{font_name}"')
def step_send_text_overlay_font(context, text, font_name):
    font = BuiltinFont.from_name(font_name)
    context.pixoo.send_text_overlay(
        TextOverlay(
            text=text,
            text_id=1,
            x=1,
            y=2,
            direction=0,
            font=font,
            text_width=56,
            speed=10,
            color="#FFFF00",
            align=1,
        )
    )


@then('the text overlay font id should be {font_id}')
def step_text_overlay_font_id(context, font_id):
    cmds = _commands(context, "Draw/SendHttpText")
    assert cmds, "No Draw/SendHttpText commands recorded"
    actual = cmds[-1].get("font")
    assert actual == int(font_id), f"Expected font id {font_id}, got {actual}"


@when("I list built-in fonts")
def step_list_fonts(context):
    context.font_registry = context.pixoo.list_fonts()


@then('the font list should include "{font_name}"')
def step_font_list_contains(context, font_name):
    fonts = context.font_registry.fonts
    assert any((f.name or "").lower() == font_name.lower() for f in fonts), (
        f"Expected font list to include {font_name}, got {[f.name for f in fonts]}"
    )


@when("I upload the native sequence with 2 overlays")
def step_upload_sequence_with_overlays(context):
    overlays = [
        TextOverlay(text="one", text_id=1, x=0, y=0, font=4, text_width=56, speed=10),
        TextOverlay(text="two", text_id=2, x=0, y=10, font=4, text_width=56, speed=10),
    ]
    context.pixoo.upload_sequence_with_overlays(context.native_sequence, overlays)


@then("the overlays should be sent after the upload")
def step_overlays_after_upload(context):
    order = [c.get("Command") for c in context._command_history]
    if "Draw/SendHttpText" not in order:
        raise AssertionError("No Draw/SendHttpText commands recorded")
    upload_indices = [
        i for i, cmd in enumerate(order) if cmd in ("Draw/SendHttpGif", "Draw/CommandList")
    ]
    if not upload_indices:
        raise AssertionError("No upload commands recorded before overlays")
    last_upload_idx = max(upload_indices)
    first_overlay_idx = min(i for i, cmd in enumerate(order) if cmd == "Draw/SendHttpText")
    assert first_overlay_idx > last_upload_idx, (
        f"Expected overlays after upload, got upload index {last_upload_idx}, overlay index {first_overlay_idx}"
    )


@then('{n} Draw/SendHttpText commands should be sent')
def step_send_http_text_count(context, n):
    actual = len(_commands(context, "Draw/SendHttpText"))
    assert actual == int(n), f"Expected {n} Draw/SendHttpText commands, got {actual}"
