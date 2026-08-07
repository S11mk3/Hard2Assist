"""Shut Hard2Assist down."""

import registry
from output import say

NAME = "stop"
TAKES_ARG = False
ALIASES = ("stopp", "quit", "exit", "shut down yourself", "goodbye")
HELP = "stop         -- quit Hard2Assist"


def run():
    say("Goodbye")
    # Hand the sentinel back so whoever is running commands can shut down
    # tidily and release the microphone on the way out. Calling exit() here
    # would kill the program from the inside and skip that.
    return registry.STOP
