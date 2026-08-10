"""What the last command acted on, so the next one can say "it".

    computer open notepad
    computer type hello
    computer minimize it

Only the App is remembered, never a window handle. Windows recycles handles,
so a stored one can end up pointing at an unrelated window -- which is why
win.py enumerates on demand and why this module does not try to be cleverer.
The memory answers "which app", and the commands go on finding the windows
themselves exactly as they do when the app is named out loud.

A plain module global is enough. Commands run one at a time, on the microphone
thread, under the GUI's command_lock, so nothing here is ever touched by two
threads at once.
"""

import time

import apps
import settings
import win
from output import say

# Ways of saying "the thing we were just talking about". Matched against the
# whole argument rather than word by word, so the list stays something you can
# read and predict instead of a guessing game.
#
# Bare "one" is deliberately absent: "open one" is not something anyone says,
# and it is close enough to real words to catch a mishearing.
PRONOUNS = {
    "it", "that", "this", "them", "those", "these", "window",
    "that one", "this one", "that window", "this window", "the window",
    "current window", "same", "same one", "last one",
}

# How long a window needs after coming forward before it will accept typed
# characters. Without this the first few letters of a `type` land nowhere.
FOCUS_SETTLE = 0.08

_last = None


def remember(app):
    """Note that a command acted on this app."""
    global _last
    _last = app


def last():
    """The app the last command acted on, or None."""
    return _last


def forget():
    """Drop the memory. Nothing calls this yet; it exists for tests."""
    global _last
    _last = None


def resolve(argument):
    """The App an argument names, or the last one acted on. None if unknown.

    What the window commands call instead of apps.find(). Everything they
    already do is unchanged -- this only adds the case where the argument is
    "it" rather than a name.

    A leading "all " is not handled here: `close`, `kill`, `minimize`,
    `fullscreen` and `shrink` each strip it themselves before asking, because
    it changes what they do rather than what they do it to.
    """
    spoken = argument.lower().strip()

    if spoken in PRONOUNS:
        return last()

    app = apps.find(spoken)

    if app is not None:
        # Remembered on a successful lookup rather than a successful action,
        # so "close notepad" when notepad was never running still leaves "open
        # it" meaning notepad.
        remember(app)

    return app


def unknown(argument):
    """Say why an argument resolved to nothing.

    "I don't know an app called it" is a nonsense sentence, and it is the one
    the user hears the first time they try a pronoun. Worth telling them what
    would work instead.
    """
    if argument.lower().strip() in PRONOUNS:
        say("I'm not sure what you mean by that yet. Name the app once and "
            "I'll remember it.")
        return

    say(f"I don't know an app called {argument}.")


def _app_name(title):
    """The app's name out of a window title, for saying out loud.

    Window titles are written to be read, not heard. "*Untitled - Notepad"
    and "build.py - Hard2Assist - Visual Studio Code" both name the app last,
    after the document, so speaking the whole thing reads out an asterisk and
    a filename nobody asked about. Every other command says a plain name --
    "Opening notepad" -- and this one should sound the same.
    """
    name = title.split(" - ")[-1].strip().lstrip("*").strip()

    return name or title


def keyboard_target():
    """Make sure typed keys will land somewhere useful.

    Returns the name of what they will reach, or None -- having already said
    why not, since there is only one sensible thing to say in each case.

    Typed keys go to whatever window has focus, so most of the time there is
    nothing to do: the user said "open notepad" a moment ago and notepad is
    in front. The exception is our own window being in front, which is
    permanently true under "only listen while I'm in focus". Typing into our
    own log panel is never what was meant, so the app that was last acted on
    is brought forward first -- which is also what makes `type` follow `open`
    in the order the two commands are spoken.
    """
    if not win.foreground_is_ours():
        title = win.foreground_title()
        return _app_name(title) if title else "the window in front"

    app = last()
    if app is None:
        say("I'm not sure where to type. Open something first, like "
            f"{settings.get('prefix')} open notepad.")
        return None

    hwnd = win.newest_window_of(app)
    if hwnd is None:
        say(f"{app.name} isn't open.")
        return None

    if not win.focus_window(hwnd):
        say(f"Windows wouldn't let me switch to {app.name}.")
        return None

    time.sleep(FOCUS_SETTLE)
    return app.name
