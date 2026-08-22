"""Drop something `remember` was told, by voice."""

import apps
from output import detail, say

NAME = "forget"
TAKES_ARG = True
ALIASES = ("forgot", "unremember")
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

    # The spoken name may be a loose match for the remembered one --
    # "forget music" for an entry saved as "music player".
    app = apps.find(name)

    if app is not None and apps.forget(app.name):
        say(f"Forgotten. I no longer know {app.name}.")
        return

    if app is not None:
        say(f"I can't forget {app.name}.")
        detail("Forgetting only covers what you asked me to remember; "
               f"{app.name} is built in or comes from your Start Menu.")
        return

    say(f"I don't know an app called {name}, so there is nothing to forget.")
