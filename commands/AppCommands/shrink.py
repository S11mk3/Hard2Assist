"""Put an app back to its normal size. The opposite of `fullscreen`."""

import session
import win
from output import detail, say

NAME = "shrink"
TAKES_ARG = True

# "restore" is what Windows calls this -- the maximise button turns into
# "Restore Down" -- and it is safe to take here because SW_RESTORE undoes a
# minimised window too, so the word means the same thing either way. The rest
# are plain synonyms and the recogniser's guesses.
ALIASES = ("restore", "windowed", "smaller", "shrinks", "shrunk",
           "unmaximize", "unmaximise")

# These have to be listed here rather than left to the word scan: every one of
# them contains "fullscreen", the name of the opposite command, and a real
# command name found anywhere in the sentence wins before anything else is
# tried. So without these, "exit fullscreen" would put the app *into*
# fullscreen -- the exact reverse of what was asked. It is the same trap
# `quiet` avoids by declaring "stop talking".
PHRASES = ("exit fullscreen", "exit full screen",
           "leave fullscreen", "leave full screen",
           "out of fullscreen", "out of full screen")

HELP = "shrink <app> -- put an app back to its normal size"
EXAMPLE = "shrink notepad"

ABOUT = """\
Shrink puts an app back to its normal size, undoing fullscreen.
"restore notepad", "smaller" and "exit fullscreen" all mean this.
It brings back a minimised window too, so it undoes "minimize" as well.
Every window that app has is restored, so fullscreen and shrink are each
other's undo rather than one of them leaving windows behind.\
"""


def run(argument):
    argument = argument.strip()

    # `close` and `kill` take "all <app>", so the phrasing gets used here too.
    if argument.lower().startswith("all "):
        argument = argument[4:].strip()

    app = session.resolve(argument)
    if app is None:
        session.unknown(argument)
        return

    handles = win.windows_of(app)
    if not handles:
        say(f"{app.name} isn't open.")
        return

    # Every window, exactly as `fullscreen` does, so the two are each other's
    # undo rather than one of them leaving windows behind.
    restored = 0
    refused = 0
    for hwnd in handles:
        if win.restore_window(hwnd):
            restored += 1
        else:
            refused += 1

    if restored:
        window = "window" if restored == 1 else "windows"
        say(f"Restored {restored} {app.name} {window}")

    if refused:
        say(f"Windows won't let me resize {app.name}")
        detail("It runs as administrator and Hard2Assist does not. Restart "
               "Hard2Assist as administrator to control it.")
