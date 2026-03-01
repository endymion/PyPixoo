"""Step definitions for display.feature."""

from behave import given, when, then

from pypixoo import Pixoo


@given('a Pixoo at IP "{ip}"')
def step_pixoo_at_ip(context, ip):
    context.pixoo = Pixoo(ip)


@given('I connect')
@when('I connect')
def step_connect(context):
    context.connect_error = None
    try:
        context.connected = context.pixoo.connect()
    except Exception as e:
        context.connect_error = e
        context.connected = False


@given('I fill with RGB {r} {g} {b}')
@when('I fill with RGB {r} {g} {b}')
def step_fill(context, r, g, b):
    context.fill_error = None
    try:
        context.pixoo.fill(int(r), int(g), int(b))
    except Exception as e:
        context.fill_error = e


@when('I load image "{path}"')
def step_load_image(context, path):
    context.load_error = None
    try:
        context.pixoo.load_image(path)
    except Exception as e:
        context.load_error = e


@when('I push')
def step_push(context):
    context.push_error = None
    try:
        context.pixoo.push()
    except Exception as e:
        context.push_error = e


@then('no error should occur')
def step_no_error(context):
    assert context.connect_error is None, f"Connect failed: {context.connect_error}"
    assert context.connected, "Connection was not successful"
    assert getattr(context, "fill_error", None) is None, f"Fill failed: {context.fill_error}"
    assert getattr(context, "load_error", None) is None, f"Load failed: {context.load_error}"
    assert context.push_error is None, f"Push failed: {context.push_error}"


@then('no load error should occur')
def step_no_load_error(context):
    assert getattr(context, "load_error", None) is None, f"Load failed: {context.load_error}"


@then('the buffer should be {width} by {height}')
def step_buffer_dimensions(context, width, height):
    buf = context.pixoo.buffer
    assert buf.width == int(width), f"Expected width {width}, got {buf.width}"
    assert buf.height == int(height), f"Expected height {height}, got {buf.height}"


@then('the buffer at {x} {y} should be RGB {r} {g} {b}')
def step_buffer_pixel(context, x, y, r, g, b):
    buf = context.pixoo.buffer
    actual = buf.get_pixel(int(x), int(y))
    expected = (int(r), int(g), int(b))
    assert actual == expected, f"At ({x},{y}) expected RGB {expected}, got {actual}"


@when('I get the buffer pixel at {x} {y}')
def step_get_buffer_pixel(context, x, y):
    context.pixel_error = None
    try:
        buf = context.pixoo.buffer
        buf.get_pixel(int(x), int(y))
    except Exception as e:
        context.pixel_error = e


@then('an IndexError should occur')
def step_index_error(context):
    assert context.pixel_error is not None, "Expected IndexError but no exception occurred"
    assert isinstance(context.pixel_error, IndexError), (
        f"Expected IndexError, got {type(context.pixel_error).__name__}: {context.pixel_error}"
    )


@then('connection should be unsuccessful')
def step_connection_unsuccessful(context):
    assert context.connected is False, "Expected connection to fail"


@then('a RuntimeError should occur on connect')
def step_runtime_error_connect(context):
    assert context.connect_error is not None, "Expected RuntimeError on connect"
    assert isinstance(context.connect_error, RuntimeError), (
        f"Expected RuntimeError, got {type(context.connect_error).__name__}: {context.connect_error}"
    )


@then('a RuntimeError should occur on push')
def step_runtime_error_push(context):
    assert context.push_error is not None, "Expected RuntimeError on push"
    assert isinstance(context.push_error, RuntimeError), (
        f"Expected RuntimeError, got {type(context.push_error).__name__}: {context.push_error}"
    )
