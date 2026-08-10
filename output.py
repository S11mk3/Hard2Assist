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

import sys

import speech


def _write(text):
    """The default sink: the terminal, in --console mode.

    Guarded because window titles and Start Menu names contain characters no
    console codepage can represent -- a braille pattern, an emoji, a CJK
    name. Printing one raises UnicodeEncodeError, which would take the whole
    command down for the sake of a single glyph. The GUI's log panel has no
    such limit, so only the terminal pays for this.
    """
    try:
        print(text)
    except UnicodeEncodeError:
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
