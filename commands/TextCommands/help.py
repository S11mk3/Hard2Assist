"""List what Hard2Assist can do. Everything here is generated, so it cannot
drift out of step with the actual commands and apps."""

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

    # Short spoken summary; the lists themselves would be tedious to listen to.
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
