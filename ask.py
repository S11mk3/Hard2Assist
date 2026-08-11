"""Asking the user for a file path mid-command.

Used by `open` when it meets a program it does not know. The GUI answers with
a file picker; console mode falls back to a typed prompt. The interface that
is running registers its handler at startup, as in output.py.
"""

import os

_handler = None


def on_request(handler):
    """Register `handler(name) -> path or None`. The GUI sets this at startup."""
    global _handler
    _handler = handler


def for_program(name):
    """Ask where a program is. Returns a path, or None if the user cancelled."""
    if _handler is None:
        return _console_ask(name)
    return _handler(name)


def _console_ask(name):
    """Fallback for --console mode, which has no window to host a dialog."""
    try:
        path = input(f"Where is '{name}'? Paste the full path, "
                     f"or press Enter to skip: ").strip().strip('"')
    except (EOFError, KeyboardInterrupt):
        return None

    return path if path and os.path.isfile(path) else None
