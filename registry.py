"""Finds the command modules and decides which one an utterance is asking for.

A command module is any .py file under commands/<group>/ that defines:

    NAME      -- the word the user says
    TAKES_ARG -- True if the rest of the sentence is passed to run()
    HELP      -- one line shown by `help`
    run()     -- run(arg) if TAKES_ARG else run()

Nothing about a command is written down anywhere else, so adding one means
dropping a file in the folder.
"""

import importlib
import os
import pkgutil

# A command returns this to tell the main loop to shut down. `stop` is the only
# one that does.
STOP = object()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COMMANDS_DIR = os.path.join(BASE_DIR, "commands")


_loaded = None


def load():
    """Import every command module. Returns {name: module}.

    Cached, so `help` can ask for the command list without redoing the scan.
    """
    global _loaded
    if _loaded is not None:
        return _loaded

    commands = {}

    for group in sorted(os.listdir(COMMANDS_DIR)):
        group_path = os.path.join(COMMANDS_DIR, group)
        if not os.path.isdir(group_path) or group == "__pycache__":
            continue

        for _finder, module_name, _ispkg in pkgutil.iter_modules([group_path]):
            if module_name == "__init__":
                continue

            full_name = f"commands.{group}.{module_name}"
            try:
                module = importlib.import_module(full_name)
            except Exception as e:
                print(f"Could not load {full_name}: {e}")
                continue

            if not hasattr(module, "NAME") or not hasattr(module, "run"):
                print(f"Skipping {full_name}: it needs a NAME and a run()")
                continue

            name = module.NAME.lower()
            if name in commands:
                print(f"Skipping {full_name}: '{name}' is already taken")
                continue

            commands[name] = module

    _loaded = commands
    return commands


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
    module = commands.get(word.lower())

    if module is None:
        print(f"I don't know the command '{word}'. Say 'computer help' for a list.")
        return None

    argument = argument.strip()

    if getattr(module, "TAKES_ARG", False):
        if not argument:
            print(f"'{module.NAME}' needs something to act on, like "
                  f"'computer {module.NAME} notepad'.")
            return None
        return module.run(argument)

    return module.run()
