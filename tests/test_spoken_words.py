"""Turning spoken words into what commands act on: numbers, punctuation, keys, sites, "all",
ending dictation."""

import pytest

import output
import session
import settings
import spoken
import win


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
    ("first line new line second line", "First line\nSecond line"),
    ("it is ready period see you soon exclamation mark", "It is ready. See you soon!"),
    # Whole words only.
    ("the commas were periodic", "The commas were periodic"),
    # The offline recogniser adds punctuation of its own around a spoken mark.
    ("Hello there, comma, how are you? Question mark.", "Hello there, how are you?"),
    ("Hello there comma, how are you question mark?", "Hello there, how are you?"),
    ("First line. New line. Second line.", "First line.\nSecond line."),
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


@pytest.mark.parametrize("spoken_keys, keys", [
    ("enter", (win.VK_RETURN,)),
    ("enter key", (win.VK_RETURN,)),
    ("save", (win.VK_CONTROL, ord("S"))),
    ("control shift t", (win.VK_CONTROL, 0x10, ord("T"))),
    ("ctrl+shift+t", (win.VK_CONTROL, 0x10, ord("T"))),
    ("alt f4", (0x12, 0x73)),
    ("f 5", (0x74,)),
    ("page down", (0x22,)),
    ("windows", (win.VK_LWIN,)),
    ("banana", None),
    ("control banana", None),
    ("", None),
])
def test_press_keys(commands, spoken_keys, keys):
    assert commands["press"].keys_for(spoken_keys) == keys


@pytest.mark.parametrize("argument, site, query", [
    ("how to cook rice", None, "how to cook rice"),
    ("for cats", None, "cats"),
    ("YouTube for cats.", "youtube", "cats"),
    ("youtube lofi music", "youtube", "lofi music"),
    ("for cats on wikipedia", "wikipedia", "cats"),
    ("google maps for coffee near me", "google maps", "coffee near me"),
])
def test_search_names_a_site(commands, argument, site, query):
    _, found_query, found_site = commands["search"].where(argument)
    assert (found_site, found_query) == (site, query)


@pytest.mark.parametrize("count, noun, text", [
    (1, "window", "1 window"),
    (2, "notepad window", "2 notepad windows"),
    (3, "process", "3 processes"),
    (0, "line", "0 lines"),
])
def test_plurals(count, noun, text):
    assert output.plural(count, noun) == text


@pytest.mark.parametrize("word, valid", [
    ("jarvis", True),
    ("Jarvis ", True),
    ("ok", False),
    ("hey you", False),
    ("R2D2", False),
])
def test_wake_word_choices(word, valid):
    assert settings.valid_prefix(word) is valid
