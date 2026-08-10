"""Folders you can open by name.

The same trick that makes websites work, applied to folders: os.startfile()
opens a folder in File Explorer exactly as it opens a program, so "computer
open documents" goes through the same `open` as everything else and needs no
command of its own. `close downloads` and `focus pictures` come free with it.

Where each folder actually lives is asked of Windows rather than assumed --
see win.known_folder(). On this PC Downloads sits on a different drive
entirely, and every folder here can be moved the same way.
"""

import os

import win

from .app import App

# Known folder ids, from the Windows shell. Fixed values -- these are the
# names Windows itself uses, not paths, which is the whole point of them.
IDS = {
    "desktop": "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}",
    "documents": "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}",
    "downloads": "{374DE290-123F-4565-9164-39C4925E467B}",
    "pictures": "{33E28130-4E1E-4676-835A-98395C3BC3BB}",
    "music": "{4BD8D571-6D19-48D3-BE97-422220080E43}",
    "videos": "{18989B1D-99B5-455B-841C-AB7C74E4DDFC}",
    "home": "{5E6C858F-0E22-4760-9AFE-EA3317B67173}",
}

# What the folder's Explorer window is titled, when it differs from the name.
# Explorer titles a window after the folder on disk, so the home folder shows
# the Windows account name rather than the word "home".
TITLES = {
    "home": os.path.basename(os.environ.get("USERPROFILE", "")) or "Users",
}

ALIASES = {
    "desktop": ("my desktop",),
    "documents": ("my documents", "docs", "document"),
    "downloads": ("my downloads", "download", "downloaded"),
    "pictures": ("my pictures", "photos", "picture", "images"),
    "music": ("my music", "songs"),
    "videos": ("my videos", "video", "movies"),
    "home": ("my folder", "user folder", "home folder", "my files"),
}


def known():
    """Every known folder that exists on this PC, as Apps.

    A folder Windows has no path for, or one that has been deleted, is left
    out rather than listed: a catalogue entry that fails the moment it is
    used is worse than the app simply not knowing the word.
    """
    found = []

    for name, guid in IDS.items():
        path = win.known_folder(guid)
        if not path or not os.path.isdir(path):
            continue

        found.append(App(
            name=name,
            launch=path,

            # Explorer's window title is the folder name and its class is
            # always CabinetWClass, so the two together find this folder's
            # window in particular -- which is what lets `close downloads`
            # close only that one and leave the other folders open.
            title=TITLES.get(name, os.path.basename(path) or name),
            window_class="CabinetWClass",

            aliases=ALIASES.get(name, ()),

            # Every folder window is explorer.exe, and `kill` terminates by
            # process. Without this, "kill documents" would take the taskbar
            # and the desktop down with it -- the same reason `file explorer`
            # is protected in system.py.
            protected=True,

            kind="folder",
        ))

    return found
