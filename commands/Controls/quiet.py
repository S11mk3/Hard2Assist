"""Stop Hard2Assist speaking its replies."""

import speech
from output import detail, say

NAME = "quiet"
TAKES_ARG = False
ALIASES = ("silent", "shush")

# Only phrasings the word scan cannot reach on its own. "stop talking" has to
# be listed here because it opens with the name of the `stop` command, so
# without it the app quits instead of going silent. "be quiet" needs no entry:
# it contains this command's own name, so the word scan already finds it.
PHRASES = ("stop talking", "stop speaking", "shut up", "stop the voice")
HELP = "quiet        -- stop speaking replies ('speak' turns it back on)"


def run():
    if not speech.available():
        detail("I have no voice on this PC anyway.")
        return

    # Confirm before disabling speech, or the confirmation itself would
    # never be heard.
    say("Going quiet")
    speech.set_enabled(False)
