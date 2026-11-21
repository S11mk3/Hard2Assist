"""Launch anything: a Windows app, an installed program, a folder, or a website."""

import os
import time

import apps
import ask
import listener
import session
import settings
import win
import wizard
from output import detail, say, warn

NAME = "open"
TAKES_ARG = True
ALIASES = ("opun", "oben", "ope")
HELP = "open <app> -- launch an app, program, folder or website"
EXAMPLE = "open notepad"

ABOUT = """\
Open launches anything I can name: an app, a program from your Start Menu
or the Microsoft Store, a folder on this PC, or a website.
I read your Start Menu and Store apps when I start, so most programs work
with no setup at all -- "{prefix} open obs studio" finds OBS Studio by
itself. Folders like documents and downloads work the same way, and so do
sites.
You do not have to say the whole name: "open ccleaner" finds CCleaner 7.
If I don't know a name, I ask whether you want to point me at the program;
say yes and a file picker opens. After that I remember it for good.
"open it" reopens whatever you last named.\
"""

# What the last `open` started, and the windows it already had, for settle().
_opened = None


def run(argument):
    app = session.resolve(argument)
    if app is None:
        if argument.lower().strip() in session.PRONOUNS:
            session.unknown(argument)   # "open it" with nothing named yet: no file to ask for
            return
        app = _ask_where_it_is(argument)
        if app is None:
            return
        session.remember(app)

    if app.kind == "itself":
        # A second copy would mean two microphones fighting over every command.
        handles = win.windows_of(app)
        say("I'm right here." if handles and win.focus_window(handles[0]) else "I'm already running.")
        return

    global _opened
    _opened = (app, set(win.windows_of(app)), win.foreground())

    # Through the Windows shell, so exes, .msc consoles, ms-settings:, shortcuts, folders, Store
    # apps and web addresses all take the same path.
    try:
        os.startfile(app.launch)
    except OSError as e:
        _opened = None
        warn(f"Could not open {app.name}")
        detail(f"({e})")
        return
    say(f"Opening {app.name}")


def settle(timeout=5):
    """Before the next command in a chain ("open notepad and type hello"): wait until the app
    has a new window, or one of its windows has come to the front (a single-window app reuses
    its window). A program starts long before it is on screen."""
    if _opened is None:
        return
    app, before, front = _opened
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        now = set(win.windows_of(app))
        if now - before or (win.foreground() != front and win.foreground() in now):
            time.sleep(session.FOCUS_SETTLE)
            return
        time.sleep(0.2)


def _ask_where_it_is(wanted):
    """An unknown name: offer the file picker, asking first, so a misheard name costs one "no"
    rather than a picker to dismiss. Then remember the answer."""
    ears = listener.current()
    if ears is None:
        say(f"I don't know {wanted}. Pick its program file.")
    elif not wizard.confirm(ears, f"I don't know {wanted}. Do you want to point me at its program?", attempts=1):
        detail(f"Never mind. Say '{settings.get('prefix')} help apps' to see what I can open.")
        return None

    path = ask.for_program(wanted)
    if not path:
        detail("Never mind.")
        return None
    if not os.path.isfile(path):
        warn("That file is not there.")
        return None

    app = apps.remember(wanted, path)
    say(f"Got it. I won't ask about {app.name} again.")
    return app
