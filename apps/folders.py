"""The standard folders, opened by name through the same `open` as everything else.

Where each one lives is asked of Windows rather than assumed; see win.known_folder().
"""

import os

import win

from .app import App

IDS = {
    "desktop": "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}",
    "documents": "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}",
    "downloads": "{374DE290-123F-4565-9164-39C4925E467B}",
    "pictures": "{33E28130-4E1E-4676-835A-98395C3BC3BB}",
    "music": "{4BD8D571-6D19-48D3-BE97-422220080E43}",
    "videos": "{18989B1D-99B5-455B-841C-AB7C74E4DDFC}",
    "home": "{5E6C858F-0E22-4760-9AFE-EA3317B67173}",
}

# Explorer titles a window after the folder on disk, so the home folder shows the account name.
TITLES = {"home": os.path.basename(os.environ.get("USERPROFILE", "")) or "Users"}

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
    """Every standard folder that exists on this PC. One that does not is left out, rather than
    offered and failing the moment it is used."""
    found = []
    for name, guid in IDS.items():
        path = win.known_folder(guid)
        if path and os.path.isdir(path):
            # Class and title together pick out this folder's window, so `close downloads`
            # closes only that one.
            found.append(App(name, path, title=TITLES.get(name, os.path.basename(path) or name),
                             aliases=ALIASES.get(name, ()), window_class="CabinetWClass",
                             kind="folder"))
    return found
