"""Start speaking replies again after `quiet`."""

import speech
from output import detail, say

NAME = "speak"
TAKES_ARG = False
ALIASES = ("speech", "talk", "voice")
HELP = "speak        -- start speaking replies again"


def run():
    if not speech.available():
        detail("I could not start a voice on this PC.")
        return

    speech.set_enabled(True)
    say("Speaking again")
