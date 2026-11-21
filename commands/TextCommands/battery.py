"""Report how much battery is left."""

import psutil

from output import plural, say

NAME = "battery"
TAKES_ARG = False
ALIASES = ("batery", "batteries")
PHRASES = ("how much charge",)
HELP = "battery -- how much charge is left"

ABOUT = """\
Battery says how much charge is left, and whether it is charging.
"how much battery is left" and "how much charge" both reach it.
When Windows can estimate the time remaining I say that as well, but it
refuses to guess for the first minute or two after unplugging, so I leave
it out rather than reading back a made-up number.
On a desktop with no battery, I say so.\
"""


def run():
    state = psutil.sensors_battery()
    if state is None:
        say("This PC has no battery.")
        return

    percent = round(state.percent)
    if state.power_plugged:
        say("Fully charged and plugged in." if percent >= 99 else f"{percent} percent, charging.")
        return

    message = f"{percent} percent"
    if state.secsleft is not None and state.secsleft > 0:   # negative while Windows estimates
        hours, minutes = divmod(state.secsleft // 60, 60)
        left = " ".join(plural(n, unit) for n, unit in ((hours, "hour"), (minutes, "minute")) if n)
        if left:
            message += f", about {left} left"
    say(message + ".")
