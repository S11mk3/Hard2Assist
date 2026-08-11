"""Start speaking replies again after `quiet`."""

import speech
from output import detail, say

NAME = "speak"
TAKES_ARG = False
ALIASES = ("speech", "talk", "voice")
# Only the phrasings that name no command word at all. "talk again" and "you
# can talk" need no entry -- "talk" is already an alias below, so the word scan
# reaches them.
PHRASES = ("start talking", "start speaking")
HELP = "speak        -- start speaking replies again"

ABOUT = """\
Speak turns my voice back on after "quiet".
"start talking" and "start speaking" work too.
Everything I say is written here either way -- this only decides whether
it is also read out loud.
The voice is the one built into Windows, so it works offline and nothing
you hear ever leaves this PC.\
"""


def run():
    if not speech.available():
        detail("I could not start a voice on this PC.")
        return

    speech.set_enabled(True)
    say("Speaking again")
