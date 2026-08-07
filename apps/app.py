"""What an app is, wherever it came from."""

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
