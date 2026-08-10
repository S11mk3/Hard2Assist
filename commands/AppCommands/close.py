"""Ask an app to close, giving it the chance to save first."""

import session
import win
from output import detail, say

NAME = "close"
TAKES_ARG = True

# "clothes" is what Google's recogniser returns for "close" more often
# than not; the rest are its other frequent guesses.
ALIASES = ("clothes", "cloths", "clothe", "closed", "cloze", "klose")

HELP = "close <app>  -- close an app, letting it save first ('close all <app>' for every one)"
EXAMPLE = "close notepad"


def run(argument):
    argument = argument.strip()

    # "close all cmd" closes every window; plain "close cmd" closes only the
    # most recently opened one.
    every = False
    if argument.lower().startswith("all "):
        every = True
        argument = argument[4:].strip()

    app = session.resolve(argument)
    if app is None:
        session.unknown(argument)
        return

    if every:
        handles = win.windows_of(app)
    else:
        newest = win.newest_window_of(app)
        handles = [newest] if newest else []

    if not handles:
        say(f"{app.name} does not seem to be open.")
        return

    closed = 0
    denied = 0
    for hwnd in handles:
        try:
            win.close_window(hwnd)
            closed += 1
        except win.AccessDenied:
            denied += 1
        except OSError as e:
            detail(f"Could not close a {app.name} window: {e}")

    if closed:
        window = "window" if closed == 1 else "windows"
        say(f"Closing {closed} {app.name} {window}")

    if denied:
        say(f"Windows won't let me close {app.name}")
        detail("It runs as administrator and Hard2Assist does not. Restart "
               "Hard2Assist as administrator to control it.")
