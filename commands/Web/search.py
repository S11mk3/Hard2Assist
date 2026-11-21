"""Search the web, or one site, for the spoken words."""

import os
import urllib.parse

from output import detail, say, warn

NAME = "search"
TAKES_ARG = True
VERBATIM = True   # the query keeps every word: "search the meaning of life"
ALIASES = ("surge",)
SYNONYMS = ("google",)
HELP = "search <words> -- search the web ('search youtube for <words>' searches one site)"
EXAMPLE = "search how to cook rice"

ABOUT = """\
Search opens your browser on the results for whatever you say after it.
"{prefix} google how to cook rice" does the same thing, and "search for
cats" drops the "for" rather than searching for it.
Name a site to search it instead: "search youtube for cats", "search
cats on wikipedia". Works for youtube, wikipedia, github, reddit, maps and
amazon.
It opens in whichever browser Windows treats as the default.\
"""

ENGINE = "https://www.google.com/search?q="
SITES = {
    "youtube": "https://www.youtube.com/results?search_query=",
    "wikipedia": "https://en.wikipedia.org/w/index.php?search=",
    "github": "https://github.com/search?q=",
    "reddit": "https://www.reddit.com/search/?q=",
    "google maps": "https://www.google.com/maps/search/",
    "maps": "https://www.google.com/maps/search/",
    "amazon": "https://www.amazon.com/s?k=",
}


def where(words):
    """(results address, query, site or None): "youtube for cats", "cats on wikipedia"."""
    query = words.strip().rstrip(".?!")
    if query.lower().startswith("for "):
        query = query[4:].strip()

    lowered = query.lower()
    for site in sorted(SITES, key=len, reverse=True):   # "google maps" before "maps"
        for lead in (f"{site} for ", f"on {site} for ", f"{site} "):
            if lowered.startswith(lead):
                return SITES[site], query[len(lead):].strip(), site
        for tail in (f" on {site}", f" in {site}"):
            if lowered.endswith(tail):
                return SITES[site], query[:-len(tail)].strip(), site
    return ENGINE, query, None


def run(argument):
    engine, query, site = where(argument)
    if not query:
        say("What should I search for?")
        return

    try:
        os.startfile(engine + urllib.parse.quote_plus(query))
    except OSError as e:
        warn("Could not open the browser")
        detail(f"({e})")
        return
    say(f"Searching {site} for {query}" if site else f"Searching for {query}")
