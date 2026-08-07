"""What day it is."""

from datetime import datetime

from output import announce

NAME = "date"
TAKES_ARG = False
ALIASES = ("day", "today", "dates")
HELP = "date         -- what day it is"


def run():
    now = datetime.now()
    announce(f"It's {now.strftime('%A, %B %#d')}")
