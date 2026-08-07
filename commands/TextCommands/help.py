"""List what Hard2Assist can do. Everything here is generated, so it cannot
drift out of step with the actual commands and apps."""

import apps
import registry
from output import say

NAME = "help"
TAKES_ARG = False
HELP = "help         -- show this list"

COLUMNS = 3
WIDTH = 24


def run():
    commands = registry.load()

    say("")
    say("Commands (say 'computer' first):")
    for name in sorted(commands):
        say("  " + getattr(commands[name], "HELP", name))

    say("")
    say("Apps you can open, close and kill:")
    names = apps.names()
    for i in range(0, len(names), COLUMNS):
        row = names[i:i + COLUMNS]
        say("  " + "".join(name.ljust(WIDTH) for name in row).rstrip())

    say("")
