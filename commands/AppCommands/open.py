"""Launch anything: a Windows app, an installed program, or a website."""

import os

import apps
import ask
import session
from output import detail, say

NAME = "open"
TAKES_ARG = True
ALIASES = ("opun", "oben", "ope")
HELP = "open <app>   -- launch an app, program or website"
EXAMPLE = "open notepad"


def run(argument):
    app = session.resolve(argument)

    if app is None:
        # "open it" with nothing to point at is a misunderstanding, not an
        # unknown program. Opening a file picker and asking the user to find
        # "it" on their disk would be absurd.
        if argument.lower().strip() in session.PRONOUNS:
            session.unknown(argument)
            return

        app = _ask_where_it_is(argument)
        if app is None:
            return

        session.remember(app)

    # os.startfile() goes through the Windows shell, which is what makes one
    # code path work for everything: plain exes, .msc consoles, ms-settings:
    # URIs, Start Menu .lnk shortcuts and https:// addresses alike.
    try:
        os.startfile(app.launch)
    except OSError as e:
        say(f"Could not open {app.name}")
        detail(f"({e})")
        return

    say(f"Opening {app.name}")


def _ask_where_it_is(wanted):
    """Unknown program: have the user point at it once, then remember it."""
    say(f"I don't know {wanted}. Pick its program file.")

    path = ask.for_program(wanted)
    if not path:
        detail("Never mind. Say 'computer help' to see what I do know.")
        return None

    if not os.path.isfile(path):
        say("That file is not there.")
        return None

    app = apps.remember(wanted, path)
    say(f"Got it. I won't ask about {app.name} again.")
    return app
