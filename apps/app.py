"""The App record: one openable thing, wherever it came from."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class App:
    name: str
    """Canonical lowercase name, listed by `help apps` and spoken back in confirmations."""

    launch: str
    """Passed to os.startfile(): an exe, .msc, .lnk, folder, URL or shell: address."""

    title: str = ""
    """Part of the window title (any case), used to find the app once it is open."""

    aliases: tuple = ()
    """Other things the user might say, including what the recogniser hears instead."""

    window_class: str = ""
    """Win32 class name, for apps whose title is not stable (Explorer shows the folder name)."""

    process: str = ""
    """Executable name such as "obs64.exe", when known (user-picked apps)."""

    kind: str = "system"
    """Source: itself, system, mine, folder, installed or web."""

    def matches(self, spoken):
        spoken = spoken.lower().strip()
        return spoken == self.name or spoken in self.aliases

    def owns_process(self, image):
        """Whether an executable belongs to this app, for when its window titles do not match.

        A Start Menu name like "Opera GX Browser" does not match the window "... - Opera", but
        the executable behind it does not drift: one of the name's words must be the executable's
        stem, optionally followed by a version number ("obs" matches obs64.exe; "task manager"
        does not claim taskhostw.exe).
        """
        image = image.lower()
        if not image.endswith(".exe"):
            return False
        if self.process:
            return image == self.process.lower()

        stem = image[:-len(".exe")]
        return any(len(word) >= 3 and re.fullmatch(re.escape(word) + r"\d*", stem)
                   for word in re.split(r"[^a-z0-9]+", self.name.lower()))
