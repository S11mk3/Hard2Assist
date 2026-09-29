"""Put an app out of the way. The opposite of `focus`."""

import session
import win

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
    session.each_window(argument, win.minimize_window, "Minimized", "minimize")
