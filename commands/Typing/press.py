"""Press a key, a shortcut, or any key combination in the app you last named."""

import session
import win
from output import detail, say, warn

NAME = "press"
TAKES_ARG = True
ALIASES = ("pressed", "presses")
SYNONYMS = ("hit", "tap")
# Said without "press" at all. "close tab" and "open a new tab" start with other commands' names,
# which a phrase outranks.
PHRASES = {"close tab": "close tab", "close the tab": "close tab", "close this tab": "close tab",
           "new tab": "new tab", "open new tab": "new tab", "open a new tab": "new tab"}
HELP = "press <key> -- press a key or shortcut: enter, tab, save, copy, paste, 'control shift t'"
EXAMPLE = "press enter"

ABOUT = """\
Press taps a key, a shortcut, or any combination of keys, in the app you
last named -- or, if you haven't named one, the window in front.
Keys: enter, tab, escape, space, backspace, delete, insert, home, end,
page up, page down, the arrow keys, F1 to F12, any letter or digit.
Shortcuts: save, copy, paste, cut, undo, redo, select all, find, print,
new tab, close tab, switch window.
Combinations: name the keys held down first -- "press control shift t",
"press alt f4", "press windows d".
"new tab" and "close tab" work without saying "press".\
"""

# What people call by what it does rather than by its keys.
SHORTCUTS = {
    "save": "control s", "copy": "control c", "paste": "control v", "cut": "control x",
    "undo": "control z", "redo": "control y", "select all": "control a", "find": "control f",
    "print": "control p", "new tab": "control t", "close tab": "control w",
    "new line": "enter", "switch window": "alt tab",
}

# Offered when a key is not recognised; the whole list would be a wall of words to hear.
SUGGESTED = ("enter", "tab", "escape", "delete", "save", "copy", "paste", "undo", "select all")


def _name(spoken):
    """"enter key" -> "enter": people say the word "key" aloud."""
    name = spoken.lower().strip(" ,.")
    for filler in (" keys", " key", " button"):
        name = name.removesuffix(filler)
    return name


def keys_for(spoken):
    """The virtual keys spoken names, or None: "enter key", "save", "control shift t"."""
    name = _name(spoken)
    return win.parse_keys(SHORTCUTS.get(name, name))


def run(argument):
    keys = keys_for(argument)
    name = _name(argument)
    if keys is None:
        warn(f"I don't know a key called {name}.")
        detail(f"Try {', '.join(SUGGESTED)}, or name keys together like 'control shift t'.")
        return

    target = session.keyboard_target()
    if target is None:
        return
    if not win.send_keys(*keys):
        session.refused(f"press that in {target}")
        return
    say(f"Pressed {name}")
