"""Apps built into Windows.

Listed by hand because they need details that cannot be discovered
automatically: the window title to find them by, and which ones must never be
killed.
"""

from .app import App

# Aliases are lowercase. The odd-looking entries ("task manger", "disc
# managment") are not typos -- they are what speech recognition returns for
# those names.
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
]
