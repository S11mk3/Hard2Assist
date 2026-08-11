"""Turn the volume up, down, or to an exact level."""

import audio
import win
from output import detail, say

NAME = "volume"
TAKES_ARG = True
ALIASES = ("vol", "sound", "volumes")
HELP = "volume up|down|mute|<number> -- change the volume"
EXAMPLE = "volume 50"

ABOUT = """\
Volume changes how loud this PC is.
"volume up" and "volume down" move it a few notches at a time; "louder"
and "quieter" do the same. "volume mute" silences it, and saying it again
brings the sound back.
For an exact level, give a number: "volume 50", "volume fifty", "volume
fifty percent", "volume twenty five". "volume max" and "volume half" work
too.
The sentence can go the other way round -- "turn up the volume" and "mute
the volume" both land here.\
"""

# Each key tap moves the volume one notch, which is 2% on Windows. Five taps
# is a noticeable step without being a jump.
STEPS = 5

# Spoken numbers arrive as words at least as often as digits.
UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19,
}
TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fourty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}


def to_number(text):
    """Parse "50", "fifty" or "twenty five" into an int. None if it is not a number."""
    text = text.lower().replace("percent", "").replace("%", "")
    text = text.replace("-", " ").strip()

    if not text:
        return None

    if text.isdigit():
        return int(text)

    if text in ("max", "maximum", "full", "all the way"):
        return 100
    if text in ("half", "halfway"):
        return 50
    if text in ("hundred", "one hundred", "a hundred"):
        return 100

    total = 0
    seen = False
    for word in text.split():
        if word in TENS:
            total += TENS[word]
            seen = True
        elif word in UNITS:
            total += UNITS[word]
            seen = True
        elif word.isdigit():
            total += int(word)
            seen = True
        else:
            # Any unrecognised word means this is not a number phrase.
            return None

    return total if seen else None


def run(argument):
    what = argument.lower().strip()

    if what.startswith(("up", "higher", "louder", "increase")):
        win.tap_key(win.VK_VOLUME_UP, STEPS)
        say("Volume up")
        return

    if what.startswith(("down", "lower", "quieter", "decrease")):
        win.tap_key(win.VK_VOLUME_DOWN, STEPS)
        say("Volume down")
        return

    if what.startswith(("mute", "unmute", "silence")):
        win.tap_key(win.VK_VOLUME_MUTE)
        say("Muted")
        return

    # Exact level: "volume 50", "volume fifty", "volume fifty percent",
    # "volume max".
    wanted = to_number(what)
    if wanted is None:
        say("Say volume up, volume down, volume mute, or a number like "
            "volume fifty.")
        return

    if wanted > 100:
        say("I can only go up to a hundred.")
        return

    result = audio.set_level(wanted)
    if result is None:
        say("I could not reach the volume control on this PC.")
        detail("Use 'volume up' and 'volume down' instead.")
        return

    say(f"Volume {result}")
