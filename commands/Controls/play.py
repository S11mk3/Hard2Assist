"""Play or pause whatever is currently playing.

Sends the same media key a keyboard with playback buttons would, so Windows
routes it to whichever app is playing -- Spotify, a YouTube tab, VLC --
without this command needing to know which.
"""

import win
from output import say

NAME = "play"
TAKES_ARG = False
ALIASES = ("pause", "plays", "played", "resume")
HELP = "play         -- play or pause whatever is playing"


def run():
    win.tap_key(win.VK_MEDIA_PLAY_PAUSE)
    # The same key toggles both and there is no way to query which happened,
    # so the confirmation has to cover either case.
    say("Play or pause")
