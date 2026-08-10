"""Force an app to stop. Unlike `close`, it does not get to save anything."""

import psutil

import session
import win
from output import detail, say

NAME = "kill"
TAKES_ARG = True
ALIASES = ("kil", "keel", "killed")
HELP = "kill <app>   -- force an app to stop, without saving ('kill all <app>' for every one)"
EXAMPLE = "kill notepad"


def run(argument):
    argument = argument.strip()

    # "kill all cmd" targets every window; plain "kill cmd" targets only the
    # most recently opened one.
    every = False
    if argument.lower().startswith("all "):
        every = True
        argument = argument[4:].strip()

    app = session.resolve(argument)
    if app is None:
        session.unknown(argument)
        return

    if app.protected:
        say(f"I won't kill {app.name}")
        detail(f"It is the Windows shell, and killing it would take the taskbar "
               f"and desktop with it. Try 'computer close {app.name}' instead.")
        return

    if every:
        handles = win.windows_of(app)
    else:
        newest = win.newest_window_of(app)
        handles = [newest] if newest else []

    if not handles:
        say(f"{app.name} does not seem to be open.")
        return

    # Several windows can belong to one process, so deduplicate the process
    # ids first and terminate each process once.
    pids = {win.pid_of_window(hwnd) for hwnd in handles}

    killed = 0
    for pid in pids:
        try:
            psutil.Process(pid).terminate()
            killed += 1
        except psutil.NoSuchProcess:
            pass  # already gone
        except psutil.AccessDenied:
            detail(f"Not allowed to kill {app.name} (pid {pid}). "
                   f"It may need an administrator.")

    if killed:
        process = "process" if killed == 1 else "processes"
        say(f"Killed {killed} {app.name} {process}")
