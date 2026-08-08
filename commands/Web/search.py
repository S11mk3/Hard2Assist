"""Search the web for the spoken words."""

import os
import urllib.parse

from output import detail, say

NAME = "search"
TAKES_ARG = True
ALIASES = ("google", "search for", "look up", "surge")
HELP = "search <words> -- search the web"
EXAMPLE = "search how to cook rice"

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
