"""Shared test setup.

The tests run the real command modules, loaded from commands/ the way the app
loads them, but never touch the microphone, the voice or the user's own
settings file.
"""

import pytest

import registry
import settings


@pytest.fixture(autouse=True)
def default_settings(tmp_path, monkeypatch):
    """Every setting at its default, saved to a throwaway folder.

    Without this a test would read %APPDATA%\\Hard2Assist\\settings.json, and
    a wake word customised on this PC would change what the tests hear.
    """
    monkeypatch.setattr(settings, "USER_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "FILE", str(tmp_path / "settings.json"))
    monkeypatch.setattr(settings, "_values", None)


@pytest.fixture(scope="session")
def commands():
    """Every command, {name: module}, as registry.load() finds them on disk."""
    return registry.load()
