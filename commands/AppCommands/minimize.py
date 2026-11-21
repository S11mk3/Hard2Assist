"""Put an app out of the way, or everything at once. The opposite of `focus`."""

import session
import win
from output import say, warn

NAME = "minimize"
TAKES_ARG = True
ALIASES = ("minimized", "minimised", "minimizes")
SYNONYMS = ("minimise", "hide")
PHRASES = {"show desktop": "everything", "show the desktop": "everything"}
HELP = "minimize <app> -- send an app to the taskbar ('minimize everything' clears the screen)"
EXAMPLE = "minimize notepad"

ABOUT = """\
Minimize sends an app down to the taskbar. It is the opposite of focus.
"hide notepad" means the same thing, and "minimize it" minimises whatever
you last named.
Every window that app has goes down, not just the one in front -- leaving
the others on screen would look like the command half worked.
"minimize everything" or "show desktop" clears the whole screen.
Nothing is closed and nothing is lost; say "focus" to bring it back.\
"""

EVERYTHING = ("all", "everything", "all windows", "every window", "everything else")


def run(argument):
    if argument.lower().strip() in EVERYTHING:
        if win.send_keys(win.VK_LWIN, ord("M")):   # Windows' own "minimize all"
            say("Minimized everything")
        else:
            warn("Windows wouldn't let me minimize everything.")
        return
    session.each_window(argument, win.minimize_window, "Minimized", "minimize")
