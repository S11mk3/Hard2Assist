"""Settings the user chooses out loud, saved between runs.

Kept beside the app catalogue in %APPDATA%\\Hard2Assist. Every value has a
default that keeps Hard2Assist working, so a missing, unreadable or
hand-edited file degrades to sensible behaviour instead of stopping the app.

Whether the file exists is also how first run is detected: no file means the
user has never been through the setup conversation (wizard.py).
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

# Values a setting is allowed to take. `prefix` is free text, checked by
# valid_prefix() instead.
CHOICES = {
    "listen_when": ("always", "focused"),
}

_values = None


def valid_prefix(word):
    """Whether a word can serve as the wake word.

    Letters only and at least three of them: recognition returns short
    fragments constantly, and a one or two letter wake word would fire on
    half of what it hears.
    """
    return bool(re.fullmatch(r"[a-z]{3,}", str(word).strip().lower()))


def _acceptable(key, value):
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
        # Anything unrecognised or out of range is ignored rather than
        # rejected wholesale, so one bad line cannot lose the other settings.
        for key, value in saved.items():
            if key in DEFAULTS and _acceptable(key, value):
                _values[key] = value

    return _values


def get(key):
    return load()[key]


def set(key, value):
    """Change one setting and write the file."""
    values = load()
    values[key] = value
    save()


def save():
    """Write the settings file, creating the folder if needed."""
    os.makedirs(USER_DIR, exist_ok=True)
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(load(), f, indent=2)


def is_first_run():
    """True when the user has never completed the setup conversation."""
    return not os.path.isfile(FILE)
