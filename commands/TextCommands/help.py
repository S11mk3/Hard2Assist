"""List what Hard2Assist can do. Everything here is generated, so it cannot
drift out of step with the actual commands and apps."""

import apps
import registry

NAME = "help"
TAKES_ARG = False
HELP = "help         -- show this list"

COLUMNS = 3
WIDTH = 24


def run():
    commands = registry.load()

    print("\nCommands (say 'computer' first):\n")
    for name in sorted(commands):
        print("  " + getattr(commands[name], "HELP", name))

    print("\nApps you can open, close and kill:\n")
    names = apps.names()
    for i in range(0, len(names), COLUMNS):
        row = names[i:i + COLUMNS]
        print("  " + "".join(name.ljust(WIDTH) for name in row).rstrip())

    print()
