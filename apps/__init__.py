"""The catalogue of everything Hard2Assist can open, searched in this order:

    itself     Hard2Assist                          apps/itself.py
    system     built into Windows                   apps/system.py
    mine       what the user pointed me at          %APPDATA%\\Hard2Assist\\my-apps.json
    folder     Documents, Downloads and the rest    apps/folders.py
    installed  Start Menu, then Store apps          apps/installed.py
    web        websites                             apps/websites.py

The user's own picks come before folders and the Start Menu, so a correction always wins.
`open`, `close` and the rest all go through find().
"""

import collections
import difflib
import threading

from . import folders, installed, itself, system, websites

# How `help apps` labels each source, in the order it lists them.
KINDS = (
    ("system", "Built into Windows"),
    ("folder", "Folders on this PC"),
    ("mine", "Programs you pointed me at"),
    ("installed", "Installed on this PC"),
    ("web", "Websites"),
)

_catalogue = None
_lock = threading.Lock()   # the window builds it in the background while commands may need it


def all_apps():
    """Every known app, in search order. Built once."""
    global _catalogue
    with _lock:
        if _catalogue is None:
            _catalogue = ([itself.ITSELF] + system.APPS + installed.mine() + folders.known()
                          + installed.scan() + installed.scan_store() + websites.SITES)
        return _catalogue


def refresh():
    global _catalogue
    with _lock:
        _catalogue = None


def find(spoken):
    """The App spoken names, or None.

    Forgiving, because nobody says "CCleaner 7" or "Visual Studio Code" in full: an exact name or
    alias, then the shortest name starting with it, then one containing it, then a near miss.
    """
    spoken = (spoken or "").lower().strip()
    if not spoken:
        return None

    catalogue = all_apps()
    for app in catalogue:
        if app.matches(spoken):
            return app

    # Long enough that a clipped word cannot land on any app starting with its first letter.
    if len(spoken) >= 3:
        starts = [app for app in catalogue if app.name.startswith(spoken)]
        if starts:
            return min(starts, key=lambda app: len(app.name))

    if len(spoken) >= 4:
        contains = [app for app in catalogue if spoken in app.name]
        if contains:
            return min(contains, key=lambda app: len(app.name))

    close = difflib.get_close_matches(spoken, [app.name for app in catalogue], n=1, cutoff=0.85)
    return next((app for app in catalogue if app.name == close[0]), None) if close else None


def _listed():
    """Each listed app once, under the first source that has its name: the one find() opens."""
    seen = set()
    labels = dict(KINDS)
    for app in all_apps():
        if app.kind in labels and app.name not in seen:
            seen.add(app.name)
            yield app


def names_by_kind():
    """[(label, sorted names)] for `help apps`."""
    grouped = collections.defaultdict(list)
    for app in _listed():
        grouped[app.kind].append(app.name)
    return [(label, sorted(grouped[kind])) for kind, label in KINDS if grouped[kind]]


def counts():
    """How many apps of each kind, counted exactly as `help apps` lists them."""
    return collections.Counter(app.kind for app in _listed())


def remember(name, path):
    """Save an app or website the user picked, findable at once."""
    app = installed.remember(name, path)
    refresh()
    return app


def forget(name):
    """Drop something remember() saved. True if there was one."""
    dropped = installed.forget(name)
    if dropped:
        refresh()
    return dropped
