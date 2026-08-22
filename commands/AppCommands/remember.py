"""Teach the catalogue a new program or website by voice.

Programs go through the same file picker `open` uses for unknown names.
Websites cannot be dictated -- nobody spells a URL out loud -- so the address
is read from the clipboard: copy it in the browser, then say the command.
Both are saved to my-apps.json and undone with `forget`.
"""

import os

import apps
import ask
import settings
import win
from output import detail, say

NAME = "remember"
TAKES_ARG = True
ALIASES = ("remembers", "remembered")
HELP = ("remember <name> -- point me at a program to save "
        "('remember website <name>' saves a copied address)")
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

# Ways the website form can start. Longest first, so "this website as" is
# not half-eaten by "website".
_SITE_MARKERS = ("this website as", "this site as", "website as", "site as",
                 "this website", "this site", "website", "site")


def run(argument):
    spoken = argument.strip()
    lowered = spoken.lower()

    for marker in _SITE_MARKERS:
        if lowered == marker:
            say("Give the website a name too, like "
                f"{settings.get('prefix')} remember website music.")
            return
        if lowered.startswith(marker + " "):
            _website(spoken[len(marker):].strip())
            return

    _program(spoken)


def _website(name):
    url = win.clipboard_text().strip()

    if not url.lower().startswith(("http://", "https://")):
        say("Copy the website's address first, then say it again.")
        detail("In the browser: Ctrl+L selects the address, Ctrl+C copies "
               f"it. Then say '{settings.get('prefix')} remember website "
               f"{name}'.")
        return

    app = apps.remember(name, url)
    say(f"Got it. '{settings.get('prefix')} open {app.name}' now opens "
        "that site.")
    detail(f"({url})")


def _program(name):
    existing = apps.find(name)
    if existing is not None and existing.kind in ("system", "folder",
                                                  "itself"):
        say(f"I already know {existing.name}. Nothing to remember.")
        return

    say(f"Pick the program file for {name}.")

    path = ask.for_program(name)
    if not path:
        detail("Never mind.")
        return

    if not os.path.isfile(path):
        say("That file is not there.")
        return

    app = apps.remember(name, path)
    say(f"Got it. '{settings.get('prefix')} open {app.name}' now opens it.")
