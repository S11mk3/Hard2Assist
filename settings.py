"""The settings the user chooses out loud, saved between runs.

Stored as JSON in %APPDATA%\\Hard2Assist. Every value has a default, so a
missing or unreadable file degrades to working behaviour instead of stopping
the app. Whether the file exists is also how first run is detected.
"""

import json
import os
import re

USER_DIR = os.path.join(os.environ.get("APPDATA", ""), "Hard2Assist")
FILE = os.path.join(USER_DIR, "settings.json")

DEFAULTS = {
    "prefix": "computer",       # the wake word
    "listen_when": "always",    # "always" | "focused"
}

# The values each setting may take. `prefix` is free text, checked by
# valid_prefix() instead.
CHOICES = {
    "listen_when": ("always", "focused"),
}

_values = None


def valid_prefix(word):
    """Whether a word can serve as the wake word: letters only, three or more.

    Recognition returns short fragments constantly, and a one or two letter
    wake word would fire on half of what it hears.
    """
    return bool(re.fullmatch(r"[a-z]{3,}", str(word).strip().lower()))


def _acceptable(key, value):
    """Whether a value read from the file is one this setting allows."""
    if key == "prefix":
        return valid_prefix(value)
    return value in CHOICES.get(key, ())


def load():
    """Every setting, defaults filled in. Read once, then cached."""
    global _values
    if _values is not None:
        return _values

    _values = dict(DEFAULTS)

    try:
        with open(FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
    except (OSError, ValueError):
        saved = {}

    if isinstance(saved, dict):
        # Unrecognised or out-of-range entries are ignored one at a time, so
        # one bad line cannot lose the other settings.
        for key, value in saved.items():
            if key in DEFAULTS and _acceptable(key, value):
                _values[key] = value

    return _values


def get(key):
    """One setting's value."""
    return load()[key]


def set(key, value):
    """Change one setting and write the file."""
    values = load()
    values[key] = value
    save()


def save():
    """Write the settings file, creating the folder if needed.

    A failed write is reported rather than raised: it used to escape all the
    way out of the microphone loop, which then announced "the microphone
    stopped working" and went deaf over a full disk. True when it stuck.
    """
    try:
        os.makedirs(USER_DIR, exist_ok=True)
        with open(FILE, "w", encoding="utf-8") as f:
            json.dump(load(), f, indent=2)
        return True
    except OSError as e:
        # Imported here rather than at the top: output's chain of imports
        # must stay free to import settings.
        from output import detail, say
        say("I could not save your settings, so they will only last until "
            "I'm closed.")
        detail(f"({e})")
        return False


def is_first_run():
    """True when the user has never completed the setup conversation."""
    return not os.path.isfile(FILE)
