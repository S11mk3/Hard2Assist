"""Asking the user for a program's file mid-command, for `open` and `remember`.

The window registers a file picker; --console falls back to a typed prompt.
"""

import os

_handler = None


def on_request(handler):
    """Register handler(name) -> path or None."""
    global _handler
    _handler = handler


def for_program(name):
    """Where a program is, or None if the user cancelled."""
    return _console_ask(name) if _handler is None else _handler(name)


def _console_ask(name):
    try:
        path = input(f"Where is '{name}'? Paste the full path, or press Enter to skip: ").strip().strip('"')
    except (EOFError, KeyboardInterrupt):
        return None
    return path if path and os.path.isfile(path) else None
