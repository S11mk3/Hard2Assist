"""Force an app to stop. Unlike `close`, it does not get to save anything."""

import psutil

import session
import settings
import win
from output import detail, plural, say, warn

NAME = "kill"
TAKES_ARG = True
EXACT_ONLY = True
ALIASES = ("kil", "keel", "killed")
HELP = "kill <app> -- force an app to stop, without saving ('kill all <app>' for every one)"
EXAMPLE = "kill notepad"

ABOUT = """\
Kill forces an app to stop immediately, without letting it save anything.
It is what to use when an app has stopped responding, or when "close" is
refused. Anything unsaved in it is lost, so try "close" first.
Plain "kill notepad" stops the one opened most recently; "kill all
notepad" stops every one.
I refuse to kill a website, which would take your whole browser with it,
or anything whose window belongs to the Windows shell or to the process
that hosts Store apps, which would take the others down too.\
"""

# Processes holding windows for many apps at once, and what killing one would take with it.
SHARED_HOSTS = {
    "explorer.exe": "the taskbar and the desktop",
    "applicationframehost.exe": "every other Store app that is open",
}


def run(argument):
    found = session.target(argument)
    if found is None:
        return
    app, every = found
    prefix = settings.get("prefix")

    if app.kind == "itself":
        say("I won't kill myself.")
        detail(f"Say '{prefix} stop' to shut me down properly.")
        return
    if app.kind == "web":
        say(f"I won't kill {app.name}.")
        detail(f"It's a tab in your browser, and killing it would close the whole browser. "
               f"Say '{prefix} close {app.name}' to close just the tab.")
        return

    handles = session.windows(app, every)
    if handles is None:
        return

    killed = 0
    for pid in {win.pid_of_window(hwnd) for hwnd in handles}:   # one process can own many windows
        try:
            process = psutil.Process(pid)
            shared = SHARED_HOSTS.get(process.name().lower())
            if shared:
                say(f"I won't kill {app.name}.")
                detail(f"Its window belongs to {process.name()}, and killing that would take {shared} "
                       f"with it. Try '{prefix} close {app.name}' instead.")
                continue
            process.terminate()
            killed += 1
        except psutil.NoSuchProcess:
            pass
        except psutil.AccessDenied:
            warn(f"Not allowed to kill {app.name}. It may need an administrator.")

    if killed:
        say(f"Killed {plural(killed, app.name + ' process')}")
