"""Force an app to stop. Unlike `close`, it does not get to save anything."""

import psutil

import apps
import win

NAME = "kill"
TAKES_ARG = True
HELP = "kill <app>   -- force an app to stop, without saving"


def run(argument):
    app = apps.find(argument)
    if app is None:
        print(f"I don't know an app called '{argument}'.")
        return

    if app.protected:
        print(f"I won't kill {app.name} -- it is the Windows shell, and killing "
              f"it would take the taskbar and desktop with it. "
              f"Try 'computer close {app.name}' instead.")
        return

    handles = win.windows_of(app)
    if not handles:
        print(f"{app.name} does not seem to be open.")
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
            print(f"Not allowed to kill {app.name} (pid {pid}). "
                  f"It may need an administrator.")

    if killed:
        process = "process" if killed == 1 else "processes"
        print(f"Killed {killed} {app.name} {process}.")
