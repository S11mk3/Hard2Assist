"""Shut Hard2Assist down."""

import registry
import speech
from output import say

NAME = "stop"
TAKES_ARG = False
ALIASES = ("stopp", "quit", "exit", "goodbye")
HELP = "stop         -- quit Hard2Assist"


def run():
    say("Goodbye")

    # say() only queues, and the speech thread is a daemon -- so returning
    # straight away tore the interpreter down before SAPI had played a word
    # and the goodbye was never actually heard. Wait for it to finish.
    speech.wait()

    # Return the sentinel so the caller can shut down cleanly and release
    # the microphone. Calling exit() here would skip that teardown.
    return registry.STOP
