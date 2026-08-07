"""How much battery is left."""

import psutil

from output import say

NAME = "battery"
TAKES_ARG = False
ALIASES = ("batery", "batteries", "power level")
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

    # secsleft is a couple of sentinel values when Windows has not worked out an
    # estimate yet, so only mention time when it is a real number.
    if state.secsleft is not None and state.secsleft > 0:
        hours, minutes = divmod(state.secsleft // 60, 60)
        if hours:
            message += f", about {hours} hours {minutes} minutes left"
        else:
            message += f", about {minutes} minutes left"

    say(message + ".")
