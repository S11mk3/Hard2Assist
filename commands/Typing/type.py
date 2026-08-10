"""Type what you say into the app in front."""

import session
import spoken
from output import detail, say

NAME = "type"
TAKES_ARG = True

# "write" is a plain synonym; the rest are the recogniser's usual guesses at
# the word said mid-sentence.
ALIASES = ("types", "typed", "write", "writes")

PHRASES = ("type out",)

HELP = "type <words> -- type what you say into the app in front"
EXAMPLE = "type hello world"


def run(argument):
    text = spoken.prepare(argument)
    if not text:
        say("There was nothing to type.")
        return

    # Where the keys will land, with our own window moved out of the way if it
    # was in front. Says why itself when there is nowhere sensible to type.
    target = session.keyboard_target()
    if target is None:
        return

    # Typed before the confirmation, so a refusal is never announced as a
    # success. say() only queues speech, so nothing is spoken in between.
    if not spoken.type_out(text):
        say(f"Windows wouldn't let me type into {target}.")
        detail("That window runs as administrator and Hard2Assist does not. "
               "Restart Hard2Assist as administrator to type into it.")
        return

    say(f"Typed into {target}")
