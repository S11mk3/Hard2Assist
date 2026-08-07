"""Where messages go.

Commands call say() to write to the log, or announce() when it is worth saying
out loud as well. Keep announce() for short confirmations -- `help` prints
twenty-six app names, and nobody wants to hear them read out.

This matters more than it looks: the built .exe has no console at all, so
sys.stdout is None and a stray print() would raise.
"""

import speech

_listener = print


def on_message(listener):
    """Send messages somewhere else. The window calls this at startup."""
    global _listener
    _listener = listener


def say(text):
    """Write to the log."""
    _listener(text)


def announce(text):
    """Write to the log and say it out loud."""
    _listener(text)
    speech.speak(text)
