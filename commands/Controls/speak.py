"""Start talking back again."""

import speech
from output import announce, say

NAME = "speak"
TAKES_ARG = False
ALIASES = ("speech", "talk", "unmute yourself", "voice")
HELP = "speak        -- start speaking replies again"


def run():
    if not speech.available():
        say("I could not start a voice on this PC.")
        return

    speech.set_enabled(True)
    announce("Speaking again")
