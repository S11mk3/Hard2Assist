"""Ask an app to close, politely."""

import apps
import win

NAME = "close"
TAKES_ARG = True
HELP = "close <app>  -- close an app, letting it save first"


def run(argument):
    app = apps.find(argument)
    if app is None:
        print(f"I don't know an app called '{argument}'.")
        return

    handles = win.windows_of(app)
    if not handles:
        print(f"{app.name} does not seem to be open.")
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
            print(f"Could not close a {app.name} window: {e}")

    if closed:
        window = "window" if closed == 1 else "windows"
        print(f"Closing {closed} {app.name} {window}.")

    if denied:
        print(f"Windows won't let me close {app.name} -- it runs as "
              f"administrator and Hard2Assist does not. Restart Hard2Assist as "
              f"administrator to control it.")
