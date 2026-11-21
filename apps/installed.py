"""Programs on this PC: Start Menu shortcuts and Microsoft Store apps, found at startup, plus what
the user pointed at with the file picker or saved with `remember website`."""

import contextlib
import os
import re

import storage
from output import detail

from .app import App

USER_FILE = os.path.join(storage.USER_DIR, "my-apps.json")

START_MENUS = [os.path.join(os.environ[variable], r"Microsoft\Windows\Start Menu\Programs")
               for variable in ("PROGRAMDATA", "APPDATA") if os.environ.get(variable)]

# Shortcuts that are a program's paperwork rather than the program, which nobody wants opened by
# accident. Whole words plus a plural, so "Revo Uninstaller" stays while "Uninstall Revo
# Uninstaller" goes.
SKIP_WORDS = (
    "uninstall", "readme", "read me", "release notes", "documentation",
    "help", "manual", "license", "licence", "website", "web site",
    "what's new", "whats new", "support", "eula", "changelog",
    "repair", "remove", "setup", "installer",
)
_SKIP = re.compile("|".join(rf"\b{re.escape(word)}s?\b" for word in SKIP_WORDS), re.IGNORECASE)


def _useful(name):
    return _SKIP.search(name) is None


def scan():
    """Every Start Menu shortcut. The .lnk itself is launched, so its target never needs reading."""
    found = {}
    for root in START_MENUS:
        for folder, _dirs, files in os.walk(root):
            for file in files:
                name, extension = os.path.splitext(file)
                key = name.lower()
                if extension.lower() == ".lnk" and _useful(name) and key not in found:
                    found[key] = App(key, os.path.join(folder, file), title=name, kind="installed")
    return list(found.values())


def scan_store():
    """Microsoft Store apps, which have no Start Menu shortcut to find.

    Read from the shell's Apps folder, where a Store app's id contains "!". Each opens through
    shell:AppsFolder, and its window is titled with its name.
    """
    try:
        import comtypes
        import comtypes.client
        with contextlib.suppress(OSError):
            comtypes.CoInitialize()
        shell = comtypes.client.CreateObject("Shell.Application", dynamic=True)
        items = shell.NameSpace("shell:AppsFolder").Items()
        entries = [(items.Item(i).Name, items.Item(i).Path) for i in range(items.Count)]
    except Exception:
        return []

    return [App(name.lower(), f"shell:AppsFolder\\{path}", title=name, kind="installed")
            for name, path in entries if "!" in path and _useful(name)]


# The user's {name: path}, read once and kept: a remember or forget that cannot be saved still
# holds until the app closes, as it says it will.
_entries = None


def _user_entries():
    global _entries
    if _entries is None:
        _entries = {name: path for name, path in storage.read_json(USER_FILE).items()
                    if isinstance(path, str)}
    return _entries


def _user_app(name, path):
    """A picked program -- whose executable is known, so close and kill match it exactly -- or a
    remembered website."""
    if path.lower().startswith(("http://", "https://")):
        return App(name, path, title=name, kind="web")

    process = os.path.basename(path)
    return App(name, path, title=os.path.splitext(process)[0],
               process=process if process.lower().endswith(".exe") else "", kind="mine")


def mine():
    return [_user_app(name, path) for name, path in _user_entries().items()]


def _save(otherwise):
    error = storage.write_json(USER_FILE, _user_entries())
    if error is not None:
        detail(f"(Could not write {os.path.basename(USER_FILE)}: {error})")
        detail(f"({otherwise})")


def remember(name, path):
    name = name.lower().strip()
    _user_entries()[name] = path
    _save(f"I'll remember {name} until I'm closed, but not after.")
    return _user_app(name, path)


def forget(name):
    """Drop a remembered entry. True if there was one, even if the file could not be written."""
    name = name.lower().strip()
    if _user_entries().pop(name, None) is None:
        return False
    _save(f"I'll forget {name} until I'm closed, but it will be back next time.")
    return True
