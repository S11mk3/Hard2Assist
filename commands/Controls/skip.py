"""Next and previous track."""

import win
from output import say

NAME = "next"
TAKES_ARG = False
ALIASES = ("skip", "nex", "next track", "forward")
HELP = "next         -- skip to the next track ('back' for the previous one)"


def run():
    win.tap_key(win.VK_MEDIA_NEXT)
    say("Next track")
