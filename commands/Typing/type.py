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

ABOUT = """\
Type sends whatever you say next to the window in front.
Recognition gives me plain lowercase words with no punctuation, so a few
marks are spoken: say "comma", "period", "question mark" and "new line"
where you want them. "{prefix} type hello there comma how are you
question mark" types "Hello there, how are you?".
If my own window is in front, I switch to the app you last named first,
so "type" follows "open" the way the two sound when you say them.
For more than a sentence or two, say "dictate" instead and just talk.\
"""


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
