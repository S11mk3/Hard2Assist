"""Shut Hard2Assist down."""

import registry
import speech
import os
from output import say

NAME = "stop"
TAKES_ARG = False
ALIASES = ("stopp", "quit", "exit", "goodbye")
PHRASES = ("shut down", "shut yourself down", "close yourself",
           "see you later", "that will be all", "stuff")
HELP = "stop         -- quit Hard2Assist"

name = os.environ.get("USERNAME", "").strip()

def run():
    say(f"Goodbye {name}")

    # say() only queues, and the speech thread is a daemon -- so returning
    # straight away tore the interpreter down before SAPI had played a word
    # and the goodbye was never actually heard. Wait for it to finish.
    speech.wait()

    # Return the sentinel so the caller can shut down cleanly and release
    # the microphone. Calling exit() here would skip that teardown.
    return registry.STOP
