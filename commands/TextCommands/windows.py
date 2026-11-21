"""List what is open on screen -- which is also what there is to call "it"."""

import os

import win
from output import detail, plural, say

NAME = "windows"
TAKES_ARG = False
SYNONYMS = ("window",)
# A phrase outranks the command word inside it, so "what's open" lands here, not on `open`.
PHRASES = ("what's open", "whats open", "what is open", "what's running", "whats running",
           "what do i have open")
HELP = "windows -- list the windows that are open ('what's open')"

ABOUT = """\
Windows lists what is open on screen right now.
"what's open", "what's running" and "what do I have open" all reach it.
It is also the answer to what "it" means: the window commands take "it"
to mean whatever you last named, and this shows what is around to name.
The taskbar, the desktop and my own window are left out, since none of
them is something you opened.\
"""

# Shell windows nobody thinks of as open, by class, which does not change with the language.
SHELL_CLASSES = {
    "Progman",                       # the desktop
    "WorkerW",                       # the wallpaper layer
    "Shell_TrayWnd",                 # the taskbar
    "Windows.UI.Core.CoreWindow",    # Start, search and notification flyouts
    "ApplicationFrameWindow",        # empty frames left behind by Store apps
}

MAX_TITLE = 70


def _listed():
    titles = []
    for hwnd, title, class_name in win.visible_windows():
        # Not our own window, file picker or message box either.
        if class_name not in SHELL_CLASSES and win.pid_of_window(hwnd) != os.getpid() and title not in titles:
            titles.append(title)
    return titles


def run():
    titles = _listed()
    if not titles:
        say("Nothing is open apart from me.")
        return

    # A count is quicker to hear than a dozen titles; the titles are quicker to read.
    say(f"{plural(len(titles), 'window')} open. They're on screen.")
    detail("")
    detail(f"OPEN WINDOWS   ({len(titles)})")
    for title in titles:
        detail(f"  {title if len(title) <= MAX_TITLE else title[:MAX_TITLE - 3] + '...'}")
    detail("")
