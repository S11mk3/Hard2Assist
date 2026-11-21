"""Type what you say into the app you last named."""

import re

import session
import spoken
from output import say

NAME = "type"
TAKES_ARG = True
VERBATIM = True   # "type the quick brown fox" keeps its "the"
ALIASES = ("types", "typed")
SYNONYMS = ("write", "writes")
PHRASES = ("type out",)
HELP = "type <words> -- type what you say into the app you last named"
EXAMPLE = "type hello world"

ABOUT = """\
Type types whatever you say next into the app you last named, bringing it
to the front if you have clicked into another window since -- so "type"
follows "open" the way the two sound when you say them. If you haven't
named an app yet, it types into the window in front.
Punctuation can be said out loud where you want it: "comma", "period",
"question mark" and "new line". "{prefix} type hello there comma how are
you question mark" types "Hello there, how are you?".
For more than a sentence or two, say "dictate" instead and just talk.\
"""

# The recogniser quotes words it hears as quoted: 'type "hello".'. One quoted span, and nothing
# but sentence punctuation after it, is the text to type.
_QUOTED = re.compile(r'\s*["“]([^"“”]*)["”][.!?]?\s*')


def unquoted(text):
    match = _QUOTED.fullmatch(text)
    return match.group(1) if match else text


def run(argument):
    text = spoken.prepare(unquoted(argument))
    if not text:
        say("There was nothing to type.")
        return

    target = session.keyboard_target()
    if target is None:
        return

    # Typed before confirming, so a refusal is never announced as a success.
    if not spoken.type_out(text):
        session.refused(f"type into {target}")
        return
    say(f"Typed into {target}")
