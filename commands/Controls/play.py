"""Play, pause and skip whatever is playing.

These are the media keys a keyboard with playback buttons sends, so Windows
routes them to whichever app is playing -- Spotify, a YouTube tab, VLC. Nothing
here needs to know which.
"""

import win
from output import announce

NAME = "play"
TAKES_ARG = False
ALIASES = ("pause", "plays", "played", "resume")
HELP = "play         -- play or pause whatever is playing"


def run():
    win.tap_key(win.VK_MEDIA_PLAY_PAUSE)
    # The same key does both and there is no way to ask which happened, so the
    # wording has to cover either.
    announce("Play or pause")
