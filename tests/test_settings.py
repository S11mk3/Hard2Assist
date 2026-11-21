"""Saved settings and apps: what is accepted from the files, and how they are written."""

import json

import apps
import settings
from apps import installed
from apps.app import App


def _saved(values):
    with open(settings.FILE, "w", encoding="utf-8") as f:
        json.dump(values, f)
    settings._values = None


def test_a_hand_edited_wake_word_is_cleaned_up():
    _saved({"prefix": "  Jarvis "})
    assert settings.get("prefix") == "jarvis"


def test_bad_values_fall_back_to_defaults_one_at_a_time():
    _saved({"prefix": "ok", "listen_when": "sometimes", "recognizer": "google",
            "voice_rate": 99, "hotkey": 5, "unknown": 1})
    assert settings.get("prefix") == "computer"
    assert settings.get("listen_when") == "always"
    assert settings.get("recognizer") == "google"
    assert settings.get("voice_rate") == 10
    assert settings.get("hotkey") == "ctrl+alt+space"


def test_a_broken_file_gives_the_defaults():
    with open(settings.FILE, "w", encoding="utf-8") as f:
        f.write("{not json")
    assert settings.load() == settings.DEFAULTS


def test_saving_writes_the_file_whole(tmp_path):
    settings.set("prefix", "jarvis")
    with open(settings.FILE, encoding="utf-8") as f:
        assert json.load(f)["prefix"] == "jarvis"
    assert not list(tmp_path.glob("*.tmp"))


def test_remembered_apps_survive_a_restart():
    installed.remember("Music Player", r"C:\Tools\player.exe")
    installed._entries = None
    assert [(app.name, app.process, app.kind) for app in installed.mine()] == [
        ("music player", "player.exe", "mine")]
    assert installed.forget("music player")
    assert not installed.forget("music player")


CATALOGUE = [
    App("hard2assist", "", kind="itself"),
    App("notepad", "notepad"),
    App("calculator", "calc", aliases=("calc",)),
    App("obs studio", "obs.lnk", kind="installed"),
    App("ccleaner 7", "cc.lnk", kind="installed"),
    App("notepad", "other.lnk", kind="installed"),   # the Start Menu's copy of a system app
    App("twitch", "https://www.twitch.tv", kind="web"),
]


def _with_catalogue(monkeypatch):
    monkeypatch.setattr(apps, "all_apps", lambda: CATALOGUE)


def test_finding_apps(monkeypatch):
    _with_catalogue(monkeypatch)
    assert apps.find("notepad").launch == "notepad"   # the first source wins
    assert apps.find("calc").name == "calculator"
    assert apps.find("ccleaner").name == "ccleaner 7"
    assert apps.find("obs").name == "obs studio"
    assert apps.find("studio").name == "obs studio"
    assert apps.find("twitc").name == "twitch"


def test_a_letter_or_two_finds_nothing(monkeypatch):
    _with_catalogue(monkeypatch)
    for spoken in ("t", "c", "no", "ob"):
        assert apps.find(spoken) is None


def test_counts_agree_with_the_list(monkeypatch):
    _with_catalogue(monkeypatch)
    listed = sum(len(names) for _, names in apps.names_by_kind())
    assert sum(apps.counts().values()) == listed == 5
