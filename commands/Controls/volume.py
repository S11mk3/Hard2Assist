"""Turn the volume up and down."""

import win
from output import announce

NAME = "volume"
TAKES_ARG = True
ALIASES = ("vol", "sound", "volumes")
HELP = "volume up|down|mute -- change the volume"
EXAMPLE = "volume up"

# Each tap is one notch, which is 2% on Windows. Five is a noticeable step
# without being a jump.
STEPS = 5


def run(argument):
    what = argument.lower().strip()

    if what.startswith(("up", "higher", "louder", "increase")):
        win.tap_key(win.VK_VOLUME_UP, STEPS)
        announce("Volume up")

    elif what.startswith(("down", "lower", "quieter", "decrease")):
        win.tap_key(win.VK_VOLUME_DOWN, STEPS)
        announce("Volume down")

    elif what.startswith(("mute", "unmute", "silence")):
        win.tap_key(win.VK_VOLUME_MUTE)
        announce("Muted")

    elif what.startswith("max"):
        win.tap_key(win.VK_VOLUME_UP, 50)
        announce("Volume at maximum")

    else:
        announce("Say volume up, volume down, or volume mute.")
