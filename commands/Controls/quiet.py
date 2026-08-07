"""Stop Hard2Assist talking back, or start again."""

import speech
from output import detail, say

NAME = "quiet"
TAKES_ARG = False
ALIASES = ("silent", "shush", "mute yourself", "stop talking")
HELP = "quiet        -- stop speaking replies ('speak' turns it back on)"


def run():
    if not speech.available():
        detail("I have no voice on this PC anyway.")
        return

    # Say goodbye before going quiet, or the confirmation never gets out.
    say("Going quiet")
    speech.set_enabled(False)
