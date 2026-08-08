"""The catalogue of everything Hard2Assist can open.

Four sources, searched in this order:

    system     apps built into Windows          apps/system.py
    mine       apps the user picked manually    %APPDATA%\\Hard2Assist\\my-apps.json
    installed  found in the Start Menu          apps/installed.py
    web        websites                         apps/websites.py

The `open`, `close` and `kill` commands do not distinguish between them --
everything goes through find(). User picks come before the Start Menu scan
so that manually correcting a bad match takes priority.
"""

import difflib

from . import installed, system, websites

_catalogue = None


def all_apps():
    """Every known app, in search order. Scanned once and cached."""
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
    """Discard the cached catalogue. Called after remembering a new app."""
    global _catalogue
    _catalogue = None


def find(spoken):
    """Return the App the user asked for, or None.

    Deliberately forgiving: Start Menu shortcuts carry version numbers and
    branding ("CCleaner 7", "Visual Studio Code") that nobody says out loud,
    so an exact match alone would miss most installed programs.

    Whichever app matches, its real name is spoken back in the confirmation,
    so the user always hears which one was picked.
    """
    if not spoken:
        return None

    spoken = spoken.lower().strip()
    catalogue = all_apps()

    # 1. Exact name or declared alias.
    for app in catalogue:
        if app.matches(spoken):
            return app

    # 2. Prefix: "ccleaner" should find "ccleaner 7". Shortest name wins
    #    as the closest fit.
    starts = [a for a in catalogue if a.name.startswith(spoken)]
    if starts:
        return min(starts, key=lambda a: len(a.name))

    # 3. Substring: "obs" inside "obs studio" -- but only for words long
    #    enough that the match is unlikely to be a coincidence.
    if len(spoken) >= 4:
        contains = [a for a in catalogue if spoken in a.name]
        if contains:
            return min(contains, key=lambda a: len(a.name))

    # 4. Fuzzy match, as a last resort for names the recogniser mangled.
    close = difflib.get_close_matches(spoken, [a.name for a in catalogue],
                                      n=1, cutoff=0.85)
    if close:
        return next(a for a in catalogue if a.name == close[0])

    return None


# The catalogue's sources, with the labels `help` shows them under, in the
# order they are listed. Ordered by how likely the user is to want the group,
# not by how the catalogue is searched.
KINDS = (
    ("system", "Built into Windows"),
    ("mine", "Programs you pointed me at"),
    ("installed", "Installed on this PC"),
    ("web", "Websites"),
)


def names():
    """Canonical names only; aliases and misspellings stay hidden from `help`.

    Deduplicated: the Start Menu scan turns up plenty of apps that system.py
    already lists by hand, so notepad, paint, task manager and a dozen more
    otherwise appear twice over.

    Sorted for display. The catalogue itself remains in search order, since
    find() relies on system apps being matched before Start Menu ones.
    """
    return sorted({app.name for app in all_apps()})


def names_by_kind():
    """Names grouped by where they came from, as [(label, names)].

    `help` reads better split up than as one run of 140 names: which of them
    are Windows' own, which were found on this PC and which are websites is
    most of what makes the list understandable.

    A name is listed once, under the first source that claims it -- the same
    precedence find() applies, so what is shown is what would be opened.
    """
    seen = set()
    grouped = {kind: [] for kind, _ in KINDS}

    for app in all_apps():
        if app.name in seen or app.kind not in grouped:
            continue

        seen.add(app.name)
        grouped[app.kind].append(app.name)

    return [(label, sorted(grouped[kind]))
            for kind, label in KINDS if grouped[kind]]


def remember(name, path):
    """Save an app the user picked and make it findable immediately."""
    app = installed.remember(name, path)
    refresh()
    return app


def counts():
    """Number of apps per source kind, for the GUI's startup log line.

    Deduplicated exactly as names() is, so the count in the window agrees
    with the list `help` prints instead of being sixteen higher.
    """
    seen = set()
    tally = {}

    for app in all_apps():
        if app.name in seen:
            continue

        seen.add(app.name)
        tally[app.kind] = tally.get(app.kind, 0) + 1

    return tally
