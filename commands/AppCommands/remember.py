"""Teach me a new program or website by voice, saved to my-apps.json and undone with `forget`.

A program is pointed at with the file picker. Nobody can dictate a URL, so a website's address
is read from the clipboard: copy it in the browser, then say the command.
"""

import os

import apps
import ask
import settings
import win
from output import detail, say, warn

NAME = "remember"
TAKES_ARG = True
ALIASES = ("remembers", "remembered")
HELP = "remember <name> -- point me at a program to save ('remember website <name>' saves a copied address)"
EXAMPLE = "remember website music"

ABOUT = """\
Remember teaches me something new to open, without touching any files.
"remember music player" opens the file picker so you can point at the
program once; after that "{prefix} open music player" just works.
"remember website music" saves a website instead: copy the address in
your browser first (Ctrl+L, then Ctrl+C), and I take it from the
clipboard under the name you said.
"forget music" undoes either one.\
"""

# Longest first, so "this website as" is not half-eaten by "website".
_SITE_MARKERS = ("this website as", "this site as", "website as", "site as",
                 "this website", "this site", "website", "site")


def run(argument):
    spoken = argument.strip()
    lowered = spoken.lower()

    for marker in _SITE_MARKERS:
        if lowered == marker:
            say(f"Give the website a name too, like {settings.get('prefix')} remember website music.")
            return
        if lowered.startswith(marker + " "):
            _website(spoken[len(marker):].strip())
            return

    _program(spoken)


def _website(name):
    url = win.clipboard_text().strip()
    prefix = settings.get("prefix")
    if not url.lower().startswith(("http://", "https://")):
        warn("Copy the website's address first, then say it again.")
        detail(f"In the browser: Ctrl+L selects the address, Ctrl+C copies it. "
               f"Then say '{prefix} remember website {name}'.")
        return

    app = apps.remember(name, url)
    say(f"Got it. '{prefix} open {app.name}' now opens that site.")
    detail(f"({url})")


def _program(name):
    existing = apps.find(name)
    if existing is not None and existing.kind in ("system", "folder", "itself"):
        say(f"I already know {existing.name}. Nothing to remember.")
        return

    say(f"Pick the program file for {name}.")
    path = ask.for_program(name)
    if not path:
        detail("Never mind.")
        return
    if not os.path.isfile(path):
        warn("That file is not there.")
        return

    app = apps.remember(name, path)
    say(f"Got it. '{settings.get('prefix')} open {app.name}' now opens it.")
