"""List everything Hard2Assist can do.

The output is generated from the loaded commands and the app catalogue,
so it cannot drift out of step with what is actually available.
"""

import apps
import registry
from output import detail, say

NAME = "help"
TAKES_ARG = False
HELP = "help         -- show this list"

COLUMNS = 3
WIDTH = 24


def run():
    commands = registry.load()

    # Speak only a short summary; the full lists would be tedious to hear.
    say(f"I know {len(commands)} commands and {len(apps.names())} apps. "
        f"They're on screen.")

    detail("")
    detail("Commands (say 'computer' first):")
    for name in sorted(commands):
        detail("  " + getattr(commands[name], "HELP", name))

    detail("")
    detail("Apps you can open, close and kill:")
    names = apps.names()
    for i in range(0, len(names), COLUMNS):
        row = names[i:i + COLUMNS]
        detail("  " + "".join(name.ljust(WIDTH) for name in row).rstrip())

    detail("")
