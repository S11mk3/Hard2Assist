"""The dock, drawn offscreen: what each state looks like in size, and how it reacts."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

import models  # noqa: E402
import settings  # noqa: E402
import speech  # noqa: E402


@pytest.fixture(scope="module")
def qt():
    models.load_library()   # the settings page lists the voices
    return QApplication.instance() or QApplication([])


@pytest.fixture
def dock(qt, monkeypatch):
    import dock as module
    monkeypatch.setattr(module.win, "set_no_activate", lambda hwnd, on: None)
    monkeypatch.setattr(speech, "talking", lambda: False)
    monkeypatch.setattr(speech, "enabled", lambda: True)
    it = module.Dock()
    it.morph.setDuration(0)
    yield it
    it.close()


def settle(dock):
    """Let the size animation finish."""
    dock.morph.setCurrentTime(dock.morph.duration())
    dock._resize(dock.morph.endValue() or dock._target())
    QApplication.processEvents()


def test_it_rests_as_a_small_pill_and_grows_with_what_it_shows(dock):
    import dock as module
    dock._set("idle", "")
    settle(dock)
    assert dock.size_now == module.IDLE

    dock.on_partial("Computer, open Notepad and type a long sentence")
    settle(dock)
    assert dock.mode == "hearing"
    assert dock.size_now.width() > module.IDLE.width()
    assert dock.size_now.height() == module.ACTIVE_HEIGHT


def test_a_command_then_its_reply(dock):
    dock.on_message("> what time is it", None)
    assert (dock.mode, dock.text) == ("working", "what time is it")
    dock.on_message("It's 1:40 am", "say")
    assert (dock.mode, dock.text) == ("speaking", "It's 1:40 am")
    dock.on_status("Listening", False)
    assert dock.linger.isActive()   # the reply stays up a moment, then the pill rests


def test_it_opens_into_the_panel_and_closes_again(dock):
    import dock as module
    dock.expand()
    settle(dock)
    dock._morphed()
    assert dock.size_now == module.OPEN and not dock.panel.isHidden()
    dock.collapse()
    settle(dock)
    assert dock.panel.isHidden() and dock.size_now != module.OPEN


def test_the_conversation_groups_details_into_one_block(dock):
    panel = dock.panel
    before = panel._list.count()
    panel.add("> help", None)
    panel.add("I know 27 commands.", "say")
    panel.add("COMMANDS", None)
    panel.add("  battery -- how much charge is left", None)
    assert panel._list.count() == before + 3


@pytest.mark.parametrize("word, accepted", [("jarvis", True), ("ok", False), ("open", False), ("r2d2", False)])
def test_the_wake_word_is_checked_before_it_is_saved(dock, word, accepted):
    dock.panel._wake.setText(word)
    dock.panel._save_wake_word()
    assert (settings.get("prefix") == word) is accepted


def test_it_hides_while_something_is_fullscreen(dock, monkeypatch):
    import dock as module
    dock.show()
    monkeypatch.setattr(module.win, "fullscreen_in_front", lambda: True)
    dock._watch_fullscreen()
    assert not dock.isVisible()
    monkeypatch.setattr(module.win, "fullscreen_in_front", lambda: False)
    dock._watch_fullscreen()
    assert dock.isVisible()
