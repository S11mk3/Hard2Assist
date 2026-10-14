"""Turning spoken words into what commands act on: numbers, punctuation, "all", ending dictation."""

import pytest

import session
import settings
import spoken


@pytest.mark.parametrize("words, number", [
    ("50", 50),
    ("fifty", 50),
    ("twenty five", 25),
    ("twenty-five", 25),
    ("seventy 5", 75),
    ("50%", 50),
    ("fifty percent", 50),
    ("max", 100),
    ("half", 50),
    ("a hundred", 100),
    ("loud", None),
    ("", None),
])
def test_volume_numbers(commands, words, number):
    assert commands["volume"].to_number(words) == number


@pytest.mark.parametrize("heard, text", [
    ("hello there comma how are you", "Hello there, how are you"),
    ("is it ready question mark", "Is it ready?"),
    ("first line new line second line", "First line\nsecond line"),
    # Whole words only.
    ("the commas were periodic", "The commas were periodic"),
])
def test_dictated_punctuation(heard, text):
    assert spoken.prepare(heard) == text


@pytest.mark.parametrize("heard, result", [
    ("computer stop dictating", ("", True)),
    ("computer please stop dictating now", ("", True)),
    ("Computer stop typing.", ("", True)),
    # The line said just before the phrase is still typed, punctuation and all...
    ("home at six. Computer, stop", ("home at six.", True)),
    # ...but not a comma left dangling where the phrase came off.
    ("six, computer stop dictating", ("six", True)),
    # Without the wake word it is text to type.
    ("I said stop dictating", ("I said stop dictating", False)),
    ("stop", ("stop", False)),
])
def test_ending_dictation(commands, heard, result):
    assert commands["dictate"]._split_stop(heard) == result


def test_ending_dictation_follows_a_customised_wake_word(commands):
    settings.set("prefix", "jarvis")
    assert commands["dictate"]._split_stop("jarvis stop dictating") == ("", True)
    assert commands["dictate"]._split_stop("computer stop dictating") == ("computer stop dictating", False)


@pytest.mark.parametrize("argument, result", [
    ("all notepad", ("notepad", True)),
    ("All Chrome", ("Chrome", True)),
    ("notepad", ("notepad", False)),
])
def test_all_applies_a_window_command_to_every_window(argument, result):
    assert session.split_all(argument) == result


@pytest.mark.parametrize("word, valid", [
    ("jarvis", True),
    ("Jarvis ", True),
    ("ok", False),
    ("hey you", False),
    ("R2D2", False),
])
def test_wake_word_choices(word, valid):
    assert settings.valid_prefix(word) is valid
