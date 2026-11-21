"""Bring an app that is already open to the front."""

import session
import settings
import win
from output import detail, say, warn

NAME = "focus"
TAKES_ARG = True
ALIASES = ("focussed", "focused", "folks")
SYNONYMS = ("switch", "show")
HELP = "focus <app> -- bring an open app to the front"
EXAMPLE = "focus notepad"

ABOUT = """\
Focus brings an app that is already open to the front, even if it was
minimised.
"show notepad" and "switch to notepad" mean the same thing.
It picks that app's most recently active window -- the one alt-tab would
reach.
The app has to be open already: if it isn't, I tell you so rather than
opening it behind your back. Say "open" for that.
Windows does not allow a background program to take the foreground in
every situation. When it refuses I say so, and the app's taskbar button
flashes instead.\
"""


def run(argument):
    found = session.target(argument)
    if found is None:
        return
    app = found[0]

    # Front first, so this is the window alt-tab would reach.
    handles = win.windows_of(app)
    if not handles:
        say(f"{app.name} isn't open. Say '{settings.get('prefix')} open {app.name}' to open it.")
        return

    if win.focus_window(handles[0]):
        say(f"Showing {app.name}")
        return

    warn(f"Windows would not bring {app.name} to the front")
    detail("Windows stops a background app taking the focus in some cases; its taskbar button "
           "should be flashing instead.")
