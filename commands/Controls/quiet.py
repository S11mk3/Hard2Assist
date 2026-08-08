"""Stop Hard2Assist speaking its replies."""

import speech
from output import detail, say

NAME = "quiet"
TAKES_ARG = False
ALIASES = ("silent", "shush")

# "stop talking" has to be listed here rather than left to the word scan:
# it opens with the name of the `stop` command, so without this it quits
# Hard2Assist instead of silencing it.
PHRASES = ("stop talking", "stop speaking", "be quiet", "shut up",
           "stop the voice")
HELP = "quiet        -- stop speaking replies ('speak' turns it back on)"


def run():
    if not speech.available():
        detail("I have no voice on this PC anyway.")
        return

    # Confirm before disabling speech, or the confirmation itself would
    # never be heard.
    say("Going quiet")
    speech.set_enabled(False)
