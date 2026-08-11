"""The App record: one openable thing, wherever it came from."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class App:
    name: str
    """Canonical name. Shown by `help apps` and spoken back in confirmations."""

    launch: str
    """Passed to os.startfile(): an exe, a .msc console, a .lnk shortcut or a URL."""

    title: str = ""
    """Case-insensitive substring of the window title, used to find the app once open."""

    aliases: tuple = ()
    """Other things the user might say, including recogniser misspellings."""

    window_class: str = ""
    """Win32 class name, for apps whose title is not stable (explorer shows the folder name)."""

    protected: bool = False
    """Never force-kill this. Terminating explorer.exe takes down the taskbar and desktop."""

    process: str = ""
    """Image name such as "obs64.exe". Known for user-picked apps, letting close
    and kill match the process exactly instead of guessing from the window title."""

    kind: str = "system"
    """Source: system, installed, mine, folder or web. Used only for reporting."""

    def matches(self, spoken):
        """True if the spoken text is this app's name or one of its aliases."""
        spoken = spoken.lower().strip()
        return spoken == self.name or spoken in self.aliases

    def owns_process(self, image):
        """Whether the given executable image belongs to this app.

        Used to locate windows when title matching fails. Start Menu shortcuts
        are named for the product, not the window -- "Opera GX Browser" opens
        a window titled "... - Opera" -- but the executable name behind the
        window does not drift the way the title does.

        For a user-picked app the real image name is known and compared
        directly. Otherwise one of the app's words must *be* the executable
        stem: "opera" in "opera gx browser" matches opera.exe, and "obs" in
        "obs studio" matches obs64.exe. Only a trailing version number is
        allowed after the word, which stops "task manager" from claiming
        taskhostw.exe.
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
