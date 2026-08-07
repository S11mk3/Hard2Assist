"""Where messages go.

Commands call say() instead of print(). In the terminal that is print; when the
window is running it appends to the log there instead.

This matters more than it looks: the built .exe has no console at all, so
sys.stdout is None and a stray print() would raise.
"""

_listener = print


def on_message(listener):
    """Send messages somewhere else. The window calls this at startup."""
    global _listener
    _listener = listener


def say(text):
    _listener(text)
