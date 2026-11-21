"""List the commands, the apps, or explain one command in full.

    computer help            every command, one line each
    computer help apps       everything I can open
    computer help open       what `open` does, and how to say it

Each explanation is the command's own ABOUT, so it cannot drift out of step with the command. A
command with no ABOUT still gets a page, built from its HELP line and EXAMPLE.
"""

import apps
import registry
import settings
from output import detail, say

NAME = "help"
TAKES_ARG = True
ARG_OPTIONAL = True   # bare `help` is the main use, not a mistake
ALIASES = ("hlep",)
SYNONYMS = ("commands",)
PHRASES = ("what can you do", "what do you do", "what can i say")
HELP = "help -- the commands ('help apps', or 'help <command>')"

ABOUT = """\
Help lists every command I know, and explains any one of them.
"{prefix} help apps" lists everything I can open: the programs on this PC,
your folders, and the websites I know.
"{prefix} help open" explains one command -- what it does, how to say it,
and the other ways of asking for it. Any command name works there.
"what can you do" reaches this too.\
"""

# Asking for the app list rather than a command; checked first, so never fuzzy-matched.
APP_TOPICS = ("apps", "app", "applications", "programs", "program", "everything")

# Said in front of the topic: "help me with volume".
TOPIC_FILLER = ("me", "with", "about", "on", "the", "a", "an", "command", "using", "use", "how", "to")

LINE_WIDTH = 76   # what the log panel shows comfortably

# A longer name gets a line of its own, rather than setting the column width for all the rest
# ("windows defender firewall with advanced security").
MAX_WIDTH = 24
GAP = "  "


def _rows(names):
    """Names in aligned columns, overlong ones on lines of their own."""
    normal = [name for name in names if len(name) <= MAX_WIDTH]
    rows = []
    if normal:
        width = max(len(name) for name in normal)
        columns = max(1, (LINE_WIDTH + len(GAP)) // (width + len(GAP)))
        for i in range(0, len(normal), columns):
            rows.append(GAP.join(name.ljust(width) for name in normal[i:i + columns]).rstrip())
    return rows + [name for name in names if len(name) > MAX_WIDTH]


def _topic(argument):
    words = argument.lower().strip(" ,.?!").split()
    while words and words[0] in TOPIC_FILLER:
        words = words[1:]
    while words and words[-1] in ("command", "commands"):
        words = words[:-1]
    return " ".join(words)


def _lines(module, prefix):
    """A command's explanation as lines: its ABOUT, or one built from its HELP line."""
    about = getattr(module, "ABOUT", "").strip()
    if not about:
        _, dashes, description = getattr(module, "HELP", "").partition("--")
        summary = description.strip() if dashes else f"a command called {module.NAME}"
        return [f"{module.NAME.capitalize()} -- {summary}."]
    # replace(), not format(): a stray brace in the prose must not raise.
    return about.replace("{prefix}", prefix).splitlines()


def help_lines(commands):
    """Each command's HELP line, its usage and description aligned in two columns."""
    rows = [getattr(commands[name], "HELP", name).partition("--") for name in sorted(commands)]
    width = max(len(usage.strip()) for usage, _, _ in rows)
    return [f"{usage.strip().ljust(width)}  -- {text.strip()}" if dashes else usage.strip()
            for usage, dashes, text in rows]


def commands_page(commands, prefix):
    detail("")
    detail(f"COMMANDS   -- say '{prefix}' first, or type them below")
    for line in help_lines(commands):
        detail("  " + line)
    detail("")
    detail("MORE")
    detail(f"  {prefix} help apps        everything I can open")
    detail(f"  {prefix} help <command>   how one command works, in full")
    detail("")


def apps_page():
    groups = apps.names_by_kind()
    say(f"I can open {sum(len(names) for _, names in groups)} things. They're on screen.")
    for label, names in groups:
        detail("")
        detail(f"{label.upper()}   ({len(names)})")
        for row in _rows(names):
            detail("  " + row)
    detail("")
    detail("Say the name of any of them after 'open'.")
    detail("")


def _spoken(lines):
    """The first sentence: worth hearing, where the rest is only worth reading. A sentence, not
    a line, since where a line breaks is only how the ABOUT happens to be wrapped."""
    text = " ".join(line.strip() for line in lines if line.strip())
    head, stop, _ = text.partition(". ")
    return head + "." if stop else text


def command_page(module, prefix):
    lines = _lines(module, prefix)
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


def run(argument=""):
    commands = registry.load()
    prefix = settings.get("prefix")
    topic = _topic(argument)

    if not topic:
        say(f"I know {len(commands)} commands and {sum(apps.counts().values())} apps. They're on screen.")
        commands_page(commands, prefix)
        return

    if topic in APP_TOPICS:
        apps_page()
        return

    # The registry's own matching, so `help clothes` explains `close` and `help full screen`
    # explains `fullscreen`.
    name = registry.understand(topic)[0]
    if name is not None:
        command_page(commands[name], prefix)
        return

    guess = registry.suggest(topic)
    if guess is not None:
        say(f"I don't have a command called {topic}. Did you mean {guess.NAME}? Say {prefix} help {guess.NAME}.")
    else:
        say(f"I don't have a command called {topic}. Say {prefix} help to see them all.")
