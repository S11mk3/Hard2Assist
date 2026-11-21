"""Shut Hard2Assist down."""

import registry
import speech
import win
from output import say

NAME = "stop"
TAKES_ARG = False
EXACT_ONLY = True
ALIASES = ("stopp",)
SYNONYMS = ("quit", "exit", "goodbye")
PHRASES = ("shut down", "shut yourself down", "close yourself", "see you later", "that will be all")
HELP = "stop -- quit Hard2Assist"

ABOUT = """\
Stop quits Hard2Assist.
"quit", "exit", "goodbye", "shut down" and "see you later" all work.
The microphone is released on the way out, so nothing is left listening.
To silence me without quitting, say "quiet" instead.\
"""


def run():
    name = win.friendly_username()
    say(f"Goodbye {name}" if name else "Goodbye")
    speech.wait()   # the speech thread dies with the app, so let it finish first
    return registry.STOP   # the caller shuts down cleanly, releasing the microphone
