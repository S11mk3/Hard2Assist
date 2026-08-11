"""List the commands, the apps, or explain one command in full.

    computer help            every command, one line each
    computer help apps       everything I can open
    computer help open       what `open` does, and how to say it

Split into three because one list was doing three jobs: the commands, a set
of example sentences and the whole app catalogue arrived together, and the
part you actually wanted scrolled past with the rest. The apps moved behind
`help apps`, and the examples are gone -- `help <command>` says how each one
is spoken, at the moment you ask about it, which is what the examples were
for.

The explanations live in each command's own ABOUT, not in a table here, for
the same reason the command list is generated: a central list is a list that
drifts. A command dropped into %APPDATA% with no ABOUT still gets a page,
built from its HELP line and its EXAMPLE.
"""

import difflib

import apps
import registry
import settings
from output import detail, say

NAME = "help"
TAKES_ARG = True

# Bare `help` is the command's main use, not a mistake to be corrected.
ARG_OPTIONAL = True

ALIASES = ("commands", "hlep")
# Only the phrasings that name no command word at all. Anything containing
# "commands" is already reached by the alias above.
PHRASES = ("what can you do", "what do you do", "what can i say")

HELP = "help         -- the commands ('help apps', or 'help <command>')"

ABOUT = """\
Help lists every command I know, and explains any one of them.
"{prefix} help apps" lists everything I can open: the programs on this PC,
your folders, and the websites I know.
"{prefix} help open" explains one command -- what it does, how to say it,
and the other ways of asking for it. Any command name works there.
"what can you do" reaches this too.\
"""

# Words that ask for the app catalogue rather than a command. Kept short and
# checked before any command lookup, so they cannot be fuzzy-matched into
# something else.
APP_TOPICS = ("apps", "app", "applications", "programs", "program",
              "everything")

# Said in front of the real topic. "help me with volume" asks about `volume`.
TOPIC_FILLER = ("me", "with", "about", "on", "the", "a", "an", "command",
                "using", "use", "how", "to")

# The log panel is comfortable at roughly this width.
LINE_WIDTH = 76

# A name longer than this gets a line to itself instead of setting the column
# width for every other name. Start Menu entries run to 48 characters
# ("windows defender firewall with advanced security"), and sizing all the
# columns to those leaves one narrow column beside a field of whitespace.
MAX_WIDTH = 24

GAP = "  "

# How close an unknown topic must be to a command name to be offered as a
# suggestion. Looser than the registry's own matching, which has already had
# its turn by the time this runs -- this only produces advice.
SUGGEST_CUTOFF = 0.6


def _rows(names):
    """Wrap names into aligned columns, the overlong ones on their own lines."""
    normal = [name for name in names if len(name) <= MAX_WIDTH]
    wide = [name for name in names if len(name) > MAX_WIDTH]

    rows = []

    if normal:
        width = max(len(name) for name in normal)
        columns = max(1, (LINE_WIDTH + len(GAP)) // (width + len(GAP)))

        for i in range(0, len(normal), columns):
            row = normal[i:i + columns]
            rows.append(GAP.join(name.ljust(width) for name in row).rstrip())

    rows.extend(wide)
    return rows


def _topic(argument):
    """The command or subject an argument names, cleaned up for matching."""
    words = argument.lower().strip().strip(" ,.?!").split()

    while words and words[0] in TOPIC_FILLER:
        words = words[1:]

    while words and words[-1] in ("command", "commands"):
        words = words[:-1]

    return " ".join(words)


def _summary(module):
    """One line describing a command, for one that declares no ABOUT.

    Taken from the half of its HELP line after the dashes, which is already
    written as a description: "close an app, letting it save first".
    """
    text = getattr(module, "HELP", "")

    if "--" in text:
        return text.split("--", 1)[1].strip()

    return f"a command called {module.NAME}"


def _lines(module, prefix):
    """A command's explanation, as lines. Its ABOUT, or a stand-in."""
    about = getattr(module, "ABOUT", "").strip()

    if not about:
        return [f"{module.NAME.capitalize()} -- {_summary(module)}."]

    # Not str.format(): an ABOUT is prose, and a stray brace in it would
    # raise rather than print. Only this one placeholder is substituted, so
    # an explanation cannot name a wake word the user has changed.
    return about.replace("{prefix}", prefix).splitlines()


def commands_page(commands, prefix):
    """Every command, one line each."""
    detail("")
    detail(f"COMMANDS   -- say '{prefix}' first")

    for name in sorted(commands):
        detail("  " + getattr(commands[name], "HELP", name))

    detail("")
    detail("MORE")
    detail(f"  {prefix} help apps        everything I can open")
    detail(f"  {prefix} help <command>   how one command works, in full")
    detail("")


def apps_page():
    """Everything the app catalogue can open, grouped by where it came from."""
    groups = apps.names_by_kind()
    total = sum(len(names) for _, names in groups)

    say(f"I can open {total} things. They're on screen.")

    for label, names in groups:
        detail("")
        detail(f"{label.upper()}   ({len(names)})")
        for row in _rows(names):
            detail("  " + row)

    detail("")
    detail("Say the name of any of them after 'open'.")
    detail("")


def _spoken(lines):
    """The part of an explanation worth hearing: its first sentence.

    A sentence rather than a first line, because where a line ends is a
    matter of how the text was wrapped in the source file -- speaking
    lines[0] read out "Open launches anything I can name: an app, a program
    from your Start Menu," and stopped there.
    """
    text = " ".join(line.strip() for line in lines if line.strip())

    head, stop, _ = text.partition(". ")

    return head + "." if stop else text


def command_page(module, prefix):
    """One command, explained in full."""
    lines = _lines(module, prefix)

    # Spoken short and written in full, the split `disk` and `windows` make.
    say(_spoken(lines))

    detail("")
    detail(module.NAME.upper())
    for line in lines:
        detail("  " + line if line else "")

    detail("")
    detail(f"  Say:  {registry.usage(module)}")

    phrases = getattr(module, "PHRASES", ())
    if phrases:
        detail(f"  Or:   {', '.join(phrases)}")

    detail("")


def _unknown(commands, topic, prefix):
    """Nothing matched. Offer the nearest command rather than the whole list."""
    close = difflib.get_close_matches(topic, list(commands), n=1,
                                      cutoff=SUGGEST_CUTOFF)

    if close:
        say(f"I don't have a command called {topic}. Did you mean {close[0]}? "
            f"Say {prefix} help {close[0]}.")
        return

    say(f"I don't have a command called {topic}. "
        f"Say {prefix} help to see them all.")


def run(argument=""):
    commands = registry.load()
    prefix = settings.get("prefix")
    topic = _topic(argument)

    if not topic:
        groups = apps.names_by_kind()
        total = sum(len(names) for _, names in groups)

        # Speak only a short summary; the full lists would be tedious to hear.
        say(f"I know {len(commands)} commands and {total} apps. "
            f"They're on screen.")

        commands_page(commands, prefix)
        return

    if topic in APP_TOPICS:
        apps_page()
        return

    # The registry's own matching, so every way of naming a command reaches
    # its page: `help clothes` explains `close`, and `help full screen`
    # explains `fullscreen`. Spoken phrasings work here only because
    # understand() lets a command word spoken first keep the sentence --
    # otherwise "full screen" would be matched as a phrase and maximise
    # something instead of explaining how to.
    name, _, _ = registry.understand(commands, topic)

    if name is None:
        _unknown(commands, topic, prefix)
        return

    command_page(commands[name], prefix)
