"""Message output for commands.

    say(text)      written to the log AND spoken aloud
    detail(text)   written to the log only

Messages go to a replaceable listener rather than to print(): the GUI points
it at its log panel, and the built .exe has no console at all.
"""

import sys

import speech


def _write(text):
    """The default sink: the terminal, used in --console mode."""
    try:
        print(text)
    except UnicodeEncodeError:
        # Window titles and Start Menu names contain characters no console
        # codepage can represent. Substitute rather than let one glyph raise.
        encoding = getattr(sys.stdout, "encoding", None) or "ascii"
        print(text.encode(encoding, "replace").decode(encoding, "replace"))


_listener = _write


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
