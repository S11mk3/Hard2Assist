"""Launch anything -- a Windows app, an installed program, or a website."""

import os

import apps
import ask
from output import detail, say

NAME = "open"
TAKES_ARG = True
ALIASES = ("opun", "oben", "ope")
HELP = "open <app>   -- launch an app, program or website"
EXAMPLE = "open notepad"


def run(argument):
    app = apps.find(argument)

    if app is None:
        app = _ask_where_it_is(argument)
        if app is None:
            return

    # os.startfile goes through the Windows shell, which is what makes this work
    # for everything we throw at it: plain exes, .msc consoles, the ms-settings:
    # URI, Start Menu .lnk shortcuts and https:// addresses alike.
    try:
        os.startfile(app.launch)
    except OSError as e:
        say(f"Could not open {app.name}")
        detail(f"({e})")
        return

    say(f"Opening {app.name}")


def _ask_where_it_is(wanted):
    """Not in the catalogue -- get you to point at it once, then remember it."""
    say(f"I don't know {wanted}. Pick its program file.")

    path = ask.for_program(wanted)
    if not path:
        detail(f"Never mind. Say 'computer help' to see what I do know.")
        return None

    if not os.path.isfile(path):
        say("That file is not there.")
        return None

    app = apps.remember(wanted, path)
    say(f"Got it. I won't ask about {app.name} again.")
    return app
