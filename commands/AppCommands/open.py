"""Launch anything: a Windows app, an installed program, or a website."""

import os

import apps
import ask
import session
import settings
import win
from output import detail, say

NAME = "open"
TAKES_ARG = True
ALIASES = ("opun", "oben", "ope")
HELP = "open <app>   -- launch an app, program or website"
EXAMPLE = "open notepad"

ABOUT = """\
Open launches anything I can name: an app, a program from your Start Menu,
a folder on this PC, or a website.
I read your Start Menu when I start, so most programs work with no setup
at all -- "{prefix} open obs studio" finds OBS Studio by itself. Folders
like documents and downloads work the same way, and so do sites.
You do not have to say the whole name: "open ccleaner" finds CCleaner 7.
If I don't know a name, I open a file picker and ask you to point at the
program once. After that I remember it for good.
"open it" reopens whatever you last named.\
"""


def run(argument):
    app = session.resolve(argument)

    if app is None:
        # "open it" with nothing to point at is a misunderstanding, not an
        # unknown program: there is no file to ask the user to find.
        if argument.lower().strip() in session.PRONOUNS:
            session.unknown(argument)
            return

        app = _ask_where_it_is(argument)
        if app is None:
            return

        session.remember(app)

    # "open yourself" must not start a second copy -- two microphones would
    # fight over every command -- so the running window comes forward instead.
    if app.kind == "itself":
        handles = win.windows_of(app)
        if handles and win.focus_window(handles[0]):
            say("I'm right here.")
        else:
            say("I'm already running.")
        return

    # os.startfile() goes through the Windows shell, so one code path covers
    # everything: plain exes, .msc consoles, ms-settings: URIs, Start Menu
    # .lnk shortcuts and https:// addresses alike.
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
        detail(f"Never mind. Say '{settings.get('prefix')} help' to see "
               "what I do know.")
        return None

    if not os.path.isfile(path):
        say("That file is not there.")
        return None

    app = apps.remember(wanted, path)
    say(f"Got it. I won't ask about {app.name} again.")
    return app
