"""Turn the volume up, down, or to an exact level."""

import audio
import win
from output import detail, say, warn

NAME = "volume"
TAKES_ARG = True
ALIASES = ("vol", "volumes")
SYNONYMS = ("sound",)
HELP = "volume up|down|mute|<number> -- change the volume ('volume up by 20')"
EXAMPLE = "volume 50"

ABOUT = """\
Volume changes how loud this PC is, and says where it ended up.
"volume up" and "volume down" move it by ten; "volume up by twenty" or
"volume down 5" by as much as you say. "louder" and "quieter" work too.
"volume mute" silences it, and saying it again brings the sound back.
For an exact level, give a number: "volume 50", "volume fifty", "volume
fifty percent", "volume twenty five". "volume max" and "volume half" work
too.
The sentence can go the other way round -- "turn up the volume" and "mute
the volume" both land here.\
"""

UP = ("up", "higher", "louder", "increase", "raise")
DOWN = ("down", "lower", "quieter", "softer", "decrease")
STEP = 10   # "volume up" with no amount

UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fourty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
NAMED = {
    "max": 100, "maximum": 100, "full": 100, "all the way": 100,
    "hundred": 100, "one hundred": 100, "a hundred": 100, "half": 50, "halfway": 50,
}


def to_number(text):
    """"50", "fifty", "twenty five", "50%" -> an int; None if it is not a number."""
    text = text.lower().replace("percent", "").replace("%", "").replace("-", " ").strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    if text in NAMED:
        return NAMED[text]

    total = 0
    for word in text.split():
        if word in TENS or word in UNITS:
            total += TENS.get(word, UNITS.get(word))
        elif word.isdigit():
            total += int(word)
        else:
            return None
    return total


def run(argument):
    words = argument.lower().split()
    first = words[0] if words else ""

    if first in UP or first in DOWN:
        _nudge(1 if first in UP else -1, " ".join(word for word in words[1:] if word != "by"))
    elif first in ("mute", "unmute", "silence"):
        _mute(first == "unmute")
    else:
        _set(to_number(argument))


def _nudge(direction, amount):
    step = to_number(amount) if amount else STEP
    if step is None:
        say("Say how much, like volume up by twenty.")
        return

    current = audio.get_level()
    level = None if current is None else audio.set_level(current + direction * step)
    if level is None:
        # No Core Audio here, but the volume keys still work, two percent a press.
        win.tap_key(win.VK_VOLUME_UP if direction > 0 else win.VK_VOLUME_DOWN, max(1, step // 2))
        say("Volume up" if direction > 0 else "Volume down")
        return
    say(f"Volume {level}")


def _mute(only_unmute):
    # The mute key toggles, so "unmute" while the sound is on would mute it.
    if only_unmute and audio.is_muted() is False:
        say("Sound is already on")
        return
    win.tap_key(win.VK_VOLUME_MUTE)
    muted = audio.is_muted()
    say("Toggled mute" if muted is None else "Muted" if muted else "Sound back on")


def _set(wanted):
    if wanted is None:
        say("Say volume up, volume down, volume mute, or a number like volume fifty.")
    elif wanted > 100:
        say("I can only go up to a hundred.")
    elif (level := audio.set_level(wanted)) is None:
        warn("I could not reach the volume control on this PC.")
        detail("Use 'volume up' and 'volume down' instead.")
    else:
        say(f"Volume {level}")
