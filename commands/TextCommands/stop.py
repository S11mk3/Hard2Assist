"""Shut Hard2Assist down."""

import registry

NAME = "stop"
TAKES_ARG = False
HELP = "stop         -- quit Hard2Assist"


def run():
    print("Stopping...")
    # Hand the sentinel back so the main loop can break out and release the
    # microphone on its way. Calling exit() here would kill the program from
    # the inside and skip that.
    return registry.STOP
