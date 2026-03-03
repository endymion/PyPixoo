"""Step definitions for system.feature."""

from behave import then, when


def _last_command(context):
    if not context._command_history:
        raise AssertionError("No commands recorded")
    return context._command_history[-1]


@when('I set brightness to {value}')
def step_set_brightness(context, value):
    context.pixoo.set_brightness(int(value))


@when('I set channel index to {value}')
def step_set_channel_index(context, value):
    context.pixoo.set_channel_index(int(value))


@when('I send raw command "{command}" with "{key}" {value}')
def step_send_raw_command(context, command, key, value):
    context.pixoo.command(command, {key: int(value)})


@then('the last command should be "{command}"')
def step_last_command(context, command):
    last = _last_command(context)
    actual = last.get("Command")
    assert actual == command, f"Expected last command {command}, got {actual}"


@then('the last command payload should include "{key}" {value}')
def step_last_command_payload(context, key, value):
    last = _last_command(context)
    actual = last.get(key)
    assert actual == int(value), f"Expected {key} {value}, got {actual}"
