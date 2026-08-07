"""What time is it."""

from datetime import datetime

from output import announce

NAME = "time"
TAKES_ARG = False
ALIASES = ("thyme", "time's")
HELP = "time         -- what time it is"


def run():
    now = datetime.now()
    # %#I is Windows' "hour without a leading zero". Saying "It's 07:05" sounds
    # like a robot; "It's 7:05" does not.
    announce(f"It's {now.strftime('%#I:%M %p').lower()}")
