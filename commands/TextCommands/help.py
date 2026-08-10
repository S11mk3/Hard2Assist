"""List everything Hard2Assist can do.

The output is generated from the loaded commands and the app catalogue,
so it cannot drift out of step with what is actually available.
"""

import apps
import registry
import settings
from output import detail, say

NAME = "help"
TAKES_ARG = False
ALIASES = ("commands", "hlep")
# Only the phrasings that name no command word at all. Anything containing
# "commands" is already reached by the alias below.
PHRASES = ("what can you do", "what do you do", "what can i say")
HELP = "help         -- show this list"

# The log panel is comfortable at roughly this width.
LINE_WIDTH = 76

# A name longer than this gets a line to itself instead of setting the column
# width for every other name. Start Menu entries run to 48 characters
# ("windows defender firewall with advanced security"), and sizing all the
# columns to those leaves one narrow column beside a field of whitespace.
MAX_WIDTH = 24

GAP = "  "


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


def run():
    commands = registry.load()
    groups = apps.names_by_kind()
    total = sum(len(names) for _, names in groups)

    # Speak only a short summary; the full lists would be tedious to hear.
    say(f"I know {len(commands)} commands and {total} apps. "
        f"They're on screen.")

    prefix = settings.get("prefix")

    detail("")
    detail(f"COMMANDS   -- say '{prefix}' first")
    for name in sorted(commands):
        detail("  " + getattr(commands[name], "HELP", name))

    detail("")
    detail("You can talk normally too -- these all work:")
    for example in (f"{prefix} what time is it",
                    f"{prefix} turn up the volume",
                    f"{prefix} can you open notepad",
                    f"{prefix} how much battery is left"):
        detail(f"  {example}")

    for label, names in groups:
        detail("")
        detail(f"{label.upper()}   ({len(names)})")
        for row in _rows(names):
            detail("  " + row)

    detail("")
