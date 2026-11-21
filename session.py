"""What the last command acted on, so the next can say "it" -- and the helpers the window and
keyboard commands share, which live here because commands are loaded by path and cannot import
each other.

    computer open notepad
    computer type hello
    computer minimize it

Only the App is remembered, never a window handle; the commands find its windows each time.
"""

import re
import time

import apps
import settings
import win
from output import detail, plural, say, warn

# Ways of saying "the thing we were just talking about", matched against the whole argument.
# Bare "one" is left out: it is close enough to real words to catch mishearings.
PRONOUNS = {
    "it", "that", "this", "them", "those", "these", "window",
    "that one", "this one", "that window", "this window", "the window",
    "current window", "same", "same one", "last one",
}

# How long a window needs after coming forward before it takes keystrokes; without it the first
# letters of a `type` land nowhere.
FOCUS_SETTLE = 0.08

ADMIN_HINT = ("It runs as administrator and Hard2Assist does not. Restart Hard2Assist as "
              "administrator to control it.")

_last = None


def remember(app):
    global _last
    _last = app


def last():
    return _last


def resolve(argument):
    """The App an argument names, or the last one named for "it". None if unknown.

    Remembered when found, not when the command succeeds, so "close notepad" with notepad not
    open still leaves "open it" meaning notepad.
    """
    spoken = argument.lower().strip()
    if spoken in PRONOUNS:
        return last()

    app = apps.find(spoken)
    if app is not None:
        remember(app)
    return app


def unknown(argument):
    """Say why an argument named nothing -- sensibly, when it was "it" and nothing was named yet."""
    if argument.lower().strip() in PRONOUNS:
        say("I'm not sure what you mean by that yet. Name the app once and I'll remember it.")
    else:
        warn(f"I don't know an app called {argument}.")


def refused(what):
    """Report a request Windows turned down: nearly always the target runs as administrator."""
    warn(f"Windows won't let me {what}.")
    detail(ADMIN_HINT)


def split_all(argument):
    """("all notepad") -> ("notepad", True)."""
    argument = argument.strip()
    if argument.lower().startswith("all "):
        return argument[4:].strip(), True
    return argument, False


def target(argument):
    """(app, every) for a window command's argument, or None after saying why.

    every is set by a leading "all": `close cmd` closes the newest console, `close all cmd` each.
    """
    argument, every = split_all(argument)
    app = resolve(argument)
    if app is None:
        unknown(argument)
        return None
    return app, every


def windows(app, every=True):
    """The app's windows, or only the newest, or None after saying it isn't open.

    The newest is the one whose process started last: `close cmd` shuts the console just opened
    by voice, not the one the user was working in.
    """
    if every:
        handles = win.windows_of(app)
    else:
        newest = win.newest_window_of(app)
        handles = [newest] if newest else []

    if not handles:
        say(f"{app.name} isn't open.")
        return None
    return handles


def each_window(argument, action, done, verb):
    """The whole of `minimize`, `fullscreen` and `shrink`: action(hwnd), which returns whether it
    worked, on every window of the app -- leaving some as they were would look half done."""
    found = target(argument)
    handles = found and windows(found[0])
    if not handles:
        return

    app = found[0]
    changed = sum(1 for hwnd in handles if action(hwnd))
    if changed:
        say(f"{done} {plural(changed, app.name + ' window')}")
    if changed < len(handles):
        refused(f"{verb} {app.name}")


def _app_name(title):
    """The app's part of a window title, to say aloud: "*Untitled - Notepad" -> "Notepad"."""
    return re.sub(r"^\W+", "", title.split(" - ")[-1]).strip() or title


def keyboard_target():
    """Make sure typed keys land in the right window. Returns its name, or None having said why.

    The app last named, brought forward if another window has been clicked since: "open notepad",
    then "dictate", types into Notepad whatever is in front. Only when nothing has been named
    does it use the window in front -- never our own.
    """
    prefix = settings.get("prefix")
    app = last()

    if app is not None and app.kind != "itself":
        handles = win.windows_of(app)
        if not handles:
            say(f"{app.name} isn't open. Say {prefix} open {app.name} first.")
            return None
        if win.foreground() in handles:   # already there, perhaps one of several the user picked
            return app.name

        hwnd = win.newest_window_of(app)
        if hwnd is None or not win.focus_window(hwnd):
            warn(f"Windows wouldn't let me switch to {app.name}.")
            return None
        time.sleep(FOCUS_SETTLE)
        return app.name

    if win.foreground_is_ours():
        say(f"I'm not sure where to type. Open something first, like {prefix} open notepad.")
        return None
    title = win.foreground_title()
    return _app_name(title) if title else "the window in front"
