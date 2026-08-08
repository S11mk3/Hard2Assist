"""The catalogue of everything Hard2Assist can open.

Four sources, searched in this order:

    system     apps built into Windows        apps/system.py
    mine       ones you pointed at yourself   %APPDATA%\\Hard2Assist\\my-apps.json
    installed  found in your Start Menu       apps/installed.py
    web        websites                       apps/websites.py

`open`, `close` and `kill` do not care which is which -- they all go through
find(). Your own picks come before the Start Menu scan so that correcting a bad
match actually sticks.
"""

import difflib

from .app import App
from . import installed, system, websites

_catalogue = None


def all_apps():
    """Every app, in search order. Scanned once and kept."""
    global _catalogue
    if _catalogue is None:
        _catalogue = (
            list(system.APPS)
            + installed.mine()
            + installed.scan()
            + list(websites.SITES)
        )
    return _catalogue


def refresh():
    """Forget the scan. Used after remembering a new app."""
    global _catalogue
    _catalogue = None


def find(spoken):
    """Return the App the user asked for, or None.

    Forgiving on purpose. Start Menu shortcuts carry version numbers and
    marketing ("CCleaner 7", "Visual Studio Code"), and nobody says those out
    loud, so an exact match alone would miss most of what is installed.

    Whatever matches, the app's real name is what gets said back, so you always
    hear which one it picked.
    """
    if not spoken:
        return None

    spoken = spoken.lower().strip()
    catalogue = all_apps()

    for app in catalogue:
        if app.matches(spoken):
            return app

    # "ccleaner" should find "ccleaner 7". Shortest wins, as the closest fit.
    starts = [a for a in catalogue if a.name.startswith(spoken)]
    if starts:
        return min(starts, key=lambda a: len(a.name))

    # "obs" inside "obs studio", but only for words long enough that this is not
    # a coincidence.
    if len(spoken) >= 4:
        contains = [a for a in catalogue if spoken in a.name]
        if contains:
            return min(contains, key=lambda a: len(a.name))

    # Last resort, for the ones the recogniser mangled.
    close = difflib.get_close_matches(spoken, [a.name for a in catalogue],
                                      n=1, cutoff=0.85)
    if close:
        return next(a for a in catalogue if a.name == close[0])

    return None


def names():
    """Canonical names only -- aliases and misspellings stay hidden from `help`.

    Sorted for reading. The catalogue itself stays in search order, because
    find() relies on system apps being matched before Start Menu ones.
    """
    return sorted(app.name for app in all_apps())


def remember(name, path):
    """Save an app you picked and make it findable straight away."""
    app = installed.remember(name, path)
    refresh()
    return app


def counts():
    """How many of each kind, for the log line the window shows at startup."""
    tally = {}
    for app in all_apps():
        tally[app.kind] = tally.get(app.kind, 0) + 1
    return tally
