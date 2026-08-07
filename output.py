"""Where messages go.

    say(text)      written to the log AND spoken
    detail(text)   written only

Speaking is the default on purpose. A voice assistant that stays quiet is
broken, and if speaking were the thing you had to remember to ask for, every
new command would start out silent.

detail() is for the parts that would be tedious to listen to: the list of
twenty-six apps behind `help`, the per-drive breakdown behind `disk`, the
second paragraph of an explanation. Say the short version, write the rest.

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
    """Write it and say it out loud."""
    _listener(text)
    speech.speak(text)


def detail(text):
    """Write it only. For lists and long explanations."""
    _listener(text)
