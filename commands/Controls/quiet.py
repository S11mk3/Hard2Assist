"""Stop Hard2Assist speaking its replies."""

import speech
from output import detail, say

NAME = "quiet"
TAKES_ARG = False
ALIASES = ("silent", "shush")

# Only phrasings the word scan cannot reach. "stop talking" opens with the
# name of the `stop` command, so without an entry here the app would quit
# instead of going silent. "be quiet" needs none: it contains this command's
# own name, so the word scan already finds it.
PHRASES = ("stop talking", "stop speaking", "shut up", "stop the voice")
HELP = "quiet        -- stop speaking replies ('speak' turns it back on)"

ABOUT = """\
Quiet stops me reading my replies out loud. I keep listening, and I keep
writing everything here.
"stop talking", "shut up" and "be quiet" all work.
Say "speak" to turn the voice back on.\
"""


def run():
    if not speech.available():
        detail("I have no voice on this PC anyway.")
        return

    # Confirm before disabling speech, or the confirmation itself would
    # never be heard.
    say("Going quiet")
    speech.set_enabled(False)
