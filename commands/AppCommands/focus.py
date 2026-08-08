"""Bring an app that is already open to the front."""

import apps
import win
from output import detail, say

NAME = "focus"
TAKES_ARG = True
ALIASES = ("focussed", "focused", "folks", "switch", "show")
HELP = "focus <app>  -- bring an open app to the front"
EXAMPLE = "focus notepad"


def run(argument):
    app = apps.find(argument)
    if app is None:
        say(f"I don't know an app called {argument}.")
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
