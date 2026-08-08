"""Say what day it is."""

from datetime import datetime

from output import say

NAME = "date"
TAKES_ARG = False
ALIASES = ("day", "today", "dates")
HELP = "date         -- what day it is"


def run():
    now = datetime.now()
    say(f"It's {now.strftime('%A, %B %#d')}")
