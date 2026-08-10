"""Fill the screen with an app. The opposite of `shrink`."""

import apps
import win
from output import detail, say

NAME = "fullscreen"
TAKES_ARG = True

# "maximize" is what Windows itself calls this, and the word half the people
# who want it will reach for; the rest are the recogniser's frequent guesses
# and plain synonyms.
ALIASES = ("maximize", "maximise", "maximized", "maximised", "maximizes",
           "expand", "enlarge", "bigger")

# The recogniser returns "full screen" as two words far more often than one,
# and an alias could never catch it: aliases are matched a word at a time, so
# a multi-word one is unreachable. A phrase is the only way to reach it.
PHRASES = ("full screen",)

HELP = "fullscreen <app> -- fill the screen with an app ('shrink' puts it back)"
EXAMPLE = "fullscreen notepad"


def run(argument):
    argument = argument.strip()

    # `close` and `kill` take "all <app>", so the phrasing gets used here too.
    # It is what this command does anyway, and erroring on it would be a
    # pointless correction.
    if argument.lower().startswith("all "):
        argument = argument[4:].strip()

    app = apps.find(argument)
    if app is None:
        say(f"I don't know an app called {argument}.")
        return

    handles = win.windows_of(app)
    if not handles:
        say(f"{app.name} isn't open.")
        return

    # Every window, exactly as `minimize` does. Maximising is not destructive,
    # so there is no reason to be cautious the way `close` is -- and leaving
    # the app's other windows small would look like the command half worked.
    maximized = 0
    refused = 0
    for hwnd in handles:
        if win.maximize_window(hwnd):
            maximized += 1
        else:
            refused += 1

    if maximized:
        window = "window" if maximized == 1 else "windows"
        say(f"Maximized {maximized} {app.name} {window}")

    if refused:
        say(f"Windows won't let me maximize {app.name}")
        detail("It runs as administrator and Hard2Assist does not. Restart "
               "Hard2Assist as administrator to control it.")
