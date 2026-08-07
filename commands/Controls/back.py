"""Previous track."""

import win
from output import announce

NAME = "back"
TAKES_ARG = False
ALIASES = ("previous", "prev", "previous track")
HELP = "back         -- go back to the previous track"


def run():
    win.tap_key(win.VK_MEDIA_PREVIOUS)
    announce("Previous track")
