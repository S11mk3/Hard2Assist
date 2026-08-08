"""Programs installed on this PC.

Two sources. Everything in the Start Menu is discovered automatically, so a
freshly installed program is openable without touching any code. Anything
not found there -- a portable exe, a shortcut with an odd name -- the user
points at once with the file picker, and it is remembered in a JSON file.
"""

import json
import os

from .app import App

USER_DIR = os.path.join(os.environ.get("APPDATA", ""), "Hard2Assist")
USER_FILE = os.path.join(USER_DIR, "my-apps.json")

START_MENUS = [
    os.path.join(os.environ.get("PROGRAMDATA", ""),
                 r"Microsoft\Windows\Start Menu\Programs"),
    os.path.join(os.environ.get("APPDATA", ""),
                 r"Microsoft\Windows\Start Menu\Programs"),
]

# Start Menu folders are full of shortcuts that are not the program itself:
# uninstallers, manuals, "visit our website" links. Launching one of those by
# accident is confusing at best and destructive at worst, so they are skipped.
SKIP_WORDS = (
    "uninstall", "readme", "read me", "release notes", "documentation",
    "help", "manual", "license", "licence", "website", "web site",
    "what's new", "whats new", "support", "报告", "eula", "changelog",
    "repair", "remove ", "setup", "installer",
)


def _looks_useful(name):
    lowered = name.lower()
    return not any(word in lowered for word in SKIP_WORDS)


def scan():
    """Every Start Menu shortcut, as an App.

    The .lnk file itself is what gets launched -- os.startfile() follows the
    shortcut, so its target never needs to be resolved here.
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
                    # title, but closing these is not guaranteed (see README).
                    title=name,
                    kind="installed",
                )

    return list(found.values())


def _load_user_file():
    try:
        with open(USER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _user_app(name, path):
    """Build the App for a user-picked program.

    These are the reliable entries: the actual executable is known, so close
    and kill can match the process by name instead of guessing from a window
    title.
    """
    process = os.path.basename(path)
    return App(
        name=name.lower().strip(),
        launch=path,
        title=os.path.splitext(process)[0],
        process=process if process.lower().endswith(".exe") else "",
        kind="mine",
    )


def mine():
    """Apps the user pointed at themselves, loaded from the JSON file."""
    return [_user_app(name, path)
            for name, path in _load_user_file().items()
            if isinstance(path, str)]


def remember(name, path):
    """Save a picked app to the JSON file, so the user is only asked once."""
    name = name.lower().strip()
    entries = _load_user_file()
    entries[name] = path

    os.makedirs(USER_DIR, exist_ok=True)
    with open(USER_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)

    return _user_app(name, path)
