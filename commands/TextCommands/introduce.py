"""Say what Hard2Assist is: its name, what it does, and who made it.

The short version is spoken; the details nobody wants read out loud -- where
the settings file lives, what the app is built from -- are written.

The wake word comes from settings and the counts from the registry and the
app catalogue, so an introduction cannot name a wake word the user has
changed or a command list that has grown since.
"""

import apps
import registry
import settings
from output import detail, say

NAME = "introduce"
TAKES_ARG = False

# What the recogniser hands back when it does not return "introduce" itself.
# Single words only: aliases are matched a word at a time.
ALIASES = ("introduction", "introductions", "intro", "introducing",
           "introduced", "introduces")

# The ways of asking that contain no command word at all. "introduce
# yourself" needs none of them -- the command word is already in it.
#
# Whole phrases rather than a "yourself" alias, which would have to be that
# single word: "shut yourself down" and "close yourself" already mean `stop`.
#
# Each is as long as the phrasing allows. A phrase is matched anywhere in a
# sentence, so a short one is text the user can never type or search for.
PHRASES = ("who are you", "what are you", "who is this",
           "who made you", "who created you", "who built you",
           "who wrote you", "what is your name", "what's your name",
           "whats your name", "tell me about yourself",
           "tell me about you", "describe yourself", "explain yourself")

HELP = "introduce    -- what I am and who made me ('who are you')"

ABOUT = """\
Introduce says what I am: my name, what I do, who made me, and what I am
built from.
"who are you", "introduce yourself", "who made you" and "tell me about
yourself" all reach it.
The short version is spoken; the version number, the wake word and where
your settings are kept are written here.\
"""

MAKER = "Andrija Simic"

# Kept in step with build.py, which is where a release sets the version.
VERSION = "1.0.0"

GAP = "  "


def _rows(commands, total, prefix):
    """The written introduction, as (label, value) pairs."""
    return (
        ("Name", "Hard2Assist"),
        ("Version", VERSION),
        ("Made by", MAKER),
        ("What I am", "A voice assistant for Windows"),
        ("Wake word", f"'{prefix}', said before every command"),
        ("I know", f"{len(commands)} commands and {total} apps, "
                   f"folders and websites"),
        ("Written in", "Python, with a Tk window"),
        ("Listening", "Google's free speech API, so I need the internet"),
        ("Speaking", "the Windows voice on this PC, which never leaves it"),
        ("Settings", settings.FILE),
    )


def run():
    commands = registry.load()
    total = sum(apps.counts().values())
    prefix = settings.get("prefix")

    say(f"I'm Hard2Assist, a voice assistant for Windows, made by {MAKER}. "
        f"I'm written in Python: I hear you through Google's speech "
        f"recognition, and answer in this PC's own Windows voice. "
        f"I know {len(commands)} commands and {total} apps. "
        f"Say {prefix} help to see them all.")

    rows = _rows(commands, total, prefix)
    width = max(len(label) for label, _ in rows)

    detail("")
    detail("ABOUT ME")
    for label, value in rows:
        detail(f"  {label.ljust(width)}{GAP}{value}")
    detail("")
