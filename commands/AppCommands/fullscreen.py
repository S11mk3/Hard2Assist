"""Fill the screen with an app. The opposite of `shrink`."""

import session
import win

NAME = "fullscreen"
TAKES_ARG = True
ALIASES = ("maximized", "maximised", "maximizes")
SYNONYMS = ("maximize", "maximise", "expand", "enlarge", "bigger")

# The recogniser writes "full screen" as two words more often than one.
PHRASES = ("full screen",)

HELP = "fullscreen <app> -- fill the screen with an app ('shrink' puts it back)"
EXAMPLE = "fullscreen notepad"

ABOUT = """\
Fullscreen fills the screen with an app, the same as its maximise button.
"maximize notepad", "full screen notepad" and "fullscreen it" all work.
Every window that app has is maximised, not only the one in front.
Say "shrink" or "exit fullscreen" to put it back to its normal size.\
"""


def run(argument):
    session.each_window(argument, win.maximize_window, "Maximized", "maximize")
