"""Asking you something mid-command.

Only used for one thing so far: when `open` meets a program it has never heard
of, it needs to know where that program lives. You cannot dictate
"C:\\Program Files\\..." into a voice-only window, so the window opens a file
picker instead and you click the program once.

Works like output.py -- whoever is running the interface registers a handler.
"""

import os

_handler = None


def on_request(handler):
    """handler(name) -> path or None. The window sets this at startup."""
    global _handler
    _handler = handler


def for_program(name):
    """Ask where a program is. Returns a path, or None if you cancelled."""
    if _handler is None:
        return _console_ask(name)
    return _handler(name)


def _console_ask(name):
    """Fallback for --console mode, where there is no window to put a dialog in."""
    try:
        path = input(f"Where is '{name}'? Paste the full path, "
                     f"or press Enter to skip: ").strip().strip('"')
    except (EOFError, KeyboardInterrupt):
        return None

    return path if path and os.path.isfile(path) else None
