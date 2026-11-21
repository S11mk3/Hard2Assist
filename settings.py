"""The settings the user chooses, saved as JSON in %APPDATA%\\Hard2Assist\\settings.json.

Every value has a default and is checked on load, so a missing, broken or hand-edited file still
gives working behaviour. Whether the file exists is how first run is detected.
"""

import os
import re

import storage

FILE = os.path.join(storage.USER_DIR, "settings.json")

DEFAULTS = {
    "prefix": "computer",        # the wake word
    "listen_when": "always",     # "always" | "focused"
    "recognizer": "auto",        # "auto" | "local" | "google"; see recognizer.py
    "voice": "",                 # part of a Windows voice's name; "" for the default voice
    "voice_rate": 0,             # -10 (slowest) to 10 (fastest)
    "hotkey": "ctrl+alt+space",  # push-to-talk; "" turns it off
}

CHOICES = {
    "listen_when": ("always", "focused"),
    "recognizer": ("auto", "local", "google"),
}

_values = None


def valid_prefix(word):
    """Letters only, three or more: a shorter wake word fires on fragments of everything heard."""
    return bool(re.fullmatch(r"[a-z]{3,}", str(word).strip().lower()))


def _clean(key, value):
    """The value as it should be stored, or None if this setting cannot take it."""
    if key == "prefix":
        return value.strip().lower() if isinstance(value, str) and valid_prefix(value) else None
    if key in CHOICES:
        return value if value in CHOICES[key] else None
    if key == "voice_rate":
        return max(-10, min(10, value)) if type(value) is int else None
    return value.strip() if isinstance(value, str) else None


def load():
    """Every setting, defaults filled in. Read once, then cached."""
    global _values
    if _values is None:
        _values = dict(DEFAULTS)
        for key, value in storage.read_json(FILE).items():
            cleaned = _clean(key, value) if key in DEFAULTS else None
            if cleaned is not None:
                _values[key] = cleaned
    return _values


def get(key):
    return load()[key]


def set(key, value):
    load()[key] = value
    save()


def save():
    """Write the file. A failure is reported rather than raised; the setting holds until exit."""
    error = storage.write_json(FILE, load())
    if error is None:
        return True

    from output import detail, warn  # output imports speech, which imports this module
    warn("I could not save your settings, so they will only last until I'm closed.")
    detail(f"({error})")
    return False


def is_first_run():
    return not os.path.isfile(FILE)
