"""Stop Hard2Assist speaking its replies."""

import speech
from output import detail, say

NAME = "quiet"
TAKES_ARG = False
SYNONYMS = ("silent", "shush")
# "stop talking" opens with `stop`'s name, so without this phrase it would quit the app.
PHRASES = ("stop talking", "stop speaking", "shut up", "stop the voice")
HELP = "quiet -- stop speaking replies ('speak' turns it back on)"

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
    say("Going quiet")   # before turning it off, or this would never be heard
    speech.set_enabled(False)
