"""Step definitions for apps.feature."""

from behave import when

from pypixoo.native import DisplayItem


@when('I set countdown timer to {minutes} minutes {seconds} seconds with status {status}')
def step_set_countdown(context, minutes, seconds, status):
    context.pixoo.set_countdown_timer((int(minutes), int(seconds), int(status)))


@when("I send display list with one item")
def step_send_display_list(context):
    item = DisplayItem(
        text_id=1,
        item_type=1,
        x=0,
        y=0,
        direction=0,
        font=4,
        text_width=32,
        text_height=16,
        text="HELLO",
        speed=10,
        color="#FFFFFF",
    )
    context.pixoo.send_display_list([item])


@when('I play buzzer with active {active} off {off} total {total}')
def step_play_buzzer(context, active, off, total):
    context.pixoo.play_buzzer(int(active), int(off), int(total))
