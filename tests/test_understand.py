"""Which command an utterance asks for, and with what argument: registry.understand() and friends."""

import pytest

import registry


@pytest.mark.parametrize("utterance, expected", [
    # The plain form.
    ("open notepad", ("open", "notepad", None)),
    ("close notepad", ("close", "notepad", None)),
    ("search how to cook rice", ("search", "how to cook rice", None)),
    # The offline recogniser capitalises and punctuates, and politeness is not part of the name.
    ("Open Notepad, please.", ("open", "notepad", None)),
    # A command word anywhere in a sentence.
    ("can you open notepad", ("open", "notepad", None)),
    # Filler between the command and its argument is dropped.
    ("set the volume to fifty", ("volume", "fifty", None)),
    # An argument spoken before the command word, when nothing follows it.
    ("turn up the volume", ("volume", "up", None)),
    ("mute the volume", ("volume", "mute", None)),
])
def test_command_and_argument(commands, utterance, expected):
    assert registry.understand(utterance) == expected


@pytest.mark.parametrize("utterance, name", [
    ("what can you do", "help"),
    ("who are you", "introduce"),
    ("what's open", "windows"),
    ("how much charge", "battery"),
    ("take a note", "dictate"),
    ("full screen", "fullscreen"),
    ("exit full screen", "shrink"),
])
def test_whole_sentences_reach_their_command(commands, utterance, name):
    assert registry.understand(utterance)[0] == name


def test_a_phrase_outranks_a_command_word_inside_it(commands):
    # "stop" alone quits the app; "stop talking" only silences the voice.
    assert registry.understand("stop talking") == ("quiet", "", None)
    assert registry.understand("stop") == ("stop", "", None)
    assert registry.understand("close yourself") == ("stop", "", None)


def test_a_command_named_before_a_phrase_keeps_it_as_its_argument(commands):
    assert registry.understand("help full screen") == ("help", "full screen", None)
    assert registry.understand("type stop talking") == ("type", "stop talking", None)


@pytest.mark.parametrize("utterance, expected", [
    ("close tab", ("press", "close tab", None)),
    ("open a new tab", ("press", "new tab", None)),
    ("show desktop", ("minimize", "everything", None)),
])
def test_a_phrase_can_imply_its_argument(commands, utterance, expected):
    assert registry.understand(utterance) == expected


def test_a_real_command_name_beats_an_alias(commands):
    # "show" is a synonym of `focus`, but "time" is a command in its own right.
    assert registry.understand("can you show me the time")[0] == "time"


def test_verbatim_commands_get_the_words_as_heard(commands):
    # Stripping "the" would change what gets typed.
    assert registry.understand("type the quick brown fox") == ("type", "the quick brown fox", None)
    assert registry.understand("type Hello there.") == ("type", "Hello there.", None)


@pytest.mark.parametrize("utterance, expected", [
    # Aliases: what the recogniser commonly returns instead of the command word.
    ("clothes notepad", ("close", "notepad", "clothes")),
    ("opun notepad", ("open", "notepad", "opun")),
    ("minimized notepad", ("minimize", "notepad", "minimized")),
    # A first word that nearly names a command.
    ("tim", ("time", "", "tim")),
])
def test_misheard_command_words_are_corrected(commands, utterance, expected):
    assert registry.understand(utterance) == expected


@pytest.mark.parametrize("utterance, expected", [
    ("maximize it", ("fullscreen", "it", None)),
    ("quit", ("stop", "", None)),
    ("switch to notepad", ("focus", "notepad", None)),
])
def test_synonyms_are_not_reported_as_corrections(commands, utterance, expected):
    assert registry.understand(utterance) == expected


@pytest.mark.parametrize("utterance", ["fill notepad", "skill notepad", "kilt chrome", "top", "shop",
                                       "clone notepad"])
def test_destructive_commands_are_never_guessed(commands, utterance):
    assert registry.understand(utterance)[0] not in ("kill", "stop", "close")


@pytest.mark.parametrize("utterance", ["", "   ", "make me a sandwich"])
def test_nothing_matches(commands, utterance):
    assert registry.understand(utterance) == (None, None, None)


@pytest.mark.parametrize("utterance, opens", [
    ("open notepad", True),
    ("can you open notepad", True),
    ("what's the time", True),
    ("what can you do", True),
    ("please stop talking", True),
    # A sentence that merely mentions a command word later on.
    ("traffic made me lose track of time", False),
    ("her, open notepad", False),
])
def test_opens_with_command(commands, utterance, opens):
    assert registry.opens_with_command(utterance) is opens


@pytest.mark.parametrize("utterance, parts", [
    ("open notepad and type hello", ["open notepad", "type hello"]),
    ("open notepad and then type hello", ["open notepad", "type hello"]),
    ("Open Notepad, then volume up.", ["Open Notepad", "volume up."]),
    ("volume up and open youtube and time", ["volume up", "open youtube", "time"]),
    # Never inside a command's text.
    ("type salt and pepper", ["type salt and pepper"]),
    ("type hello and open notepad", ["type hello and open notepad"]),
    ("search cats and dogs", ["search cats and dogs"]),
    # Only before a real command name.
    ("close notepad and calculator", ["close notepad and calculator"]),
])
def test_chained_commands(commands, utterance, parts):
    assert registry._chain(utterance) == parts


def test_every_command_declares_what_help_shows(commands):
    for name, module in commands.items():
        assert module.NAME.lower() == name
        assert "--" in getattr(module, "HELP", ""), f"{name} has no 'usage -- description' HELP line"
        assert callable(module.run)


def test_help_lines_are_aligned(commands):
    lines = commands["help"].help_lines(commands)
    assert len({line.index("--") for line in lines}) == 1


def test_command_modules_get_plain_names(commands):
    for module in commands.values():
        assert "." not in module.__name__
