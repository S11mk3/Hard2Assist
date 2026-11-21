"""Start speaking replies again after `quiet`, or speak faster or slower."""

import settings
import speech
from output import say, warn

NAME = "speak"
TAKES_ARG = True
ARG_OPTIONAL = True
SYNONYMS = ("speech", "talk", "voice")
PHRASES = ("start talking", "start speaking")
HELP = "speak -- start speaking replies again ('speak faster', 'speak slower')"

ABOUT = """\
Speak turns my voice back on after "quiet".
"start talking" and "start speaking" work too.
"speak faster" and "talk slower" change how fast I talk, and the speed is
kept for next time.
Everything I say is written here either way -- this only decides whether
it is also read out loud.
The voice is the one built into Windows, so it works offline and nothing
you hear ever leaves this PC.\
"""

STEP = 2   # of SAPI's -10..10 rate scale


def run(argument=""):
    if not speech.available():
        warn("I could not start a voice on this PC.")
        return
    speech.set_enabled(True)

    words = set(argument.lower().split())
    change = STEP if words & {"faster", "quicker"} else -STEP if words & {"slower"} else 0
    if not change:
        say("Speaking again")
        return

    current = settings.get("voice_rate")
    rate = max(-10, min(10, current + change))
    if rate == current:
        say("That's as fast as I go." if change > 0 else "That's as slow as I go.")
        return
    settings.set("voice_rate", rate)
    say("Speaking faster" if change > 0 else "Speaking slower")
