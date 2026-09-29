"""Shut Hard2Assist down."""

import registry
import speech
import win
from output import say

NAME = "stop"
TAKES_ARG = False
ALIASES = ("stopp", "quit", "exit", "goodbye")
PHRASES = ("shut down", "shut yourself down", "close yourself",
           "see you later", "that will be all")
HELP = "stop         -- quit Hard2Assist"

ABOUT = """\
Stop quits Hard2Assist.
"quit", "exit", "goodbye", "shut down" and "see you later" all work.
The microphone is released on the way out, so nothing is left listening.
To silence me without quitting, say "quiet" instead.\
"""


def run():
    # Validated the same way the launch greeting is, so an account called
    # "marko-kg102" hears a plain goodbye rather than its login string.
    name = win.friendly_username()
    say(f"Goodbye {name}" if name else "Goodbye")

    # say() only queues, and the speech thread is a daemon, so returning
    # straight away would tear the interpreter down before SAPI played a word.
    speech.wait()

    # The sentinel lets the caller shut down cleanly and release the
    # microphone. Calling exit() here would skip that teardown.
    return registry.STOP
