"""Search the web for the spoken words."""

import os
import urllib.parse

from output import detail, say

NAME = "search"
TAKES_ARG = True
ALIASES = ("google", "surge")
HELP = "search <words> -- search the web"
EXAMPLE = "search how to cook rice"

ABOUT = """\
Search opens your browser on the results for whatever you say after it.
"{prefix} google how to cook rice" does the same thing, and "search for
cats" drops the "for" rather than searching for it.
It opens in whichever browser Windows treats as the default.\
"""

ENGINE = "https://www.google.com/search?q="


def run(argument):
    words = argument.strip()

    # "search for cats" and "google for cats" both land here; drop the
    # leading "for" so it does not become part of the query.
    if words.lower().startswith("for "):
        words = words[4:].strip()

    if not words:
        say("What should I search for?")
        return

    url = ENGINE + urllib.parse.quote_plus(words)

    try:
        os.startfile(url)
    except OSError as e:
        say("Could not open the browser")
        detail(f"({e})")
        return

    say(f"Searching for {words}")
