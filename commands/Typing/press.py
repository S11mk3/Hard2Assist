"""Press a key, or a keyboard shortcut, in the app in front."""

import session
import win
from output import detail, say

NAME = "press"
TAKES_ARG = True
ALIASES = ("hit", "tap", "pressed", "presses")
HELP = "press <key>  -- press a key or shortcut: enter, tab, escape, save, copy, paste"
EXAMPLE = "press enter"

ABOUT = """\
Press taps a single key, or a keyboard shortcut, in the window in front.
Keys: enter, tab, escape, space, backspace, delete, home, end, and the
four arrow keys -- "press up", "press left".
Shortcuts: save, copy, paste, cut, undo, redo, select all, find, print,
new tab, close tab.
"press the enter key" works as well as "press enter".\
"""

CTRL = win.VK_CONTROL

# What each spoken name presses. The shortcuts are here rather than as
# commands of their own because "press save" and "computer save" would be two
# words competing for the same meaning, and one table is easier to extend than
# a folder of near-identical files.
KEYS = {
    "enter": (win.VK_RETURN,),
    "return": (win.VK_RETURN,),
    "new line": (win.VK_RETURN,),
    "tab": (win.VK_TAB,),
    "escape": (win.VK_ESCAPE,),
    "esc": (win.VK_ESCAPE,),
    "space": (win.VK_SPACE,),
    "spacebar": (win.VK_SPACE,),
    "backspace": (win.VK_BACK,),
    "back space": (win.VK_BACK,),
    "delete": (win.VK_DELETE,),
    "home": (win.VK_HOME,),
    "end": (win.VK_END,),
    "up": (win.VK_UP,),
    "down": (win.VK_DOWN,),
    "left": (win.VK_LEFT,),
    "right": (win.VK_RIGHT,),

    "save": (CTRL, ord("S")),
    "copy": (CTRL, ord("C")),
    "paste": (CTRL, ord("V")),
    "cut": (CTRL, ord("X")),
    "undo": (CTRL, ord("Z")),
    "redo": (CTRL, ord("Y")),
    "select all": (CTRL, ord("A")),
    "find": (CTRL, ord("F")),
    "print": (CTRL, ord("P")),
    "new tab": (CTRL, ord("T")),
    "close tab": (CTRL, ord("W")),
}

# Offered when a key is not recognised. The whole table would be a wall of
# words to hear read out, so this is the useful half.
SUGGESTED = ("enter", "tab", "escape", "delete", "save", "copy", "paste",
             "undo", "select all")


def run(argument):
    key = argument.lower().strip().strip(" ,.")

    # "press the enter key" is how people say it out loud.
    for filler in ("the ", "a "):
        if key.startswith(filler):
            key = key[len(filler):]
    for filler in (" key", " button"):
        if key.endswith(filler):
            key = key[:-len(filler)]

    if key not in KEYS:
        say(f"I don't know a key called {key}.")
        detail(f"Try {', '.join(SUGGESTED)}.")
        return

    target = session.keyboard_target()
    if target is None:
        return

    if not win.send_keys(*KEYS[key]):
        say(f"Windows wouldn't let me press that in {target}.")
        detail("That window runs as administrator and Hard2Assist does not. "
               "Restart Hard2Assist as administrator to control it.")
        return

    say(f"Pressed {key}")
