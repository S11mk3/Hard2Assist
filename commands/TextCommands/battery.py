"""Report how much battery is left."""

import psutil

from output import say

NAME = "battery"
TAKES_ARG = False
ALIASES = ("batery", "batteries")
HELP = "battery      -- how much charge is left"


def run():
    state = psutil.sensors_battery()

    if state is None:
        say("This PC has no battery.")
        return

    percent = round(state.percent)

    if state.power_plugged:
        if percent >= 99:
            say("Fully charged and plugged in.")
        else:
            say(f"{percent} percent, charging.")
        return

    message = f"{percent} percent"

    # secsleft holds sentinel values while Windows is still estimating, so
    # only mention remaining time when it is a real positive number.
    if state.secsleft is not None and state.secsleft > 0:
        hours, minutes = divmod(state.secsleft // 60, 60)
        if hours:
            message += f", about {hours} hours {minutes} minutes left"
        else:
            message += f", about {minutes} minutes left"

    say(message + ".")
