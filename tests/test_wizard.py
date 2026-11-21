"""Understanding answers in the spoken setup: yes or no, and which word to wake on."""

import pytest

import wizard


@pytest.mark.parametrize("answer, verdict", [
    ("yes", True),
    ("yes please", True),
    ("that's right", True),
    ("sure why not", True),
    # "know" stands in for a misheard "no", but a yes said first still wins.
    ("yes i know", True),
    ("no", False),
    ("nope", False),
    ("know", False),
    # A yes-word inside a no is still a no.
    ("no that's not right", False),
    ("that's not right", False),
    ("no not correct", False),
    ("i don't think that's right", False),
    ("banana", None),
])
def test_yes_or_no(answer, verdict):
    assert wizard._yes_or_no(answer) is verdict


@pytest.mark.parametrize("answer, word", [
    ("jarvis", "jarvis"),
    ("use jarvis", "jarvis"),
    ("let's use jarvis please", "jarvis"),
    ("my wake word is friday", "friday"),
    # Commands, and what the conversation itself listens for, cannot be the wake word.
    ("open", None),
    ("stop", None),
    ("keep", None),
    ("yes", None),
    ("the", None),
    ("ok", None),
])
def test_wake_word_in_an_answer(commands, answer, word):
    assert wizard.wake_word_in(answer) == word


@pytest.mark.parametrize("answer, when", [
    ("always", "always"),
    ("all the time", "always"),
    ("focus", "focused"),
    ("only when in focus", "focused"),
    # Both kinds of word: the focus one is what was meant.
    ("only when ah not always", "focused"),
    ("not always", "focused"),
    ("always even when the window is minimised", "always"),
    ("banana", None),
])
def test_when_to_listen(answer, when):
    assert wizard.listen_when_in(answer) == when


class _Ears:
    def __init__(self, *answers):
        self.answers = list(answers)

    def listen_once(self):
        return self.answers.pop(0) if self.answers else None


def test_confirm_asks_again_when_not_understood(monkeypatch):
    monkeypatch.setattr(wizard, "_speak", lambda text: None)
    assert wizard.confirm(_Ears("banana", "No, that's not right."), "Should I?") is False
    assert wizard.confirm(_Ears(None, None, None), "Should I?") is None
