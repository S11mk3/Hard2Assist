"""Where typed keys go: the app last named, else the window in front -- for `type`, `press` and
`dictate`. The desktop is faked, so nothing is really focused or typed."""

import pytest

import output
import session
import spoken
import win
from apps.app import App

NOTEPAD = App("notepad", "notepad", "Notepad")
ITSELF = App("hard2assist", "", kind="itself")
TERMINAL, OURS = 1, 99


@pytest.fixture
def desktop(monkeypatch):
    """Notepad has windows 5 and 6 (6 the newest); a terminal is in front; nothing named yet."""
    state = {"front": TERMINAL, "windows": {"notepad": [5, 6]}, "focused": [], "said": []}

    def focus(hwnd):
        state["focused"].append(hwnd)
        state["front"] = hwnd
        return True

    monkeypatch.setattr(win, "windows_of", lambda app: state["windows"].get(app.name, []))
    monkeypatch.setattr(win, "newest_window_of", lambda app: max(state["windows"].get(app.name, []), default=None))
    monkeypatch.setattr(win, "focus_window", focus)
    monkeypatch.setattr(win, "foreground", lambda: state["front"])
    monkeypatch.setattr(win, "foreground_is_ours", lambda: state["front"] == OURS)
    monkeypatch.setattr(win, "foreground_title",
                        lambda: {TERMINAL: "✳ claude code", OURS: "Hard2Assist"}.get(state["front"], ""))
    monkeypatch.setattr(session, "FOCUS_SETTLE", 0)
    monkeypatch.setattr(session, "_last", None)
    monkeypatch.setattr(output, "_sink", lambda text, tag=None: state["said"].append(text))
    return state


def test_the_app_last_named_is_brought_forward(desktop):
    session.remember(NOTEPAD)
    assert session.keyboard_target() == "notepad"
    assert desktop["focused"] == [6]


def test_a_window_of_it_already_in_front_is_kept(desktop):
    session.remember(NOTEPAD)
    desktop["front"] = 5   # the older notepad, which the user picked
    assert session.keyboard_target() == "notepad"
    assert desktop["focused"] == []


def test_nothing_is_typed_when_the_app_named_is_not_open(desktop):
    session.remember(NOTEPAD)
    desktop["windows"]["notepad"] = []
    assert session.keyboard_target() is None
    assert desktop["said"] == ["notepad isn't open. Say computer open notepad first."]


@pytest.mark.parametrize("named", [None, ITSELF])
def test_with_nothing_named_keys_go_to_the_window_in_front(desktop, named):
    session.remember(named)
    assert session.keyboard_target() == "claude code"   # its symbol is not read aloud
    assert desktop["focused"] == []


def test_never_into_our_own_window(desktop):
    desktop["front"] = OURS
    assert session.keyboard_target() is None
    assert desktop["focused"] == []


class _Ears:
    def __init__(self, *utterances):
        self.utterances = list(utterances)

    def listen_once(self, **_):
        return self.utterances.pop(0) if self.utterances else None


def test_dictation_finds_its_app_again_before_every_line(commands, monkeypatch):
    targets = iter(["notepad", "notepad", None])
    typed = []
    monkeypatch.setattr(session, "keyboard_target", lambda: next(targets))
    monkeypatch.setattr(spoken, "type_out", lambda text: typed.append(text) or True)
    monkeypatch.setattr(output, "_sink", lambda text, tag=None: None)

    lines = commands["dictate"]._listen(_Ears("hello there", "second line", "third line", "more"))

    # The third line found its app gone, so dictation stopped rather than typing it elsewhere.
    assert lines == 2
    assert typed == ["Hello there", " ", "Second line", " "]


@pytest.mark.parametrize("heard, text", [
    ('"hello".', "hello"),
    ("“hello there”", "hello there"),
    ("hello there.", "hello there."),
    ('"a" and "b"', '"a" and "b"'),
])
def test_type_drops_the_recognisers_quotes(commands, heard, text):
    assert commands["type"].unquoted(heard) == text
