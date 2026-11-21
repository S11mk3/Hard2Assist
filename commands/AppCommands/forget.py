"""Drop something `remember` was told."""

import apps
from output import detail, say, warn

NAME = "forget"
TAKES_ARG = True
ALIASES = ("forgot",)
SYNONYMS = ("unremember",)
HELP = "forget <name> -- drop a program or website you told me to remember"
EXAMPLE = "forget music"

ABOUT = """\
Forget removes something you taught me with "remember" -- a program you
pointed me at, or a website saved from the clipboard.
It only covers those: apps built into Windows or found in your Start Menu
are not mine to forget.
The change is saved, so the name stays gone next time too.\
"""


def run(argument):
    name = argument.lower().strip()
    if apps.forget(name):
        say(f"Forgotten. I no longer know {name}.")
        return

    # Perhaps a loose name for a remembered one: "forget music" for "music player".
    app = apps.find(name)
    if app is None:
        warn(f"I don't know an app called {name}, so there is nothing to forget.")
    elif apps.forget(app.name):
        say(f"Forgotten. I no longer know {app.name}.")
    else:
        warn(f"I can't forget {app.name}.")
        detail(f"Forgetting only covers what you asked me to remember; {app.name} is built in or "
               "comes from your Start Menu.")
