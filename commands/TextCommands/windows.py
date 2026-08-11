"""List what is open on screen.

Also the answer to "what does 'it' mean right now": the window commands take
"it" to mean whatever was last named, and this is how you see what is around
to be named.
"""

import os

import win
from output import detail, say

NAME = "windows"
TAKES_ARG = False
ALIASES = ("window",)

# The natural phrasings name no command word at all. Safe to declare even
# though "open" is a command: a phrase is matched before any single word, so
# "what's open" reaches here rather than running `open` with no argument.
PHRASES = ("what's open", "whats open", "what is open", "what's running",
           "whats running", "what do i have open")

HELP = "windows      -- list the windows that are open ('what's open')"

ABOUT = """\
Windows lists what is open on screen right now.
"what's open", "what's running" and "what do I have open" all reach it.
It is also the answer to what "it" means: the window commands take "it"
to mean whatever you last named, and this shows what is around to name.
The taskbar, the desktop and my own window are left out, since none of
them is something you opened.\
"""

# Always-on shell windows that are not something the user opened and would
# not think of as being "open". Matched on window class, which does not
# change with the Windows display language the way a title does.
SHELL_CLASSES = {
    "Progman",              # the desktop
    "WorkerW",              # the desktop's wallpaper layer
    "Shell_TrayWnd",        # the taskbar
    "Windows.UI.Core.CoreWindow",   # Start menu, search, notification flyouts
    "ApplicationFrameWindow",       # empty frames left behind by store apps
}

# The log panel is comfortable at roughly this width.
MAX_TITLE = 70


def _listed():
    """Titles of the windows worth telling the user about."""
    ours = os.getpid()

    found = []
    for hwnd, title, class_name in win.visible_windows():
        if class_name in SHELL_CLASSES:
            continue

        # Our own window, and any file picker or message box we put up.
        if win.pid_of_window(hwnd) == ours:
            continue

        if title not in found:
            found.append(title)

    return found


def run():
    titles = _listed()

    if not titles:
        say("Nothing is open apart from me.")
        return

    # Spoken as a count, written as the list -- reading a dozen window titles
    # out loud takes longer than looking at them, the same split `help` and
    # `disk` make.
    window = "window" if len(titles) == 1 else "windows"
    say(f"{len(titles)} {window} open. They're on screen.")

    detail("")
    detail(f"OPEN WINDOWS   ({len(titles)})")
    for title in titles:
        if len(title) > MAX_TITLE:
            title = title[:MAX_TITLE - 3] + "..."
        detail(f"  {title}")
    detail("")
