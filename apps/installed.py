"""Programs installed on this PC.

Two sources. Everything in the Start Menu is discovered automatically, so a
freshly installed program is openable without touching any code. Anything not
found there -- a portable exe, a shortcut with an odd name -- the user points
at once with the file picker, and it is remembered in a JSON file.
"""

import json
import os
import re

import settings

from .app import App

USER_FILE = os.path.join(settings.USER_DIR, "my-apps.json")

START_MENUS = [
    os.path.join(os.environ.get("PROGRAMDATA", ""),
                 r"Microsoft\Windows\Start Menu\Programs"),
    os.path.join(os.environ.get("APPDATA", ""),
                 r"Microsoft\Windows\Start Menu\Programs"),
]

# Start Menu folders are full of shortcuts that are not the program itself:
# uninstallers, manuals, "visit our website" links. Launching one by accident
# is confusing at best and destructive at worst, so they are skipped.
SKIP_WORDS = (
    "uninstall", "readme", "read me", "release notes", "documentation",
    "help", "manual", "license", "licence", "website", "web site",
    "what's new", "whats new", "support", "eula", "changelog",
    "repair", "remove", "setup", "installer",
)

# Matched as whole words plus an optional plural, not as substrings: "Revo
# Uninstaller" is a real program somebody installed on purpose, and a plain
# substring test loses it to the "uninstall" entry -- while still needing to
# drop "Uninstall Revo Uninstaller" beside it in the same folder.
_SKIP = re.compile(
    "|".join(rf"\b{re.escape(word)}s?\b" for word in SKIP_WORDS), re.IGNORECASE
)


def _looks_useful(name):
    """Whether a shortcut name is the program rather than its paperwork."""
    return _SKIP.search(name) is None


def scan():
    """Every Start Menu shortcut, as an App.

    The .lnk file itself is what gets launched: os.startfile() follows the
    shortcut, so its target never needs resolving here.
    """
    found = {}

    for root in START_MENUS:
        if not root or not os.path.isdir(root):
            continue

        for folder, _dirs, files in os.walk(root):
            for file in files:
                if not file.lower().endswith(".lnk"):
                    continue

                name = os.path.splitext(file)[0]
                if not _looks_useful(name):
                    continue

                key = name.lower()
                if key in found:
                    continue  # first occurrence wins

                found[key] = App(
                    name=key,
                    launch=os.path.join(folder, file),
                    # Best effort: most programs put their name in the window
                    # title, but closing these is not guaranteed.
                    title=name,
                    kind="installed",
                )

    return list(found.values())


# The user's {name: path} entries, read from the file once and then kept here.
# In memory rather than re-read each time, so a remember or forget that could
# not be saved still holds until the app is closed, as it says it will.
_entries = None


def _user_entries():
    """The saved {name: path} entries, or {} if the file is missing or bad."""
    global _entries
    if _entries is None:
        try:
            with open(USER_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
        except (OSError, ValueError):
            loaded = {}
        _entries = loaded if isinstance(loaded, dict) else {}
    return _entries


def _user_app(name, path):
    """Build the App for a user-picked program or a remembered website.

    Programs are the reliable entries: the executable is known, so close and
    kill can match the process by name instead of guessing from a window
    title. A URL (from `remember website`) becomes a web App like the ones
    in websites.py, titled by name so `focus` can find the open tab.
    """
    name = name.lower().strip()

    if path.lower().startswith(("http://", "https://")):
        return App(name=name, launch=path, title=name, kind="web")

    process = os.path.basename(path)
    return App(
        name=name,
        launch=path,
        title=os.path.splitext(process)[0],
        process=process if process.lower().endswith(".exe") else "",
        kind="mine",
    )


def mine():
    """Apps the user pointed at themselves, loaded from the JSON file."""
    return [_user_app(name, path)
            for name, path in _user_entries().items()
            if isinstance(path, str)]


def _save_user_file():
    """Write the entries back. False when the folder is unwritable."""
    try:
        os.makedirs(settings.USER_DIR, exist_ok=True)
        with open(USER_FILE, "w", encoding="utf-8") as f:
            json.dump(_user_entries(), f, indent=2)
        return True
    except OSError as e:
        # Imported late so this module stays importable before output is.
        from output import detail
        detail(f"(Could not write {os.path.basename(USER_FILE)}: {e})")
        return False


def remember(name, path):
    """Save a picked app to the JSON file, so the user is only asked once."""
    name = name.lower().strip()
    _user_entries()[name] = path

    if not _save_user_file():
        from output import detail
        detail(f"(I'll remember {name} until I'm closed, but not after.)")

    return _user_app(name, path)


def forget(name):
    """Drop a remembered entry. True if there was one to drop.

    True even when the file could not be written: the entry is gone for this
    session, and the failure has already been reported.
    """
    name = name.lower().strip()
    entries = _user_entries()

    if name not in entries:
        return False

    del entries[name]

    if not _save_user_file():
        from output import detail
        detail(f"(I'll forget {name} until I'm closed, but it will be back "
               "next time.)")

    return True
