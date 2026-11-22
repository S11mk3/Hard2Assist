"""The settings the user chooses, saved as JSON in %APPDATA%\\Hard2Assist\\settings.json.

Every value has a default and is checked on load, so a missing, broken or hand-edited file still
gives working behaviour. Whether the file exists is how first run is detected.
"""

import os
import re

import storage

FILE = os.path.join(storage.USER_DIR, "settings.json")

DEFAULTS = {
    "prefix": "computer",         # the wake word
    "voice": "kokoro_am_fenrir",  # a Kokoro voice; see models.voices()
    "speed": 1.0,                 # how fast the voice talks, from SPEED[0] to SPEED[1]
    "microphone": "",             # an input device's name; "" for the Windows default
    "sounds": True,               # a chime on hearing a command, another when something fails
}

SPEED = (0.7, 1.5)

_values = None


def valid_prefix(word):
    """Letters only, three or more: a shorter wake word fires on fragments of everything heard."""
    return bool(re.fullmatch(r"[a-z]{3,}", str(word).strip().lower()))


def _clean(key, value):
    """The value as it should be stored, or None if this setting cannot take it."""
    if key == "prefix":
        return value.strip().lower() if isinstance(value, str) and valid_prefix(value) else None
    if key == "speed":
        return round(max(SPEED[0], min(SPEED[1], value)), 2) if type(value) in (int, float) else None
    if key == "voice":
        return value.strip() if isinstance(value, str) and value.startswith("kokoro_") else None
    if key == "sounds":
        return value if isinstance(value, bool) else None
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
