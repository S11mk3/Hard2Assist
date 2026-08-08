"""Shut Hard2Assist down."""

import registry
from output import say

NAME = "stop"
TAKES_ARG = False
ALIASES = ("stopp", "quit", "exit", "shut down yourself", "goodbye")
HELP = "stop         -- quit Hard2Assist"


def run():
    say("Goodbye")
    # Return the sentinel so the caller can shut down cleanly and release
    # the microphone. Calling exit() here would skip that teardown.
    return registry.STOP
