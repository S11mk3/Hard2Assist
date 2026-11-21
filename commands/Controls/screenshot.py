"""Save a picture of the whole screen."""

import win
from output import say, warn

NAME = "screenshot"
TAKES_ARG = False
ALIASES = ("screenshots",)
SYNONYMS = ("capture",)
PHRASES = ("screen shot", "print screen", "take a screen shot")
HELP = "screenshot -- save a picture of the screen to Pictures"

ABOUT = """\
Screenshot saves a picture of the whole screen.
It presses Win+PrintScreen for you, which is the shortcut Windows itself
answers: the picture lands in your Pictures folder, under Screenshots,
named by date, and the screen dims for a moment to confirm it.
For a picture of one window or a region, say "{prefix} open snipping
tool" instead.\
"""


def run():
    if win.send_keys(win.VK_LWIN, win.VK_SNAPSHOT):
        say("Saved a screenshot to your Pictures folder, under Screenshots.")
    else:
        warn("Windows would not take the screenshot.")
