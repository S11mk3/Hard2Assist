"""Say what Hard2Assist is: its name, what it does, and who made it.

The short version is spoken; the details nobody wants read aloud are written. The wake word and
counts are read live, so the introduction never names a wake word or a number that has changed.
"""

import apps
import recognizer
import registry
import settings
from output import detail, say
from version import AUTHOR, VERSION
from version import NAME as APP_NAME

NAME = "introduce"
TAKES_ARG = False
SYNONYMS = ("introduction", "introductions", "intro")
ALIASES = ("introducing", "introduced", "introduces")

# The ways of asking that hold no command word. Not a "yourself" alias: "shut yourself down" and
# "close yourself" mean `stop`.
PHRASES = ("who are you", "what are you", "who is this", "who made you", "who created you",
           "who built you", "who wrote you", "what is your name", "what's your name",
           "whats your name", "tell me about yourself", "tell me about you", "describe yourself",
           "explain yourself")

HELP = "introduce -- what I am and who made me ('who are you')"

ABOUT = """\
Introduce says what I am: my name, what I do, who made me, and what I am
built from.
"who are you", "introduce yourself", "who made you" and "tell me about
yourself" all reach it.
The short version is spoken; the version number, the wake word and where
your settings are kept are written here.\
"""


def _listening():
    """(spoken, written) for how speech is recognised right now: Moonshine can fail to load."""
    if recognizer.is_local():
        return "a speech model that runs on this PC", "Moonshine, on this PC, so nothing you say leaves it"
    return "Google's speech recognition", "Google's free speech API, so I need the internet"


def run():
    commands = registry.load()
    total = sum(apps.counts().values())
    prefix = settings.get("prefix")
    spoken, written = _listening()

    say(f"I'm {APP_NAME}, a voice assistant for Windows, made by {AUTHOR}. I'm written in Python: "
        f"I hear you through {spoken}, and answer in this PC's own Windows voice. "
        f"I know {len(commands)} commands and {total} apps. Say {prefix} help to see them all.")

    rows = (
        ("Name", APP_NAME),
        ("Version", VERSION),
        ("Made by", AUTHOR),
        ("What I am", "A voice assistant for Windows"),
        ("Wake word", f"'{prefix}', said before every command"),
        ("I know", f"{len(commands)} commands and {total} apps, folders and websites"),
        ("Written in", "Python, with a Tk window"),
        ("Listening", written),
        ("Speaking", "the Windows voice on this PC, which never leaves it"),
        ("Settings", settings.FILE),
    )
    width = max(len(label) for label, _ in rows)
    detail("")
    detail("ABOUT ME")
    for label, value in rows:
        detail(f"  {label.ljust(width)}  {value}")
    detail("")
