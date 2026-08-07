"""Ask an app to close, politely."""

import apps
import win
from output import say

NAME = "close"
TAKES_ARG = True
HELP = "close <app>  -- close an app, letting it save first ('close all <app>' for every one)"


def run(argument):
    argument = argument.strip()

    # "close all cmd" means every window; plain "close cmd" means the one you
    # most likely just opened.
    every = False
    if argument.lower().startswith("all "):
        every = True
        argument = argument[4:].strip()

    app = apps.find(argument)
    if app is None:
        say(f"I don't know an app called '{argument}'.")
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
            say(f"Could not close a {app.name} window: {e}")

    if closed:
        window = "window" if closed == 1 else "windows"
        say(f"Closing {closed} {app.name} {window}.")

    if denied:
        say(f"Windows won't let me close {app.name} -- it runs as administrator "
            f"and Hard2Assist does not. Restart Hard2Assist as administrator to "
            f"control it.")
