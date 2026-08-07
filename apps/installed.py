"""Programs installed on this PC.

Two sources. Everything in the Start Menu is found automatically, so a freshly
installed program is openable without touching any code. Anything that is not
there -- a portable exe, something with an odd shortcut name -- you point at
once with the file picker and it is remembered.
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

# Start Menu folders are full of things that are not the program: uninstallers,
# manuals, "visit our website" links. Opening one of those by accident is at
# best confusing and at worst destructive, so they are left out.
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

    The .lnk itself is what gets launched -- os.startfile follows it, so we never
    have to work out what it points at.
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
                    continue  # first one wins

                found[key] = App(
                    name=key,
                    launch=os.path.join(folder, file),
                    # Best effort: most programs put their name in their window
                    # title. See the README -- closing these is not guaranteed.
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


def mine():
    """Apps you pointed at yourself.

    These are the reliable ones: we have the actual .exe, so close and kill can
    match the process by name instead of guessing from a window title.
    """
    apps = []
    for name, path in _load_user_file().items():
        if not isinstance(path, str):
            continue
        process = os.path.basename(path)
        apps.append(App(
            name=name.lower(),
            launch=path,
            title=os.path.splitext(process)[0],
            process=process if process.lower().endswith(".exe") else "",
            kind="mine",
        ))
    return apps


def remember(name, path):
    """Save an app you picked, so you are only asked once."""
    name = name.lower().strip()
    entries = _load_user_file()
    entries[name] = path

    os.makedirs(USER_DIR, exist_ok=True)
    with open(USER_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)

    return App(
        name=name,
        launch=path,
        title=os.path.splitext(os.path.basename(path))[0],
        process=(os.path.basename(path)
                 if path.lower().endswith(".exe") else ""),
        kind="mine",
    )
