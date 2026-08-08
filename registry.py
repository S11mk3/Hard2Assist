"""Command discovery and dispatch.

A command module is any .py file under commands/<group>/ that defines:

    NAME      -- the word the user says
    TAKES_ARG -- True if the rest of the sentence is passed to run()
    HELP      -- one line shown by the `help` command
    ALIASES   -- optional; words the recogniser commonly returns instead
    run()     -- run(arg) if TAKES_ARG, otherwise run()

Commands are registered purely by their presence on disk: adding one means
dropping a file into the folder, with no central list to update.
"""

import difflib
import glob
import importlib.util
import os
import sys

from output import detail, say

# Sentinel a command returns to request shutdown. Only `stop` uses it.
STOP = object()


def _roots():
    """Directories that may contain a commands/ folder.

    Running from source there is only one. In the built .exe there are two:
    the PyInstaller bundle (sys._MEIPASS, where the shipped commands are
    unpacked) and the directory next to the .exe itself, so users can drop
    in new commands without rebuilding.
    """
    if getattr(sys, "frozen", False):
        return [sys._MEIPASS, os.path.dirname(sys.executable)]
    return [os.path.dirname(os.path.abspath(__file__))]


_loaded = None
_aliases = {}


def load():
    """Import every command module. Returns {name: module}.

    The result is cached so callers (such as `help`) can request the command
    list without rescanning the disk.
    """
    global _loaded
    if _loaded is not None:
        return _loaded

    commands = {}

    for root in _roots():
        pattern = os.path.join(root, "commands", "*", "*.py")

        for path in sorted(glob.glob(pattern)):
            if os.path.basename(path).startswith("__"):
                continue

            module = _import_file(path)
            if module is None:
                continue

            if not hasattr(module, "NAME") or not hasattr(module, "run"):
                detail(f"Skipping {os.path.basename(path)}: it needs a NAME and a run()")
                continue

            name = module.NAME.lower()
            if name in commands:
                # First root wins; a command next to the .exe never overrides
                # a bundled one of the same name.
                continue

            commands[name] = module

    _loaded = commands
    _build_aliases(commands)
    return commands


def _build_aliases(commands):
    """Map each declared alias onto its command.

    Aliases absorb consistent recognition errors -- for example, Google's
    recogniser returns "clothes" for "close" far more often than not.
    """
    global _aliases
    _aliases = {}

    for name, module in commands.items():
        for alias in getattr(module, "ALIASES", ()):
            alias = alias.lower()
            # A real command name always takes priority over an alias.
            if alias not in commands:
                _aliases.setdefault(alias, name)


def resolve(commands, word):
    """Determine which command a spoken word refers to.

    Returns (name, corrected_from), where corrected_from is the original word
    when a correction was applied (alias or fuzzy match) and None on an exact
    match. Corrections are reported to the user rather than applied silently.
    Returns (None, None) when nothing matches.
    """
    word = word.lower()

    if word in commands:
        return word, None

    if word in _aliases:
        return _aliases[word], word

    close = difflib.get_close_matches(word, list(commands), n=1, cutoff=0.75)
    if close:
        return close[0], word

    return None, None


def _import_file(path):
    """Load a single .py file as a module, by path.

    Loading by path rather than through a `commands` package is what allows
    the built .exe to pick up command files dropped in next to it: a package
    is bound to the folder it was first imported from, so files added later
    in a different folder would never be found.
    """
    # The module name includes the full path so that same-named files in
    # different groups do not collide in sys.modules.
    unique = "h2a_command_" + path.replace(os.sep, "_").replace(":", "").lstrip("_")

    try:
        spec = importlib.util.spec_from_file_location(unique, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[unique] = module
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        detail(f"Could not load {os.path.basename(path)}: {e}")
        sys.modules.pop(unique, None)
        return None


def dispatch(commands, utterance):
    """Run the command an utterance asks for.

    The first word selects the command and the rest becomes its argument:
    "open task manager" runs `open` with "task manager". Matching only the
    first word keeps dispatch predictable when a sentence happens to contain
    more than one command name.
    """
    utterance = utterance.strip()
    if not utterance:
        return None

    word, _, argument = utterance.partition(" ")
    name, corrected_from = resolve(commands, word)

    if name is None:
        say(f"I don't know the command '{word}'. Say 'computer help' for a list.")
        return None

    if corrected_from:
        # Written but not spoken: the command's own confirmation, which
        # follows immediately, already says what it decided to do.
        detail(f"(heard '{corrected_from}', taking it as '{name}')")

    module = commands[name]
    argument = argument.strip()

    if getattr(module, "TAKES_ARG", False):
        if not argument:
            example = getattr(module, "EXAMPLE", f"{module.NAME} something")
            say(f"'{module.NAME}' needs something after it, like "
                f"'computer {example}'.")
            return None
        return module.run(argument)

    return module.run()
