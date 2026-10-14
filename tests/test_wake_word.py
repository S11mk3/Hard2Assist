"""Finding the wake word and the command after it: listener.find_command()."""

import pytest

import listener
import registry

PREFIX = "computer"


@pytest.fixture
def opens_with_command(commands):
    return lambda text: registry.opens_with_command(commands, text)


@pytest.mark.parametrize("heard, command", [
    ("computer open notepad", "open notepad"),
    ("COMPUTER time", "time"),
    # Case and punctuation stay, so `type` can type the text as heard.
    ("Computer, type Hello there.", "type Hello there."),
])
def test_the_exact_wake_word_always_counts(heard, command):
    assert listener.find_command(heard, PREFIX) == (command, None)


@pytest.mark.parametrize("heard", [
    "I bought a computer yesterday",
    "computers are slow",
    "computertime",
])
def test_conversation_does_not_trigger_commands(heard, opens_with_command):
    assert listener.find_command(heard, PREFIX, opens_with_command) == (None, None)


def test_the_wake_word_must_be_a_whole_word(opens_with_command):
    assert listener.find_command("maximize notepad", "max", opens_with_command) == (None, None)
    assert listener.find_command("max, maximize notepad", "max") == ("maximize notepad", None)


@pytest.mark.parametrize("heard, command", [
    ("hey computer open notepad", "open notepad"),
    ("okay, computer, what time is it", "what time is it"),
    # Background speech heard before the wake word.
    ("The game's on. Computer, volume up.", "volume up."),
])
def test_wake_word_after_a_greeting_or_another_sentence(heard, command, opens_with_command):
    assert listener.find_command(heard, PREFIX, opens_with_command) == (command, None)
    # Those are guesses: without the command check, only an opening wake word counts.
    assert listener.find_command(heard, PREFIX) == (None, None)


@pytest.mark.parametrize("heard, command, heard_as", [
    ("commuter open notepad", "open notepad", "commuter"),
    # Split into two words by the recogniser.
    ("compute her, open notepad", "open notepad", "compute her"),
])
def test_a_misheard_wake_word_counts_before_a_command(heard, command, heard_as, opens_with_command):
    assert listener.find_command(heard, PREFIX, opens_with_command) == (command, heard_as)


def test_a_misheard_wake_word_before_ordinary_speech_does_not(opens_with_command):
    heard = "commuter traffic made me lose track of time"
    assert listener.find_command(heard, PREFIX, opens_with_command) == (None, None)
