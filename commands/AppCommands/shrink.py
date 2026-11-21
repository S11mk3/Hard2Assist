"""Put an app back to its normal size. The opposite of `fullscreen`."""

import session
import win

NAME = "shrink"
TAKES_ARG = True
ALIASES = ("shrinks", "shrunk")
# "restore" is Windows' own word for this, and is safe because restoring undoes minimised too.
SYNONYMS = ("restore", "windowed", "smaller", "unmaximize", "unmaximise")

# Each contains "fullscreen", the opposite command's name, so without these "exit fullscreen"
# would put the app into fullscreen.
PHRASES = ("exit fullscreen", "exit full screen", "leave fullscreen", "leave full screen",
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
    session.each_window(argument, win.restore_window, "Restored", "resize")
