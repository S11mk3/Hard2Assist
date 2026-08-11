"""Put an app out of the way. The opposite of `focus`."""

import session
import win
from output import detail, say

NAME = "minimize"
TAKES_ARG = True

# "minimise" is the British spelling, and what the recogniser often returns
# however it was said. "hide" is a plain synonym rather than a mishearing.
ALIASES = ("minimise", "minimized", "minimised", "minimizes", "hide")

HELP = "minimize <app> -- send an app to the taskbar (the opposite of focus)"
EXAMPLE = "minimize notepad"

ABOUT = """\
Minimize sends an app down to the taskbar. It is the opposite of focus.
"hide notepad" means the same thing, and "minimize it" minimises whatever
you last named.
Every window that app has goes down, not just the one in front -- leaving
the others on screen would look like the command half worked.
Nothing is closed and nothing is lost; say "focus" to bring it back.\
"""


def run(argument):
    argument = argument.strip()

    # `close` and `kill` take "all <app>", so the phrasing turns up here too.
    # It is what this command does anyway.
    if argument.lower().startswith("all "):
        argument = argument[4:].strip()

    app = session.resolve(argument)
    if app is None:
        session.unknown(argument)
        return

    handles = win.windows_of(app)
    if not handles:
        say(f"{app.name} isn't open.")
        return

    # Every window, not just the front one: leaving the app's others on
    # screen would look like the command had failed.
    minimized = 0
    refused = 0
    for hwnd in handles:
        if win.minimize_window(hwnd):
            minimized += 1
        else:
            refused += 1

    if minimized:
        window = "window" if minimized == 1 else "windows"
        say(f"Minimized {minimized} {app.name} {window}")

    if refused:
        say(f"Windows won't let me minimize {app.name}")
        detail("It runs as administrator and Hard2Assist does not. Restart "
               "Hard2Assist as administrator to control it.")
