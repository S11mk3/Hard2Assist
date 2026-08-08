"""Asking the user a question mid-command.

Currently used for one thing: when `open` meets a program it does not know,
it needs the program's location, and a file path cannot be dictated into a
voice-only interface. The GUI answers by opening a file picker; console mode
falls back to a typed prompt.

Follows the same pattern as output.py: whichever interface is running
registers a handler at startup.
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
    """Fallback for --console mode, where there is no window to host a dialog."""
    try:
        path = input(f"Where is '{name}'? Paste the full path, "
                     f"or press Enter to skip: ").strip().strip('"')
    except (EOFError, KeyboardInterrupt):
        return None

    return path if path and os.path.isfile(path) else None
