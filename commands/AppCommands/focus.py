"""Bring an app that is already open to the front."""

import session
import win
from output import detail, say

NAME = "focus"
TAKES_ARG = True
ALIASES = ("focussed", "focused", "folks", "switch", "show")
HELP = "focus <app>  -- bring an open app to the front"
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
    app = session.resolve(argument)
    if app is None:
        session.unknown(argument)
        return

    handles = win.windows_of(app)
    if not handles:
        say(f"{app.name} isn't open. Say 'computer open {app.name}' "
            f"if you want me to open it.")
        return

    # windows_of() returns handles in Z-order, front first, so the first one
    # is what alt-tab would reach: this app's most recently active window.
    # A minimised window keeps its WS_VISIBLE style, so it is still in there.
    if win.focus_window(handles[0]):
        say(f"Showing {app.name}")
        return

    say(f"Windows would not bring {app.name} to the front")
    detail("Windows blocks a background app from stealing focus in some "
           "cases; its taskbar button should be flashing instead.")
