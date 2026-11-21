"""Shared test setup.

The tests run the real command modules, loaded from commands/ the way the app loads them, but
never touch the microphone, the voice, or the user's own settings and saved apps.
"""

import pytest

import registry
import settings
from apps import installed


@pytest.fixture(autouse=True)
def isolated_files(tmp_path, monkeypatch):
    """Settings at their defaults and saved apps empty, both kept in a throwaway folder."""
    monkeypatch.setattr(settings, "FILE", str(tmp_path / "settings.json"))
    monkeypatch.setattr(settings, "_values", None)
    monkeypatch.setattr(installed, "USER_FILE", str(tmp_path / "my-apps.json"))
    monkeypatch.setattr(installed, "_entries", None)


@pytest.fixture(scope="session")
def commands():
    """Every command, {name: module}, as registry.load() finds them on disk."""
    return registry.load()
