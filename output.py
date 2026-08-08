"""Message output for commands.

    say(text)      written to the log AND spoken aloud
    detail(text)   written to the log only

Speaking is the default so that a new command is never accidentally silent.
detail() exists for output that would be tedious to hear: the app list behind
`help`, the per-drive breakdown behind `disk`, or any long explanation.
Commands should speak the short version and write the rest.

Messages go through a replaceable listener rather than print() directly:
the GUI redirects them into its log panel, and the built .exe has no console
at all (sys.stdout is None), where a stray print() would raise.
"""

import speech

_listener = print


def on_message(listener):
    """Redirect all output to `listener(text)`. The GUI calls this at startup."""
    global _listener
    _listener = listener


def say(text):
    """Write the message and speak it aloud."""
    _listener(text)
    speech.speak(text)


def detail(text):
    """Write the message only. For lists and long explanations."""
    _listener(text)
