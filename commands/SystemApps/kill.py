"""Force an app to stop. Unlike `close`, it does not get to save anything."""

import psutil

import apps
import win
from output import say

NAME = "kill"
TAKES_ARG = True
HELP = "kill <app>   -- force an app to stop, without saving ('kill all <app>' for every one)"


def run(argument):
    argument = argument.strip()

    every = False
    if argument.lower().startswith("all "):
        every = True
        argument = argument[4:].strip()

    app = apps.find(argument)
    if app is None:
        say(f"I don't know an app called '{argument}'.")
        return

    if app.protected:
        say(f"I won't kill {app.name} -- it is the Windows shell, and killing it "
            f"would take the taskbar and desktop with it. "
            f"Try 'computer close {app.name}' instead.")
        return

    if every:
        handles = win.windows_of(app)
    else:
        newest = win.newest_window_of(app)
        handles = [newest] if newest else []

    if not handles:
        say(f"{app.name} does not seem to be open.")
        return

    # Several windows can belong to one process, so collect the ids first and
    # terminate each process once.
    pids = {win.pid_of_window(hwnd) for hwnd in handles}

    killed = 0
    for pid in pids:
        try:
            psutil.Process(pid).terminate()
            killed += 1
        except psutil.NoSuchProcess:
            pass  # already gone, nothing to do
        except psutil.AccessDenied:
            say(f"Not allowed to kill {app.name} (pid {pid}). "
                f"It may need an administrator.")

    if killed:
        process = "process" if killed == 1 else "processes"
        say(f"Killed {killed} {app.name} {process}.")
