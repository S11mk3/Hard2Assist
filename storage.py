"""Where Hard2Assist keeps things: its own files, the user's folder, and the JSON saved there."""

import contextlib
import json
import os
import sys
import tempfile

FROZEN = getattr(sys, "frozen", False)

# The app's own files: PyInstaller's _internal folder when built, the source tree otherwise.
BUNDLE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))

# The folder holding Hard2Assist.exe; the source tree when run from source.
EXE_DIR = os.path.dirname(sys.executable) if FROZEN else BUNDLE_DIR

# Settings, saved apps, added commands and the log: small, and they follow a roaming profile.
USER_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "Hard2Assist")

# The speech models: hundreds of megabytes, so kept on this PC only.
LOCAL_DIR = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "Hard2Assist")


def read_json(path):
    """The dict saved at path, or {} if it is missing, unreadable or not a dict."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_json(path, data):
    """Save data at path. Returns None, or the OSError that stopped it.

    Written to a temporary file and swapped in, so a crash mid-write cannot leave half a file.
    """
    folder = os.path.dirname(path)
    try:
        os.makedirs(folder, exist_ok=True)
        handle, temporary = tempfile.mkstemp(dir=folder, suffix=".tmp")
    except OSError as e:
        return e

    try:
        with os.fdopen(handle, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(temporary, path)
    except OSError as e:
        with contextlib.suppress(OSError):
            os.remove(temporary)
        return e
    return None
