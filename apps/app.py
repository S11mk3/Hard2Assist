"""What an app is, wherever it came from."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class App:
    name: str
    """Canonical name. This is what `help` prints and what we say back to the user."""

    launch: str
    """Passed to os.startfile(). An exe, a .msc console, a .lnk shortcut or a URL."""

    title: str = ""
    """Case-insensitive substring of the window title, used to find the app once open."""

    aliases: tuple = ()
    """Other things the user might say. Includes misspellings the recogniser produces."""

    window_class: str = ""
    """Win32 class name, for apps whose title is not stable (explorer shows the folder name)."""

    protected: bool = False
    """Never force-kill this. Terminating explorer.exe takes down the taskbar and desktop."""

    process: str = ""
    """Image name such as "obs64.exe". Known for apps you picked yourself, so close and
    kill can match them exactly rather than guessing from the window title."""

    kind: str = "system"
    """Where it came from: system, installed, mine or web. Only used for reporting."""

    def matches(self, spoken):
        spoken = spoken.lower().strip()
        return spoken == self.name or spoken in self.aliases

    def owns_process(self, image):
        """Is this .exe ours? Used to find our windows when the title does not.

        A Start Menu shortcut is named for the product, not the window: "Opera GX
        Browser" opens a window that only ever says "- Opera", so the title we
        guessed while scanning matches nothing. The executable behind the window
        does not drift like that.

        For an app you picked yourself we have the real image name and compare it
        outright. Otherwise the app's own name is all we have, so a word of it has
        to *be* the executable -- "opera" in "opera gx browser" for opera.exe, and
        "obs" in "obs studio" for obs64.exe. Only a trailing version number is
        allowed on the end, so "task manager" cannot reach for taskhostw.exe.
        """
        image = image.lower()
        if not image.endswith(".exe"):
            return False

        if self.process:
            return image == self.process.lower()

        stem = image[:-len(".exe")]
        for word in re.split(r"[^a-z0-9]+", self.name.lower()):
            if len(word) >= 3 and re.fullmatch(re.escape(word) + r"\d*", stem):
                return True
        return False
