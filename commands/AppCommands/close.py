"""Ask an app to close, giving it the chance to save first."""

import time

import session
import win
from output import detail, plural, say, warn

NAME = "close"
TAKES_ARG = True
EXACT_ONLY = True
ALIASES = ("clothes", "cloths", "clothe", "closed", "cloze", "klose")
HELP = "close <app> -- close an app, letting it save first ('close all <app>' for every one)"
EXAMPLE = "close notepad"

ABOUT = """\
Close asks an app to close, the same as clicking its X, so it can prompt
you to save first.
Plain "close notepad" closes the notepad opened most recently, so closing
one by voice leaves the one you were already working in alone. Say
"close all notepad" to close every one of them.
"close it" closes whatever you last named. A website closes only its tab,
not the whole browser: "close youtube".
An app running as administrator cannot be closed this way -- Windows
blocks it, and I say so rather than pretending. Start me as
administrator to control those, or use "kill", which usually still works.\
"""


def run(argument):
    found = session.target(argument)
    if found is None:
        return
    app, every = found
    handles = session.windows(app, every)
    if handles is None:
        return

    if app.kind == "web":
        _close_tabs(app, handles)
        return

    closed = denied = 0
    for hwnd in handles:
        try:
            win.close_window(hwnd)
            closed += 1
        except win.AccessDenied:
            denied += 1
        except OSError as e:
            detail(f"Could not close a {app.name} window: {e}")

    if closed:
        say(f"Closing {plural(closed, app.name + ' window')}")
    if denied:
        session.refused(f"close {app.name}")


def _close_tabs(app, handles):
    """A website is a browser tab. Its window is titled after the tab in front, so bringing the
    window forward and pressing Ctrl+W closes exactly that tab, not every tab in the window."""
    closed = 0
    for hwnd in handles:
        if win.focus_window(hwnd):
            time.sleep(session.FOCUS_SETTLE)
            closed += win.send_keys(win.VK_CONTROL, ord("W"))

    if closed:
        say(f"Closed {plural(closed, app.name + ' tab')}")
    if closed < len(handles):
        warn(f"Windows wouldn't let me switch to the {app.name} tab to close it.")
