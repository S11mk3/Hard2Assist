"""The catalogue of apps Hard2Assist can open and close.

This is the single source of truth. `open` launches App.launch, `close`/`kill`
find the app's windows with App.title / App.window_class, and `help` prints
App.name. Adding an app means adding one line here and nothing else.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class App:
    name: str
    """Canonical name. This is what `help` prints and what we say back to the user."""

    launch: str
    """Passed to os.startfile(). Can be an exe, a .msc console or a ms-settings: URI."""

    title: str = ""
    """Case-insensitive substring of the window title, used to find the app once open."""

    aliases: tuple = ()
    """Other things the user might say. Includes misspellings the recogniser produces."""

    window_class: str = ""
    """Win32 class name, for apps whose title is not stable (explorer shows the folder name)."""

    protected: bool = False
    """Never force-kill this. Terminating explorer.exe takes down the taskbar and desktop."""

    def matches(self, spoken):
        spoken = spoken.lower().strip()
        return spoken == self.name or spoken in self.aliases


# Aliases are lowercase. The odd-looking ones ("task manger", "disc managment")
# are not typos in this file -- they are what speech recognition actually returns.
APPS = [
    App("calculator", "calc", "Calculator", ("calc",)),
    App("notepad", "notepad", "Notepad"),
    App("paint", "mspaint", "Paint"),
    App("wordpad", "write", "WordPad"),
    App("snipping tool", "snippingtool", "Snipping Tool", ("screenshot",)),

    App("file explorer", "explorer", aliases=("explorer",),
        window_class="CabinetWClass", protected=True),

    App("task manager", "taskmgr", "Task Manager", ("taskmgr", "task manger")),
    App("command prompt", "cmd", "cmd.exe", ("cmd",)),
    App("powershell", "powershell", "Windows PowerShell", ("power",)),

    App("settings", "ms-settings:", "Settings"),
    App("control panel", "control", "Control Panel", ("control pan",)),
    App("registry editor", "regedit", "Registry Editor", ("regedit",)),

    App("device manager", "devmgmt.msc", "Device Manager",
        ("device manger", "device man")),
    App("disk management", "diskmgmt.msc", "Disk Management",
        ("disk managment", "disc managment")),
    App("services", "services.msc", "Services"),
    App("computer management", "compmgmt.msc", "Computer Management",
        ("computer managment", "computer manger")),
    App("event viewer", "eventvwr", "Event Viewer"),

    App("system information", "msinfo32", "System Information"),
    App("resource monitor", "resmon", "Resource Monitor"),
    App("performance monitor", "perfmon", "Performance Monitor",
        ("performance mon",)),
    App("user accounts", "netplwiz", "User Accounts", ("user account",)),

    App("narrator", "narrator", "Narrator"),
    App("magnifier", "magnify", "Magnifier"),
    App("on screen keyboard", "osk", "On-Screen Keyboard"),

    App("edge", "msedge", "Edge"),
    App("vlc", "vlc", "VLC media player"),
]


def find(spoken):
    """Return the App the user asked for, or None. Matches name or alias."""
    if not spoken:
        return None
    for app in APPS:
        if app.matches(spoken):
            return app
    return None


def names():
    """Canonical names only -- aliases and misspellings stay hidden from `help`."""
    return [app.name for app in APPS]
