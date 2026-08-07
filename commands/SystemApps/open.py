"""Launch a system app."""

import os

import apps
from output import say

NAME = "open"
TAKES_ARG = True
HELP = "open <app>   -- launch an app"


def run(argument):
    app = apps.find(argument)
    if app is None:
        say(f"I don't know an app called '{argument}'. "
            f"Say 'computer help' for the list.")
        return

    # os.startfile goes through the Windows shell, which is what makes this work
    # for all three kinds of target we have: plain exes, .msc consoles, and the
    # ms-settings: URI. It also finds apps that are not on PATH (Edge, VLC) via
    # the App Paths registry, and unlike a shell command it cannot be tricked by
    # whatever the speech recogniser hands us.
    try:
        os.startfile(app.launch)
    except OSError as e:
        say(f"Could not open {app.name}: {e}")
        return

    say(f"Opening {app.name}...")
