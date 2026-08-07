"""Finds the command modules and decides which one an utterance is asking for.

A command module is any .py file under commands/<group>/ that defines:

    NAME      -- the word the user says
    TAKES_ARG -- True if the rest of the sentence is passed to run()
    HELP      -- one line shown by `help`
    ALIASES   -- optional; other words the recogniser produces for this one
    run()     -- run(arg) if TAKES_ARG else run()

Nothing about a command is written down anywhere else, so adding one means
dropping a file in the folder.
"""

import difflib
import glob
import importlib.util
import os
import sys

from output import detail, say

# A command returns this to tell the main loop to shut down. `stop` is the only
# one that does.
STOP = object()


def _roots():
    """Directories that might hold a commands/ folder.

    Running from source there is only one. Inside the built .exe there are two:
    PyInstaller unpacks the bundled files to a temporary folder (sys._MEIPASS),
    and we also look next to the .exe itself so you can drop in a new command
    without rebuilding.
    """
    if getattr(sys, "frozen", False):
        return [sys._MEIPASS, os.path.dirname(sys.executable)]
    return [os.path.dirname(os.path.abspath(__file__))]


_loaded = None
_aliases = {}


def load():
    """Import every command module. Returns {name: module}.

    Cached, so `help` can ask for the command list without redoing the scan.
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
                continue  # first root wins; a later one does not override

            commands[name] = module

    _loaded = commands
    _build_aliases(commands)
    return commands


def _build_aliases(commands):
    """Map every alias a command declares onto that command.

    "close" is the one that really needs this -- Google's recogniser hears the
    ordinary English word "clothes" almost every time.
    """
    global _aliases
    _aliases = {}

    for name, module in commands.items():
        for alias in getattr(module, "ALIASES", ()):
            alias = alias.lower()
            if alias not in commands:      # a real command always wins
                _aliases.setdefault(alias, name)


def resolve(commands, word):
    """Work out which command a spoken word meant.

    Returns (name, corrected_from) where corrected_from is set if we had to
    interpret. Never guesses silently -- being told "I took 'cloze' as 'close'"
    is far better than wondering why the wrong thing happened.
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
    """Load a single .py file as a module, by its path.

    Loading by path rather than as part of a `commands` package is what lets the
    built .exe pick up commands dropped in beside it. A package remembers the
    folder it was first imported from, so anything added later in a different
    folder would never be found.
    """
    # Unique name per file, so two groups can hold same-named files.
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

    The first word is the command and the rest is its argument, so "open task
    manager" is the `open` command with "task manager". Matching the first word
    exactly keeps this predictable -- the old code searched for a command name
    anywhere in the sentence, so a sentence containing two command words was
    resolved by whatever order the files happened to be listed in.
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
        # Written but not spoken: you are about to hear the command's own
        # confirmation, which already tells you what it decided to do.
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
